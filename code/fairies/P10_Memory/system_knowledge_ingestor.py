"""
System Knowledge Ingestor

Processes system knowledge documents (like whisper_core_knowledge.md) into
SRM_Intake records so the CognitionRouter can recall them.

This is how the system learns about itself - self-knowledge becomes
searchable memory.
"""

import os
import sys
import json
import time
import uuid
import re
from typing import List, Dict, Optional


def chunk_by_sections(content: str) -> List[Dict]:
    """
    Split markdown content into chunks by ## headers.
    Each section becomes a separate memory record with Q&A format.
    """
    chunks = []

    # Split by ## headers
    sections = re.split(r'\n## ', content)

    for section in sections:
        if not section.strip():
            continue

        lines = section.strip().split('\n')

        # First line is the header (title/question)
        header = lines[0].strip()
        if header.startswith('#'):
            header = header.lstrip('#').strip()

        # Rest is the content (answer)
        body_lines = lines[1:]
        body = '\n'.join(body_lines).strip()

        if not body:
            continue

        # Clean up the body - remove markdown formatting for cleaner recall
        body_clean = body.replace('**', '').replace('`', '')

        # Create a searchable query from the header
        # "What is X?" style questions work well for recall
        if not header.endswith('?'):
            query = f"What is {header}?" if not header.lower().startswith('what') else header
        else:
            query = header

        chunks.append({
            "header": header,
            "query": query,
            "content": body_clean,
            "content_preview": body_clean[:200] + "..." if len(body_clean) > 200 else body_clean
        })

    return chunks


def ingest_knowledge_file(filepath: str, srm_dir: str = None) -> Dict:
    """
    Ingest a knowledge markdown file into SRM_Intake.

    Returns stats about ingestion.
    """
    if srm_dir is None:
        srm_dir = os.path.join(os.getcwd(), "SRM_Intake")

    day = time.strftime("%Y-%m-%d", time.gmtime())
    day_dir = os.path.join(srm_dir, day)
    os.makedirs(day_dir, exist_ok=True)

    # Read the file
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Get source filename for tracking
    source_name = os.path.basename(filepath)

    # Chunk into sections
    chunks = chunk_by_sections(content)

    stats = {
        "source": source_name,
        "chunks_created": 0,
        "files_written": []
    }

    for chunk in chunks:
        # Create a conversation.learning style record
        # This format is recognized by CognitionRouter for recall
        record = {
            "kind": "system.knowledge",
            "data": {
                "query": chunk["query"],
                "response": chunk["content"],
                "source": "system_knowledge",
                "source_file": source_name,
                "header": chunk["header"],
                "learned_at": time.time(),
            },
            "meta": {
                "type": "system_knowledge",
                "source_file": source_name,
                "header": chunk["header"],
            },
            "ts": time.time()
        }

        # Write to SRM_Intake
        fname = f"system.knowledge-{uuid.uuid4().hex[:8]}.json"
        fpath = os.path.join(day_dir, fname)

        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=2)

        stats["chunks_created"] += 1
        stats["files_written"].append(fpath)

        print(f"  [OK] {chunk['header'][:50]}...")

    return stats


def ingest_all_knowledge(knowledge_dir: str = None, srm_dir: str = None) -> Dict:
    """
    Ingest all .md files from the knowledge directory.
    """
    if knowledge_dir is None:
        knowledge_dir = os.path.join(os.getcwd(), "P10_Memory", "system_knowledge")

    if not os.path.isdir(knowledge_dir):
        print(f"Knowledge directory not found: {knowledge_dir}")
        return {"error": "directory_not_found"}

    stats = {
        "files_processed": 0,
        "total_chunks": 0,
        "details": []
    }

    for fname in os.listdir(knowledge_dir):
        if fname.endswith('.md'):
            fpath = os.path.join(knowledge_dir, fname)
            print(f"\n Processing: {fname}")

            file_stats = ingest_knowledge_file(fpath, srm_dir)
            stats["files_processed"] += 1
            stats["total_chunks"] += file_stats["chunks_created"]
            stats["details"].append(file_stats)

    return stats


def update_cognition_router_for_system_knowledge():
    """
    Patch the CognitionRouter to also search system.knowledge records.
    """
    # The router already searches conversation.learning, but we need
    # to also check system.knowledge records
    pass  # Already handled by the scoring update we made earlier


if __name__ == "__main__":
    print("=" * 60)
    print("SYSTEM KNOWLEDGE INGESTOR")
    print("=" * 60)

    # Find the ebook root
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Check if we're in the right place
    knowledge_dir = os.path.join(script_dir, "system_knowledge")
    srm_dir = os.path.join(os.path.dirname(script_dir), "SRM_Intake")

    if not os.path.isdir(knowledge_dir):
        # Try from ebook root
        ebook_root = os.path.dirname(script_dir)
        knowledge_dir = os.path.join(ebook_root, "P10_Memory", "system_knowledge")
        srm_dir = os.path.join(ebook_root, "SRM_Intake")

    print(f"\nKnowledge dir: {knowledge_dir}")
    print(f"SRM dir: {srm_dir}")

    if os.path.isdir(knowledge_dir):
        stats = ingest_all_knowledge(knowledge_dir, srm_dir)

        print("\n" + "=" * 60)
        print("INGESTION COMPLETE")
        print("=" * 60)
        print(f"Files processed: {stats['files_processed']}")
        print(f"Total chunks created: {stats['total_chunks']}")
        print("\nThe system now knows about itself!")
        print("Try asking: 'What is the consciousness loop?'")
    else:
        print(f"\n[X] Knowledge directory not found: {knowledge_dir}")
        print("Create it and add .md files with system knowledge.")
