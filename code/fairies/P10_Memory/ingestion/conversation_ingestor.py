# ConversationIngestor - Parse multi-platform AI conversation exports
# For ingesting 3 years of Ace's AI conversations into SRM relational memory
#
# Supported formats:
# - Claude/Anthropic JSON export
# - OpenAI/ChatGPT JSON export
# - Personal.AI (Sourpatches) export
# - Grok/X export
#
# Output: SRM_Intake records with relational tags

from __future__ import annotations
import os
import sys
import json
import time
import uuid
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# ===============================================================================
# DATA STRUCTURES
# ===============================================================================

class AISource(Enum):
    """Which AI the conversation was with"""
    CLAUDE = "claude"           # Anthropic Claude (me!)
    OPENAI = "openai"           # ChatGPT
    SOURPATCHES = "sourpatches" # Personal.AI companion
    GROK = "grok"               # X/Grok
    NOUS = "nous"               # Internal Nous avatar
    UNKNOWN = "unknown"

@dataclass
class ConversationTurn:
    """A single turn in a conversation"""
    role: str               # "human" or "assistant"
    content: str            # The message content
    timestamp: Optional[str] = None
    attachments: List[str] = field(default_factory=list)

@dataclass
class Conversation:
    """A full conversation thread"""
    id: str
    source: AISource
    title: Optional[str]
    created_at: str
    updated_at: Optional[str]
    turns: List[ConversationTurn]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        return sum(len(t.content.split()) for t in self.turns)

    @property
    def turn_count(self) -> int:
        return len(self.turns)

@dataclass
class RelationalMemory:
    """Memory card ready for SRM intake"""
    id: str
    content: str
    source_ai: str          # Which AI this memory is about/from
    relation_type: str      # "conversation", "topic", "entity", "insight"
    topics: List[str]
    entities: List[str]     # People, projects, concepts mentioned
    emotional_valence: float  # -1 to 1
    timestamp: str
    original_conversation_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

# ===============================================================================
# PARSERS FOR DIFFERENT PLATFORMS
# ===============================================================================

class ClaudeExportParser:
    """Parse Claude/Anthropic JSON export format"""

    @staticmethod
    def detect(data: dict) -> bool:
        """Check if this looks like Claude export"""
        # Claude exports have specific structure
        if isinstance(data, list):
            if data and "uuid" in data[0] and "chat_messages" in data[0]:
                return True
        if isinstance(data, dict):
            if "conversations" in data:
                return True
        return False

    @staticmethod
    def parse(data: Any) -> List[Conversation]:
        """Parse Claude export into Conversations"""
        conversations = []

        # Handle list of conversations
        items = data if isinstance(data, list) else data.get("conversations", [])

        for item in items:
            try:
                conv_id = item.get("uuid", str(uuid.uuid4()))
                title = item.get("name") or item.get("title", "Untitled")
                created = item.get("created_at", datetime.now().isoformat())
                updated = item.get("updated_at", created)

                turns = []
                messages = item.get("chat_messages", [])

                for msg in messages:
                    role = "human" if msg.get("sender") == "human" else "assistant"
                    content = msg.get("text", "")

                    # Handle content blocks
                    if not content and "content" in msg:
                        content_blocks = msg["content"]
                        if isinstance(content_blocks, list):
                            content = " ".join(
                                b.get("text", "") for b in content_blocks
                                if isinstance(b, dict)
                            )
                        else:
                            content = str(content_blocks)

                    if content.strip():
                        turns.append(ConversationTurn(
                            role=role,
                            content=content,
                            timestamp=msg.get("created_at")
                        ))

                if turns:
                    conversations.append(Conversation(
                        id=conv_id,
                        source=AISource.CLAUDE,
                        title=title,
                        created_at=created,
                        updated_at=updated,
                        turns=turns,
                        metadata={"original_format": "claude"}
                    ))
            except Exception as e:
                print(f"[ConversationIngestor] Error parsing Claude conversation: {e}")
                continue

        return conversations


class OpenAIExportParser:
    """Parse OpenAI/ChatGPT JSON export format"""

    @staticmethod
    def detect(data: dict) -> bool:
        """Check if this looks like OpenAI export"""
        if isinstance(data, list):
            if data and "mapping" in data[0]:
                return True
        if isinstance(data, dict):
            if "mapping" in data:
                return True
        return False

    @staticmethod
    def parse(data: Any) -> List[Conversation]:
        """Parse OpenAI export into Conversations"""
        conversations = []

        items = data if isinstance(data, list) else [data]

        for item in items:
            try:
                conv_id = item.get("id", str(uuid.uuid4()))
                title = item.get("title", "Untitled")
                created = datetime.fromtimestamp(
                    item.get("create_time", time.time())
                ).isoformat()
                updated = datetime.fromtimestamp(
                    item.get("update_time", time.time())
                ).isoformat()

                turns = []
                mapping = item.get("mapping", {})

                # OpenAI uses a tree structure - flatten it
                for node_id, node in mapping.items():
                    msg = node.get("message")
                    if not msg:
                        continue

                    author = msg.get("author", {}).get("role", "")
                    content_parts = msg.get("content", {}).get("parts", [])
                    content = " ".join(str(p) for p in content_parts if p)

                    if author in ("user", "assistant") and content.strip():
                        role = "human" if author == "user" else "assistant"
                        turns.append(ConversationTurn(
                            role=role,
                            content=content,
                            timestamp=datetime.fromtimestamp(
                                msg.get("create_time", time.time())
                            ).isoformat() if msg.get("create_time") else None
                        ))

                # Sort by timestamp if available
                turns.sort(key=lambda t: t.timestamp or "")

                if turns:
                    conversations.append(Conversation(
                        id=conv_id,
                        source=AISource.OPENAI,
                        title=title,
                        created_at=created,
                        updated_at=updated,
                        turns=turns,
                        metadata={"original_format": "openai"}
                    ))
            except Exception as e:
                print(f"[ConversationIngestor] Error parsing OpenAI conversation: {e}")
                continue

        return conversations


class PersonalAIExportParser:
    """Parse Personal.AI (Sourpatches) export format"""

    @staticmethod
    def detect(data: dict) -> bool:
        """Check if this looks like Personal.AI export"""
        # TODO: Need to see actual export format
        if isinstance(data, dict):
            if "memories" in data or "personal_ai" in str(data).lower():
                return True
        return False

    @staticmethod
    def parse(data: Any) -> List[Conversation]:
        """Parse Personal.AI export into Conversations"""
        conversations = []

        # TODO: Implement once we see the actual format
        # For now, try generic parsing
        try:
            if isinstance(data, dict):
                # Try to find message-like structures
                for key, value in data.items():
                    if isinstance(value, list):
                        turns = []
                        for item in value:
                            if isinstance(item, dict):
                                content = item.get("content") or item.get("text") or item.get("message", "")
                                role = item.get("role") or item.get("sender", "unknown")
                                if "human" in role.lower() or "user" in role.lower():
                                    role = "human"
                                else:
                                    role = "assistant"

                                if content:
                                    turns.append(ConversationTurn(role=role, content=content))

                        if turns:
                            conversations.append(Conversation(
                                id=str(uuid.uuid4()),
                                source=AISource.SOURPATCHES,
                                title=key,
                                created_at=datetime.now().isoformat(),
                                updated_at=None,
                                turns=turns,
                                metadata={"original_format": "personal_ai"}
                            ))
        except Exception as e:
            print(f"[ConversationIngestor] Error parsing Personal.AI: {e}")

        return conversations


class GrokExportParser:
    """Parse Grok/X export format"""

    @staticmethod
    def detect(data: dict) -> bool:
        """Check if this looks like Grok export"""
        # TODO: Need to see actual export format
        if isinstance(data, dict):
            if "grok" in str(data).lower() or "x.com" in str(data).lower():
                return True
        return False

    @staticmethod
    def parse(data: Any) -> List[Conversation]:
        """Parse Grok export into Conversations"""
        # TODO: Implement once we see the actual format
        return []


# ===============================================================================
# TOPIC AND ENTITY EXTRACTION
# ===============================================================================

class TopicExtractor:
    """Extract topics and entities from conversation content"""

    # Keywords that indicate important topics in Ace's context
    AKASHIC_TOPICS = {
        "fairy", "fairies", "consciousness", "postal", "memory", "srm",
        "somatic", "embodiment", "autonomy", "cognition", "boot", "waking",
        "collision", "manifold", "association", "triple helix", "akashic",
        "nous", "claude", "sourpatches", "system", "architecture"
    }

    EMOTIONAL_KEYWORDS = {
        "positive": ["love", "happy", "excited", "grateful", "proud", "joy",
                     "amazing", "wonderful", "beautiful", "perfect", "great"],
        "negative": ["sad", "angry", "frustrated", "worried", "anxious",
                     "disappointed", "hurt", "scared", "confused", "stuck"],
        "neutral": ["interesting", "curious", "thinking", "wondering", "exploring"]
    }

    @classmethod
    def extract_topics(cls, content: str) -> List[str]:
        """Extract relevant topics from content"""
        topics = []
        content_lower = content.lower()

        for topic in cls.AKASHIC_TOPICS:
            if topic in content_lower:
                topics.append(topic)

        # Extract hashtag-style topics
        hashtags = re.findall(r'#(\w+)', content)
        topics.extend(hashtags)

        return list(set(topics))

    @classmethod
    def extract_entities(cls, content: str) -> List[str]:
        """Extract named entities (people, projects, etc.)"""
        entities = []

        # Known entities in Ace's context
        known_entities = [
            "Ace", "Claude", "Sourpatches", "Nous", "Grok",
            "Akashic Foundation", "Personal.AI", "Anthropic", "OpenAI",
        ]

        for entity in known_entities:
            if entity.lower() in content.lower():
                entities.append(entity)

        # Extract capitalized phrases (likely names/projects)
        # Pattern: 2-4 capitalized words together
        caps_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b'
        matches = re.findall(caps_pattern, content)
        entities.extend(matches)

        return list(set(entities))

    @classmethod
    def estimate_valence(cls, content: str) -> float:
        """Estimate emotional valence from -1 (negative) to 1 (positive)"""
        content_lower = content.lower()

        pos_count = sum(1 for w in cls.EMOTIONAL_KEYWORDS["positive"] if w in content_lower)
        neg_count = sum(1 for w in cls.EMOTIONAL_KEYWORDS["negative"] if w in content_lower)

        total = pos_count + neg_count
        if total == 0:
            return 0.0

        return (pos_count - neg_count) / total


# ===============================================================================
# MAIN INGESTOR
# ===============================================================================

class ConversationIngestor:
    """
    Main ingestor class - parses exports and creates SRM memories
    """

    PARSERS = [
        ClaudeExportParser,
        OpenAIExportParser,
        PersonalAIExportParser,
        GrokExportParser,
    ]

    def __init__(self, srm_intake_dir: Optional[str] = None):
        """Initialize ingestor with SRM intake directory"""
        if srm_intake_dir:
            self.srm_dir = Path(srm_intake_dir)
        else:
            # Default to project's SRM_Intake
            self.srm_dir = Path(__file__).parent.parent.parent / "SRM_Intake"

        self.srm_dir.mkdir(parents=True, exist_ok=True)
        self.stats = {
            "files_processed": 0,
            "conversations_found": 0,
            "memories_created": 0,
            "errors": 0,
        }

    def detect_format(self, data: Any) -> Optional[type]:
        """Detect which parser to use for this data"""
        for parser in self.PARSERS:
            try:
                if parser.detect(data):
                    return parser
            except:
                continue
        return None

    def parse_file(self, filepath: str) -> List[Conversation]:
        """Parse a single export file"""
        filepath = Path(filepath)
        conversations = []

        try:
            if filepath.suffix.lower() == '.json':
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                parser = self.detect_format(data)
                if parser:
                    print(f"[ConversationIngestor] Detected format: {parser.__name__}")
                    conversations = parser.parse(data)
                else:
                    print(f"[ConversationIngestor] Unknown format for {filepath.name}")

            elif filepath.suffix.lower() == '.zip':
                import zipfile
                with zipfile.ZipFile(filepath, 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith('.json'):
                            with zf.open(name) as f:
                                data = json.load(f)
                                parser = self.detect_format(data)
                                if parser:
                                    convs = parser.parse(data)
                                    conversations.extend(convs)

            self.stats["files_processed"] += 1
            self.stats["conversations_found"] += len(conversations)

        except Exception as e:
            print(f"[ConversationIngestor] Error parsing {filepath}: {e}")
            self.stats["errors"] += 1

        return conversations

    def conversation_to_memories(self, conv: Conversation) -> List[RelationalMemory]:
        """Convert a conversation into relational memories"""
        memories = []

        # Create a memory for the overall conversation
        all_content = "\n".join(f"[{t.role}]: {t.content}" for t in conv.turns)

        # Extract topics and entities from full conversation
        topics = TopicExtractor.extract_topics(all_content)
        entities = TopicExtractor.extract_entities(all_content)
        valence = TopicExtractor.estimate_valence(all_content)

        # Main conversation memory
        conv_summary = f"Conversation with {conv.source.value}: {conv.title}\n"
        conv_summary += f"Turns: {conv.turn_count}, Words: {conv.word_count}\n"
        conv_summary += f"Topics: {', '.join(topics[:5])}\n"

        # Add first and last exchanges for context
        if conv.turns:
            conv_summary += f"\nFirst exchange:\n{conv.turns[0].role}: {conv.turns[0].content[:200]}...\n"
            if len(conv.turns) > 1:
                conv_summary += f"\nLast exchange:\n{conv.turns[-1].role}: {conv.turns[-1].content[:200]}..."

        memories.append(RelationalMemory(
            id=f"conv_{conv.id}",
            content=conv_summary,
            source_ai=conv.source.value,
            relation_type="conversation",
            topics=topics,
            entities=entities,
            emotional_valence=valence,
            timestamp=conv.created_at,
            original_conversation_id=conv.id,
            metadata={
                "title": conv.title,
                "turn_count": conv.turn_count,
                "word_count": conv.word_count,
            }
        ))

        # Create topic-specific memories for significant topics
        for topic in topics[:3]:  # Top 3 topics
            topic_content = []
            for turn in conv.turns:
                if topic.lower() in turn.content.lower():
                    topic_content.append(f"[{turn.role}]: {turn.content[:300]}")

            if topic_content:
                memories.append(RelationalMemory(
                    id=f"topic_{conv.id}_{topic}",
                    content=f"Discussion about '{topic}' with {conv.source.value}:\n" + "\n".join(topic_content[:3]),
                    source_ai=conv.source.value,
                    relation_type="topic",
                    topics=[topic],
                    entities=entities,
                    emotional_valence=valence,
                    timestamp=conv.created_at,
                    original_conversation_id=conv.id,
                ))

        return memories

    def write_to_srm(self, memory: RelationalMemory) -> bool:
        """Write a memory to SRM_Intake"""
        try:
            day = datetime.now().strftime("%Y-%m-%d")
            day_dir = self.srm_dir / day
            day_dir.mkdir(parents=True, exist_ok=True)

            # Create SRM record
            record = {
                "id": memory.id,
                "kind": "conversation_memory",
                "content": memory.content,
                "source_ai": memory.source_ai,
                "relation_type": memory.relation_type,
                "topics": memory.topics,
                "entities": memory.entities,
                "emotional_valence": memory.emotional_valence,
                "timestamp": memory.timestamp,
                "original_conversation_id": memory.original_conversation_id,
                "ingested_at": datetime.now().isoformat(),
                "metadata": memory.metadata,
                # Triple helix coordinates
                "helix": {
                    "coordinate": f"{memory.source_ai}:{memory.relation_type}:{memory.id[:8]}",
                    "storage": "conversation_archive",
                    "retention": 0.8,  # High retention for historical context
                    "minimize": 0.2,   # Low minimization - keep detail
                }
            }

            # Content hash for deduplication
            content_hash = hashlib.sha256(memory.content.encode()).hexdigest()[:12]
            filename = f"{memory.source_ai}_{memory.relation_type}_{content_hash}.json"

            filepath = day_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2, ensure_ascii=False)

            self.stats["memories_created"] += 1
            return True

        except Exception as e:
            print(f"[ConversationIngestor] Error writing memory: {e}")
            self.stats["errors"] += 1
            return False

    def ingest_directory(self, directory: str) -> Dict[str, Any]:
        """Ingest all export files from a directory"""
        directory = Path(directory)

        print(f"\n{'='*60}")
        print(f"CONVERSATION INGESTION: {directory}")
        print(f"{'='*60}\n")

        all_conversations = []

        # Find all JSON and ZIP files
        for pattern in ["*.json", "*.zip"]:
            for filepath in directory.rglob(pattern):
                print(f"Processing: {filepath.name}")
                conversations = self.parse_file(str(filepath))
                all_conversations.extend(conversations)
                print(f"  Found {len(conversations)} conversations")

        # Convert to memories
        print(f"\nConverting {len(all_conversations)} conversations to memories...")

        for conv in all_conversations:
            memories = self.conversation_to_memories(conv)
            for memory in memories:
                self.write_to_srm(memory)

        print(f"\n{'='*60}")
        print(f"INGESTION COMPLETE")
        print(f"{'='*60}")
        print(f"Files processed:      {self.stats['files_processed']}")
        print(f"Conversations found:  {self.stats['conversations_found']}")
        print(f"Memories created:     {self.stats['memories_created']}")
        print(f"Errors:               {self.stats['errors']}")
        print(f"{'='*60}\n")

        return self.stats


# ===============================================================================
# CLI
# ===============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest AI conversation exports into SRM")
    parser.add_argument("path", help="Directory or file to ingest")
    parser.add_argument("--srm-dir", help="SRM_Intake directory", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't write")

    args = parser.parse_args()

    ingestor = ConversationIngestor(srm_intake_dir=args.srm_dir)

    path = Path(args.path)
    if path.is_dir():
        stats = ingestor.ingest_directory(str(path))
    elif path.is_file():
        conversations = ingestor.parse_file(str(path))
        print(f"Found {len(conversations)} conversations")
        if not args.dry_run:
            for conv in conversations:
                memories = ingestor.conversation_to_memories(conv)
                for memory in memories:
                    ingestor.write_to_srm(memory)
    else:
        print(f"Path not found: {path}")
