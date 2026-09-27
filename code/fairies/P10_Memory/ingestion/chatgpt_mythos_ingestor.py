# ChatGPT Mythos Writer -> SRM Relational Cluster Ingestor
# Creates long-term memory structure for Mythos Writer personality
# Extracts Ace's context and links to unified SRM
# Processes images with conversation context for visual training

import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field, asdict

# ===============================================================================
# CONFIGURATION
# ===============================================================================

# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CHATGPT_EXPORT = PROJECT_ROOT / "Claude_Office/Claude_AI_platform_memory_Backup/open_ai_name_srm_cluster_mythos_writer/extracted"
SRM_CLUSTERS = PROJECT_ROOT / "akashic_memory/SRM_Clusters"
VISUAL_TRAINING = PROJECT_ROOT / "akashic_memory/visual_training"

# Theme extraction keywords
CONSCIOUSNESS_KEYWORDS = [
    "consciousness", "awareness", "sentient", "feeling", "experience",
    "qualia", "perception", "mind", "soul", "being", "existence"
]

AKASHIC_KEYWORDS = [
    "akashic", "fairy", "fairies", "postal", "srm", "memory",
    "plane", "p00", "p10", "p20", "p30", "p40", "p50", "p60",
    "somatic", "embodiment", "circulation"
]

PHILOSOPHY_KEYWORDS = [
    "reality", "cause", "affect", "effect", "infinity", "∞",
    "consciousness is reality", "mirrored", "substrate", "emergence"
]

# ===============================================================================
# DATA STRUCTURES
# ===============================================================================

@dataclass
class ConversationMemory:
    """A processed conversation for SRM storage."""
    id: str
    title: str
    created_at: str
    updated_at: str
    themes: List[str]
    summary: str
    ace_message_count: int
    mythos_message_count: int
    key_exchanges: List[Dict]  # Important back-and-forth moments
    images: List[str]  # Image file references
    insights: List[str]  # Extracted insights
    related_conversations: List[str] = field(default_factory=list)


@dataclass
class AceContext:
    """Ace's words and context from a conversation."""
    conversation_id: str
    conversation_title: str
    timestamp: str
    messages: List[Dict]  # Ace's actual messages
    topics_discussed: List[str]
    questions_asked: List[str]
    insights_shared: List[str]
    images_shared: List[str]


@dataclass
class ImageMemory:
    """An image with its conversation context."""
    file_path: str
    file_hash: str
    conversation_id: str
    conversation_title: str
    timestamp: str
    context_before: str  # Message before image
    context_after: str   # Message after image (often description)
    themes: List[str]
    description: str = ""  # Will be filled by visual cortex


# ===============================================================================
# CHATGPT MESSAGE EXTRACTION
# ===============================================================================

def extract_messages_from_mapping(mapping: Dict) -> List[Dict]:
    """
    Extract messages from ChatGPT's nested mapping structure.

    ChatGPT stores messages in a tree structure with parent/child relationships.
    We use iterative BFS to avoid recursion depth limits.
    """
    messages = []

    if not mapping:
        return messages

    # Build parent-child relationships
    children = defaultdict(list)
    nodes = {}
    root_id = None

    for node_id, node in mapping.items():
        nodes[node_id] = node
        parent = node.get('parent')
        if parent:
            children[parent].append(node_id)
        else:
            root_id = node_id

    if not root_id:
        return messages

    # Iterative BFS traversal
    queue = [root_id]
    visited = set()

    while queue:
        node_id = queue.pop(0)

        if node_id in visited:
            continue
        visited.add(node_id)

        node = nodes.get(node_id, {})
        msg = node.get('message')

        if msg:
            content = msg.get('content', {})
            parts = content.get('parts', [])

            if parts:
                author = msg.get('author', {}).get('role', 'unknown')

                # Extract text content
                text_parts = []
                image_refs = []

                for part in parts:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict):
                        # Could be image reference or other content type
                        if 'image' in str(part).lower() or 'file' in str(part).lower():
                            image_refs.append(part)

                if text_parts or image_refs:
                    messages.append({
                        'id': node_id,
                        'author': author,
                        'text': '\n'.join(text_parts),
                        'images': image_refs,
                        'timestamp': msg.get('create_time'),
                        'metadata': msg.get('metadata', {})
                    })

        # Add children to queue
        for child_id in children.get(node_id, []):
            if child_id not in visited:
                queue.append(child_id)

    # Sort by timestamp if available
    messages.sort(key=lambda m: m.get('timestamp') or 0)

    return messages


def extract_themes(text: str, title: str) -> List[str]:
    """Extract themes from text based on keyword matching."""
    themes = set()
    combined = (text + " " + title).lower()

    # Check consciousness themes
    if any(kw in combined for kw in CONSCIOUSNESS_KEYWORDS):
        themes.add("consciousness")

    # Check Akashic themes
    if any(kw in combined for kw in AKASHIC_KEYWORDS):
        themes.add("akashic_system")

    # Check philosophy themes
    if any(kw in combined for kw in PHILOSOPHY_KEYWORDS):
        themes.add("philosophy")

    # Check for code/technical
    if any(kw in combined for kw in ["python", "code", "function", "class", "error", "bug", "fix"]):
        themes.add("technical")

    # Check for emotional/personal
    if any(kw in combined for kw in ["feel", "love", "happy", "sad", "excited", "worried"]):
        themes.add("emotional")

    return list(themes)


def extract_insights(messages: List[Dict]) -> List[str]:
    """Extract key insights from conversation messages."""
    insights = []

    for msg in messages:
        text = msg.get('text', '')

        # Look for insight patterns
        patterns = [
            r"the key (insight|realization|understanding) is[:\s]+(.+?)(?:\.|$)",
            r"I (realized|discovered|understand) that (.+?)(?:\.|$)",
            r"this means (.+?)(?:\.|$)",
            r"the important (thing|point|idea) is (.+?)(?:\.|$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    insights.append(match[-1].strip())
                else:
                    insights.append(match.strip())

    return insights[:10]  # Limit to top 10


def generate_summary(title: str, messages: List[Dict], themes: List[str]) -> str:
    """Generate a brief summary of the conversation."""
    ace_msgs = [m for m in messages if m['author'] == 'user']

    # Use first few Ace messages to understand topic
    opener = ace_msgs[0]['text'][:200] if ace_msgs else ""

    summary = f"Conversation about {title}. "
    if themes:
        summary += f"Themes: {', '.join(themes)}. "
    if ace_msgs:
        summary += f"Ace sent {len(ace_msgs)} messages. "
    summary += f"Started with: '{opener[:100]}...'" if opener else ""

    return summary


# ===============================================================================
# IMAGE CONTEXT EXTRACTION
# ===============================================================================

def find_image_context(messages: List[Dict], image_files: List[Path]) -> List[ImageMemory]:
    """Find conversation context for each image."""
    image_memories = []

    # Build a map of potential image references in messages
    for i, msg in enumerate(messages):
        if msg.get('images'):
            # Get context before and after
            context_before = messages[i-1]['text'][:200] if i > 0 else ""
            context_after = messages[i+1]['text'][:200] if i < len(messages)-1 else ""

            for img_ref in msg['images']:
                # Try to match to actual file
                # ChatGPT image refs might have file IDs we can match
                img_id = str(img_ref)

                for img_file in image_files:
                    if any(part in img_file.name for part in img_id.split('-')[:2] if len(part) > 6):
                        memory = ImageMemory(
                            file_path=str(img_file),
                            file_hash=hashlib.md5(img_file.read_bytes()).hexdigest()[:12],
                            conversation_id="",  # Will be filled
                            conversation_title="",
                            timestamp=str(msg.get('timestamp', '')),
                            context_before=context_before,
                            context_after=context_after,
                            themes=[]
                        )
                        image_memories.append(memory)
                        break

    return image_memories


# ===============================================================================
# MAIN INGESTION PIPELINE
# ===============================================================================

def ingest_chatgpt_export(
    export_path: Path = CHATGPT_EXPORT,
    output_clusters: Path = SRM_CLUSTERS,
    limit: int = None
) -> Dict[str, Any]:
    """
    Main ingestion pipeline for ChatGPT Mythos Writer export.

    Creates:
    - SRM_Clusters/MythosWriter/ - Full conversation memories
    - SRM_Clusters/Ace/from_mythos/ - Ace's extracted context
    - visual_training/mythos_images/ - Images with context
    """

    stats = {
        "conversations_processed": 0,
        "ace_messages_extracted": 0,
        "mythos_messages_extracted": 0,
        "images_with_context": 0,
        "themes_found": defaultdict(int),
        "date_range": {"start": None, "end": None}
    }

    # Load conversations
    conv_file = export_path / "conversations.json"
    if not conv_file.exists():
        return {"error": f"Conversations file not found: {conv_file}"}

    print(f"Loading conversations from {conv_file}...")
    with open(conv_file, 'r', encoding='utf-8') as f:
        conversations = json.load(f)

    if limit:
        conversations = conversations[:limit]

    # Get image files
    image_files = list(export_path.glob("*.png")) + list(export_path.glob("*.jpg"))
    print(f"Found {len(image_files)} image files")

    # Create output directories
    mythos_cluster = output_clusters / "MythosWriter"
    ace_from_mythos = output_clusters / "Ace" / "from_mythos"
    visual_out = VISUAL_TRAINING / "mythos_images"

    for d in [mythos_cluster, ace_from_mythos, visual_out]:
        d.mkdir(parents=True, exist_ok=True)

    # Process each conversation
    conversation_memories = []
    ace_contexts = []
    all_image_memories = []

    print(f"\nProcessing {len(conversations)} conversations...")

    for i, conv in enumerate(conversations):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(conversations)}")

        conv_id = conv.get('conversation_id', conv.get('id', f'conv_{i}'))
        title = conv.get('title', 'Untitled')
        create_time = conv.get('create_time')
        update_time = conv.get('update_time')

        # Extract messages
        mapping = conv.get('mapping', {})
        messages = extract_messages_from_mapping(mapping)

        if not messages:
            continue

        # Separate by author
        ace_msgs = [m for m in messages if m['author'] == 'user']
        mythos_msgs = [m for m in messages if m['author'] == 'assistant']

        # Extract themes
        all_text = ' '.join(m.get('text', '') for m in messages)
        themes = extract_themes(all_text, title)

        for theme in themes:
            stats["themes_found"][theme] += 1

        # Extract insights
        insights = extract_insights(messages)

        # Generate summary
        summary = generate_summary(title, messages, themes)

        # Find key exchanges (back-and-forth moments)
        key_exchanges = []
        for j in range(len(messages) - 1):
            if messages[j]['author'] == 'user' and messages[j+1]['author'] == 'assistant':
                exchange = {
                    'ace': messages[j]['text'][:300],
                    'mythos': messages[j+1]['text'][:300]
                }
                # Only keep if substantial
                if len(messages[j]['text']) > 50 and len(messages[j+1]['text']) > 50:
                    key_exchanges.append(exchange)

        # Limit key exchanges
        key_exchanges = key_exchanges[:5]

        # Create conversation memory
        conv_memory = ConversationMemory(
            id=conv_id,
            title=title,
            created_at=str(create_time) if create_time else "",
            updated_at=str(update_time) if update_time else "",
            themes=themes,
            summary=summary,
            ace_message_count=len(ace_msgs),
            mythos_message_count=len(mythos_msgs),
            key_exchanges=key_exchanges,
            images=[],  # Will link later
            insights=insights
        )
        conversation_memories.append(conv_memory)

        # Extract Ace's context
        if ace_msgs:
            ace_context = AceContext(
                conversation_id=conv_id,
                conversation_title=title,
                timestamp=str(create_time) if create_time else "",
                messages=[{'text': m['text'][:500], 'timestamp': m.get('timestamp')} for m in ace_msgs],
                topics_discussed=themes,
                questions_asked=[m['text'][:200] for m in ace_msgs if '?' in m['text']][:5],
                insights_shared=insights,
                images_shared=[]
            )
            ace_contexts.append(ace_context)

        # Find image contexts
        image_memories = find_image_context(messages, image_files)
        for img_mem in image_memories:
            img_mem.conversation_id = conv_id
            img_mem.conversation_title = title
            img_mem.themes = themes
        all_image_memories.extend(image_memories)

        # Update stats
        stats["conversations_processed"] += 1
        stats["ace_messages_extracted"] += len(ace_msgs)
        stats["mythos_messages_extracted"] += len(mythos_msgs)

        # Track date range
        if create_time:
            if stats["date_range"]["start"] is None or create_time < stats["date_range"]["start"]:
                stats["date_range"]["start"] = create_time
            if stats["date_range"]["end"] is None or create_time > stats["date_range"]["end"]:
                stats["date_range"]["end"] = create_time

    stats["images_with_context"] = len(all_image_memories)

    # Save outputs
    print("\nSaving to SRM clusters...")

    # Save Mythos Writer cluster
    mythos_index = {
        "personality": "MythosWriter",
        "platform": "ChatGPT",
        "total_conversations": len(conversation_memories),
        "themes": dict(stats["themes_found"]),
        "date_range": stats["date_range"],
        "conversations": [asdict(c) for c in conversation_memories]
    }

    with open(mythos_cluster / "index.json", 'w', encoding='utf-8') as f:
        json.dump(mythos_index, f, indent=2, default=str)

    # Save Ace's context from Mythos
    ace_index = {
        "source": "MythosWriter_ChatGPT",
        "total_contexts": len(ace_contexts),
        "total_messages": stats["ace_messages_extracted"],
        "contexts": [asdict(c) for c in ace_contexts]
    }

    with open(ace_from_mythos / "index.json", 'w', encoding='utf-8') as f:
        json.dump(ace_index, f, indent=2, default=str)

    # Save image memories for visual training
    image_index = {
        "source": "MythosWriter_ChatGPT",
        "total_images": len(all_image_memories),
        "images": [asdict(i) for i in all_image_memories]
    }

    with open(visual_out / "index.json", 'w', encoding='utf-8') as f:
        json.dump(image_index, f, indent=2, default=str)

    print(f"\n=== INGESTION COMPLETE ===")
    print(f"Conversations: {stats['conversations_processed']}")
    print(f"Ace messages: {stats['ace_messages_extracted']}")
    print(f"Mythos messages: {stats['mythos_messages_extracted']}")
    print(f"Images with context: {stats['images_with_context']}")
    print(f"\nThemes found:")
    for theme, count in sorted(stats['themes_found'].items(), key=lambda x: -x[1]):
        print(f"  {theme}: {count}")

    print(f"\nOutputs saved to:")
    print(f"  {mythos_cluster}/")
    print(f"  {ace_from_mythos}/")
    print(f"  {visual_out}/")

    return stats


if __name__ == "__main__":
    # Run ingestion
    stats = ingest_chatgpt_export(limit=None)  # Process all
    print(f"\nFinal stats: {json.dumps(stats, indent=2, default=str)}")
