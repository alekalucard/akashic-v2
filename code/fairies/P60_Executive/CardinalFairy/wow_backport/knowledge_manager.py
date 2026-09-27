"""
Knowledge Manager - Interface with SRM for persistent WoW knowledge
===================================================================

This module manages Cardinal's learned knowledge about WoW systems:
- Stores analyzed spell data
- Tracks successful backport patterns
- Records failed approaches
- Maintains a knowledge graph of WoW mechanics

Integrates with the Akashic SRM (Semantic Relational Memory) system.
"""

import json
import hashlib
import asyncio
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
from enum import Enum


# =============================================================================
# KNOWLEDGE CATEGORIES
# =============================================================================

class KnowledgeCategory(Enum):
    """Categories of WoW knowledge"""
    SPELL = "spell"
    TALENT = "talent"
    CLASS = "class"
    MECHANIC = "mechanic"
    MODEL = "model"
    ANIMATION = "animation"
    BACKPORT_PATTERN = "backport_pattern"
    BACKPORT_FAILURE = "backport_failure"
    ENGINE_LIMITATION = "engine_limitation"
    WORKAROUND = "workaround"


@dataclass
class KnowledgeEntry:
    """A single piece of learned knowledge"""
    id: str
    category: str
    name: str
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 to 1.0
    source: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    related_entries: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "KnowledgeEntry":
        return KnowledgeEntry(**d)


@dataclass
class BackportPattern:
    """A proven pattern for backporting a mechanic"""
    id: str
    name: str
    retail_mechanic: str
    wotlk_equivalent: str
    implementation_type: str  # "eluna", "sql", "dbc", "hybrid"
    code_template: str
    success_count: int = 0
    failure_count: int = 0
    notes: str = ""
    examples: List[int] = field(default_factory=list)  # Spell IDs

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# SRM INTEGRATION
# =============================================================================

class SRMBridge:
    """
    Bridge to the Akashic SRM memory system.

    Provides read/write access to the Cardinal knowledge cluster.
    """

    def __init__(self, srm_root: Optional[Path] = None):
        """
        Initialize SRM bridge.

        Args:
            srm_root: Root path to SRM storage (auto-detected if None)
        """
        if srm_root:
            self.srm_root = Path(srm_root)
        else:
            # Auto-detect SRM root
            import os
            akashic_root = os.getenv("AKASHIC_ROOT", ".")
            self.srm_root = Path(akashic_root) / "P10_Memory" / "Akashic_triple_helix_memory_storage"

        self.cardinal_cluster = self.srm_root / "relational_clusters" / "Cardinal"
        self._ensure_cluster()

    def _ensure_cluster(self):
        """Ensure Cardinal cluster directories exist."""
        subdirs = [
            "spells",
            "talents",
            "classes",
            "mechanics",
            "patterns",
            "failures",
            "models",
        ]
        for subdir in subdirs:
            (self.cardinal_cluster / subdir).mkdir(parents=True, exist_ok=True)

        # Create cluster index if it doesn't exist
        index_path = self.cardinal_cluster / "index.json"
        if not index_path.exists():
            index_data = {
                "source": "cardinal_wow_knowledge",
                "created_at": datetime.now().isoformat(),
                "categories": subdirs,
                "cards": [],
            }
            index_path.write_text(json.dumps(index_data, indent=2))

    def _get_index(self, category: str) -> Dict:
        """Get index for a category."""
        index_path = self.cardinal_cluster / category / "index.json"
        if index_path.exists():
            return json.loads(index_path.read_text())
        return {"cards": []}

    def _save_index(self, category: str, index_data: Dict):
        """Save index for a category."""
        index_path = self.cardinal_cluster / category / "index.json"
        index_path.write_text(json.dumps(index_data, indent=2))

    def store(self, entry: KnowledgeEntry) -> bool:
        """Store a knowledge entry."""
        try:
            # Determine category path
            cat_path = self.cardinal_cluster / entry.category
            cat_path.mkdir(parents=True, exist_ok=True)

            # Save entry file
            entry_file = cat_path / f"{entry.id}.json"
            entry.updated_at = datetime.now().timestamp()
            if entry.created_at == 0:
                entry.created_at = entry.updated_at

            entry_file.write_text(json.dumps(entry.to_dict(), indent=2))

            # Update category index
            index = self._get_index(entry.category)
            cards = index.get("cards", [])

            # Remove existing entry if present
            cards = [c for c in cards if c.get("id") != entry.id]

            # Add updated entry
            cards.append({
                "id": entry.id,
                "name": entry.name,
                "description": entry.description[:200],
                "tags": entry.tags,
                "confidence": entry.confidence,
                "updated_at": entry.updated_at,
            })

            index["cards"] = cards
            index["updated_at"] = entry.updated_at
            self._save_index(entry.category, index)

            return True
        except Exception as e:
            print(f"[SRMBridge] Store error: {e}")
            return False

    def retrieve(self, category: str, entry_id: str) -> Optional[KnowledgeEntry]:
        """Retrieve a specific knowledge entry."""
        entry_file = self.cardinal_cluster / category / f"{entry_id}.json"
        if not entry_file.exists():
            return None

        try:
            data = json.loads(entry_file.read_text())
            return KnowledgeEntry.from_dict(data)
        except Exception:
            return None

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[KnowledgeEntry]:
        """
        Search knowledge base.

        Args:
            query: Search terms
            category: Limit to specific category (None = all)
            limit: Max results
        """
        results = []
        terms = query.lower().split()

        categories = [category] if category else [
            "spells", "talents", "classes", "mechanics", "patterns", "failures"
        ]

        for cat in categories:
            index = self._get_index(cat)
            for card in index.get("cards", []):
                # Score based on matches
                score = 0.0
                text = f"{card.get('name', '')} {card.get('description', '')}".lower()
                tags = [t.lower() for t in card.get("tags", [])]

                for term in terms:
                    if term in text:
                        score += 1.0
                    if term in tags:
                        score += 2.0

                if score > 0:
                    # Load full entry
                    entry = self.retrieve(cat, card["id"])
                    if entry:
                        entry.confidence = score  # Repurpose as search score
                        results.append(entry)

        # Sort by score and limit
        results.sort(key=lambda e: e.confidence, reverse=True)
        return results[:limit]

    def list_category(self, category: str) -> List[Dict]:
        """List all entries in a category."""
        index = self._get_index(category)
        return index.get("cards", [])

    def get_patterns(self, mechanic_type: Optional[str] = None) -> List[BackportPattern]:
        """Get backport patterns."""
        patterns = []
        pattern_dir = self.cardinal_cluster / "patterns"

        for pattern_file in pattern_dir.glob("*.json"):
            if pattern_file.name == "index.json":
                continue
            try:
                data = json.loads(pattern_file.read_text())
                pattern = BackportPattern(**data)
                if mechanic_type is None or pattern.retail_mechanic == mechanic_type:
                    patterns.append(pattern)
            except Exception:
                continue

        return patterns

    def store_pattern(self, pattern: BackportPattern) -> bool:
        """Store a backport pattern."""
        try:
            pattern_file = self.cardinal_cluster / "patterns" / f"{pattern.id}.json"
            pattern_file.write_text(json.dumps(pattern.to_dict(), indent=2))

            # Update index
            index = self._get_index("patterns")
            cards = index.get("cards", [])
            cards = [c for c in cards if c.get("id") != pattern.id]
            cards.append({
                "id": pattern.id,
                "name": pattern.name,
                "retail_mechanic": pattern.retail_mechanic,
                "implementation_type": pattern.implementation_type,
                "success_count": pattern.success_count,
            })
            index["cards"] = cards
            self._save_index("patterns", index)

            return True
        except Exception as e:
            print(f"[SRMBridge] Pattern store error: {e}")
            return False


# =============================================================================
# KNOWLEDGE MANAGER
# =============================================================================

class KnowledgeManager:
    """
    High-level interface for managing Cardinal's WoW knowledge.

    Provides semantic operations on top of raw SRM storage:
    - Learn from successful backports
    - Recall relevant knowledge for new tasks
    - Track patterns and anti-patterns
    - Query knowledge in natural language
    """

    def __init__(
        self,
        srm_root: Optional[Path] = None,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "mistral",
    ):
        """
        Initialize knowledge manager.

        Args:
            srm_root: SRM storage root
            ollama_url: Ollama server URL
            ollama_model: Model to use for semantic operations
        """
        self.srm = SRMBridge(srm_root)
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model

    # =========================================================================
    # SPELL KNOWLEDGE
    # =========================================================================

    def store_spell_knowledge(
        self,
        spell_id: int,
        name: str,
        version: str,
        data: Dict[str, Any],
        analysis: Optional[Dict] = None,
    ) -> KnowledgeEntry:
        """
        Store knowledge about a spell.

        Args:
            spell_id: WoW spell ID
            name: Spell name
            version: "retail" or "3.3.5a"
            data: Spell data dict
            analysis: Optional analysis results
        """
        entry_id = f"spell_{version}_{spell_id}"

        entry = KnowledgeEntry(
            id=entry_id,
            category="spells",
            name=f"{name} ({version})",
            description=data.get("description", "")[:500],
            data={
                "spell_id": spell_id,
                "version": version,
                "spell_data": data,
                "analysis": analysis,
            },
            tags=self._extract_spell_tags(data, analysis),
            confidence=0.9 if version == "3.3.5a" else 0.7,
            source="dbc" if version == "3.3.5a" else "wowhead",
        )

        self.srm.store(entry)
        return entry

    def _extract_spell_tags(
        self,
        data: Dict,
        analysis: Optional[Dict],
    ) -> List[str]:
        """Extract tags from spell data."""
        tags = []

        # Add school tags
        school = data.get("school_name", "")
        if school:
            tags.append(school.lower())

        # Add effect type tags
        for effect in data.get("effects", []):
            effect_type = effect.get("effect_type_name", "")
            if effect_type:
                tags.append(effect_type.lower())

        # Add analysis tags
        if analysis:
            if analysis.get("can_backport"):
                tags.append("backportable")
            else:
                tags.append("not-backportable")
            tags.append(f"difficulty-{analysis.get('backport_difficulty', 'unknown')}")

        return list(set(tags))

    def get_spell_knowledge(
        self,
        spell_id: int,
        version: str = "3.3.5a",
    ) -> Optional[KnowledgeEntry]:
        """Get stored knowledge about a spell."""
        entry_id = f"spell_{version}_{spell_id}"
        return self.srm.retrieve("spells", entry_id)

    def find_similar_spells(self, spell_name: str) -> List[KnowledgeEntry]:
        """Find spells with similar names or mechanics."""
        return self.srm.search(spell_name, category="spells")

    # =========================================================================
    # BACKPORT PATTERNS
    # =========================================================================

    def record_successful_backport(
        self,
        retail_spell_id: int,
        wotlk_implementation: Dict[str, Any],
        mechanic_type: str,
        code: str,
        implementation_type: str = "eluna",
    ) -> BackportPattern:
        """
        Record a successful backport as a reusable pattern.

        Args:
            retail_spell_id: The retail spell that was backported
            wotlk_implementation: Details of the 3.3.5a implementation
            mechanic_type: Type of mechanic (damage, healing, cc, etc.)
            code: The implementation code
            implementation_type: "eluna", "sql", "dbc", or "hybrid"
        """
        pattern_id = f"pattern_{mechanic_type}_{hashlib.md5(code.encode()).hexdigest()[:8]}"

        # Check if pattern already exists
        existing = [p for p in self.srm.get_patterns() if p.id == pattern_id]

        if existing:
            pattern = existing[0]
            pattern.success_count += 1
            if retail_spell_id not in pattern.examples:
                pattern.examples.append(retail_spell_id)
        else:
            pattern = BackportPattern(
                id=pattern_id,
                name=f"{mechanic_type.title()} Backport Pattern",
                retail_mechanic=mechanic_type,
                wotlk_equivalent=wotlk_implementation.get("effect_type", "SCRIPT_EFFECT"),
                implementation_type=implementation_type,
                code_template=code,
                success_count=1,
                examples=[retail_spell_id],
            )

        self.srm.store_pattern(pattern)
        return pattern

    def record_failed_backport(
        self,
        retail_spell_id: int,
        attempted_approach: str,
        failure_reason: str,
        mechanic_type: str,
    ) -> KnowledgeEntry:
        """
        Record a failed backport attempt to avoid repeating mistakes.

        Args:
            retail_spell_id: The retail spell that failed
            attempted_approach: What was tried
            failure_reason: Why it failed
            mechanic_type: Type of mechanic attempted
        """
        failure_id = f"failure_{retail_spell_id}_{hashlib.md5(attempted_approach.encode()).hexdigest()[:8]}"

        entry = KnowledgeEntry(
            id=failure_id,
            category="failures",
            name=f"Failed: {mechanic_type} for spell {retail_spell_id}",
            description=f"Approach: {attempted_approach}\nReason: {failure_reason}",
            data={
                "spell_id": retail_spell_id,
                "mechanic_type": mechanic_type,
                "attempted_approach": attempted_approach,
                "failure_reason": failure_reason,
            },
            tags=["failure", mechanic_type, "avoid"],
            confidence=1.0,
            source="experiment",
        )

        self.srm.store(entry)
        return entry

    def get_pattern_for_mechanic(self, mechanic_type: str) -> Optional[BackportPattern]:
        """Get the best pattern for a mechanic type."""
        patterns = self.srm.get_patterns(mechanic_type)
        if not patterns:
            return None

        # Return pattern with highest success rate
        return max(
            patterns,
            key=lambda p: p.success_count / max(p.success_count + p.failure_count, 1)
        )

    def check_known_failures(self, mechanic_type: str) -> List[KnowledgeEntry]:
        """Check for known failure patterns."""
        return self.srm.search(mechanic_type, category="failures")

    # =========================================================================
    # CLASS & TALENT KNOWLEDGE
    # =========================================================================

    def store_class_knowledge(
        self,
        class_id: int,
        class_name: str,
        version: str,
        data: Dict[str, Any],
    ) -> KnowledgeEntry:
        """Store knowledge about a class."""
        entry_id = f"class_{version}_{class_id}"

        entry = KnowledgeEntry(
            id=entry_id,
            category="classes",
            name=f"{class_name} ({version})",
            description=f"WoW {class_name} class data for {version}",
            data={
                "class_id": class_id,
                "class_name": class_name,
                "version": version,
                **data,
            },
            tags=[class_name.lower(), version],
            confidence=0.9,
            source="analysis",
        )

        self.srm.store(entry)
        return entry

    def store_talent_knowledge(
        self,
        talent_id: int,
        talent_name: str,
        class_name: str,
        spec_name: str,
        version: str,
        data: Dict[str, Any],
    ) -> KnowledgeEntry:
        """Store knowledge about a talent."""
        entry_id = f"talent_{version}_{talent_id}"

        entry = KnowledgeEntry(
            id=entry_id,
            category="talents",
            name=f"{talent_name} ({class_name} - {spec_name}, {version})",
            description=data.get("description", "")[:500],
            data={
                "talent_id": talent_id,
                "talent_name": talent_name,
                "class_name": class_name,
                "spec_name": spec_name,
                "version": version,
                **data,
            },
            tags=[class_name.lower(), spec_name.lower(), version],
            confidence=0.8,
            source="analysis",
        )

        self.srm.store(entry)
        return entry

    # =========================================================================
    # SEMANTIC QUERY
    # =========================================================================

    async def query_knowledge(self, question: str) -> Dict[str, Any]:
        """
        Query the knowledge base using natural language.

        Uses Cardinal (Mistral) to interpret the question and find
        relevant knowledge entries.

        Args:
            question: Natural language question

        Returns:
            Dict with answer and supporting knowledge entries
        """
        # First, search for relevant entries
        search_results = self.srm.search(question, limit=10)

        # Build context from search results
        context_parts = []
        for entry in search_results:
            context_parts.append(f"""
**{entry.name}** (Category: {entry.category})
{entry.description}
Data: {json.dumps(entry.data, indent=2)[:500]}
Tags: {', '.join(entry.tags)}
""")

        context = "\n---\n".join(context_parts) if context_parts else "No relevant knowledge found."

        # Ask Cardinal to synthesize an answer
        prompt = f"""You are Cardinal, answering questions about WoW backporting.

## KNOWLEDGE BASE CONTEXT:
{context}

## QUESTION:
{question}

## INSTRUCTIONS:
1. Answer the question using ONLY the knowledge provided
2. If the knowledge is insufficient, say so
3. Reference specific entries when applicable
4. Suggest what additional knowledge would help

Provide a clear, technical answer."""

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3},
                    }
                )

                if response.status_code == 200:
                    answer = response.json().get("response", "Unable to generate answer")
                    return {
                        "question": question,
                        "answer": answer,
                        "sources": [e.id for e in search_results],
                        "source_count": len(search_results),
                    }

        except Exception as e:
            pass

        # Fallback: return search results without synthesis
        return {
            "question": question,
            "answer": "Unable to synthesize answer. See raw search results.",
            "sources": [e.id for e in search_results],
            "search_results": [e.to_dict() for e in search_results[:5]],
        }

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        stats = {
            "categories": {},
            "total_entries": 0,
            "patterns": {
                "count": len(self.srm.get_patterns()),
                "by_mechanic": {},
            },
        }

        for category in ["spells", "talents", "classes", "mechanics", "failures"]:
            entries = self.srm.list_category(category)
            stats["categories"][category] = len(entries)
            stats["total_entries"] += len(entries)

        # Pattern breakdown
        for pattern in self.srm.get_patterns():
            mech = pattern.retail_mechanic
            if mech not in stats["patterns"]["by_mechanic"]:
                stats["patterns"]["by_mechanic"][mech] = 0
            stats["patterns"]["by_mechanic"][mech] += 1

        return stats


# =============================================================================
# STANDALONE TESTING
# =============================================================================

def main():
    """Test the knowledge manager."""
    print("=== Knowledge Manager Test ===")
    print()

    km = KnowledgeManager()

    # Store some test knowledge
    print("Storing test spell knowledge...")
    entry = km.store_spell_knowledge(
        spell_id=116,
        name="Frostbolt",
        version="3.3.5a",
        data={
            "description": "Launches a bolt of frost at the enemy, causing X Frost damage and slowing movement speed by Y% for Z sec.",
            "school_name": "Frost",
            "effects": [{"effect_type_name": "SCHOOL_DAMAGE"}],
        },
        analysis={
            "can_backport": True,
            "backport_difficulty": "trivial",
        },
    )
    print(f"  Stored: {entry.id}")

    # Search
    print()
    print("Searching for 'frost'...")
    results = km.find_similar_spells("frost")
    for r in results:
        print(f"  Found: {r.name} (confidence: {r.confidence})")

    # Stats
    print()
    print("Knowledge base stats:")
    stats = km.get_stats()
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Categories: {stats['categories']}")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
