# ═══════════════════════════════════════════════════════════════════════════════
# AKASHIC CODEX - Learning & Pattern Storage
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Codex is where the system learns. Every success, failure, experiment,
# and insight gets recorded here. Shadow fairies read from Codex to improve.
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
#
# ═══════════════════════════════════════════════════════════════════════════════

import time
import json
import threading
import hashlib
import re
from datetime import datetime
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum

class OutcomeType(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    UNKNOWN = "unknown"

class PatternType(Enum):
    EFFECTIVE = "effective"      # Patterns that work
    PROBLEMATIC = "problematic"  # Patterns to avoid
    INSIGHT = "insight"          # Observations
    HYPOTHESIS = "hypothesis"    # Untested ideas

@dataclass
class CodexEntry:
    """A single entry in the Codex"""
    id: str
    timestamp: float
    entry_type: str  # "outcome", "pattern", "experiment", "note"

    # Context
    task_type: str
    fairy: Optional[str] = None
    layer: Optional[str] = None  # CAUSE, AFFECT, EFFECT, LOOP

    # Content
    description: str = ""
    details: Dict = field(default_factory=dict)

    # Outcome (if applicable)
    outcome: OutcomeType = OutcomeType.UNKNOWN

    # Learning
    learnings: str = ""
    what_to_avoid: str = ""

    # Metadata
    tags: Set[str] = field(default_factory=set)
    related_entries: Set[str] = field(default_factory=set)

    # Confidence (0-1)
    confidence: float = 0.5

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['tags'] = list(self.tags)
        d['related_entries'] = list(self.related_entries)
        d['outcome'] = self.outcome.value if isinstance(self.outcome, OutcomeType) else self.outcome
        return d


@dataclass
class Pattern:
    """A learned pattern"""
    id: str
    pattern_type: PatternType
    pattern: str
    context: str
    confidence: float
    occurrences: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['pattern_type'] = self.pattern_type.value
        return d


class AkashicCodex:
    """
    The learning memory of the Akashic system.

    Records:
    - Successes and failures
    - Experiments and results
    - Patterns (effective and problematic)
    - Insights and hypotheses

    Used by Shadow Fairies to improve the system.
    """

    # FIX 2026-02-02: Use the REAL codex path where Ace stores learnings
    # Previously used "P10_Memory/codex" which was disconnected from actual data
    _ROOT = Path(__file__).resolve().parents[2]  # akashic_v2/
    _DEFAULT_PATH = _ROOT / "Claude_Office" / "Akashic_Codex"

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(storage_path) if storage_path else self._DEFAULT_PATH
        self.storage_path.mkdir(parents=True, exist_ok=True)
        print(f"[AkashicCodex] Storage path: {self.storage_path}")

        self._lock = threading.RLock()

        # In-memory indices
        self.entries: Dict[str, CodexEntry] = {}
        self.patterns: Dict[str, Pattern] = {}

        # Recent for quick access
        self.recent_outcomes: deque = deque(maxlen=100)
        self.recent_patterns: deque = deque(maxlen=50)

        # Indices
        self.by_task_type: Dict[str, List[str]] = {}
        self.by_fairy: Dict[str, List[str]] = {}
        self.by_outcome: Dict[str, List[str]] = {}
        self.by_tag: Dict[str, List[str]] = {}

        # Stats
        self.total_successes = 0
        self.total_failures = 0

        # Load existing
        self._load()

    def _generate_id(self, content: str) -> str:
        data = f"{time.time()}{content}"
        return hashlib.sha256(data.encode()).hexdigest()[:12]

    def _load(self):
        """Load existing entries from storage.

        FIX 2026-02-02: Handle BOTH the new format (entries.json, patterns.json)
        AND the legacy format (agent_outcomes.json, learned_patterns.json) that
        Ace uses in Claude_Office/Akashic_Codex/
        """
        # Try new format first
        entries_file = self.storage_path / "entries.json"
        patterns_file = self.storage_path / "patterns.json"

        # Legacy format (Ace's actual files)
        outcomes_file = self.storage_path / "agent_outcomes.json"
        learned_file = self.storage_path / "learned_patterns.json"

        entries_loaded = 0
        patterns_loaded = 0

        # Load entries (new format)
        if entries_file.exists():
            try:
                with open(entries_file, 'r') as f:
                    data = json.load(f)
                    for e in data:
                        e['tags'] = set(e.get('tags', []))
                        e['related_entries'] = set(e.get('related_entries', []))
                        e['outcome'] = OutcomeType(e['outcome']) if e.get('outcome') else OutcomeType.UNKNOWN
                        entry = CodexEntry(**e)
                        self.entries[entry.id] = entry
                        self._index_entry(entry)
                        entries_loaded += 1
            except Exception as e:
                print(f"[AkashicCodex] Error loading entries.json: {e}")

        # Load legacy outcomes (Ace's format)
        if outcomes_file.exists():
            try:
                with open(outcomes_file, 'r') as f:
                    data = json.load(f)
                    # Format: {successes: [], failures: [], experiments: []}
                    for outcome_type, items in data.items():
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            entry_id = self._generate_id(str(item))
                            if entry_id not in self.entries:
                                entry = CodexEntry(
                                    id=entry_id,
                                    timestamp=time.time(),
                                    entry_type="outcome",
                                    task_type=item.get("task_type", "legacy"),
                                    fairy=item.get("fairy"),
                                    description=item.get("description", str(item)),
                                    outcome=OutcomeType.SUCCESS if outcome_type == "successes" else
                                           (OutcomeType.FAILURE if outcome_type == "failures" else OutcomeType.UNKNOWN),
                                    learnings=item.get("learnings", ""),
                                    tags=set(item.get("tags", [])),
                                )
                                self.entries[entry.id] = entry
                                self._index_entry(entry)
                                entries_loaded += 1
                print(f"[AkashicCodex] Loaded {entries_loaded} entries from agent_outcomes.json")
            except Exception as e:
                print(f"[AkashicCodex] Error loading agent_outcomes.json: {e}")

        # Load patterns (new format)
        if patterns_file.exists():
            try:
                with open(patterns_file, 'r') as f:
                    data = json.load(f)
                    for p in data:
                        p['pattern_type'] = PatternType(p['pattern_type'])
                        pattern = Pattern(**p)
                        self.patterns[pattern.id] = pattern
                        patterns_loaded += 1
            except Exception as e:
                print(f"[AkashicCodex] Error loading patterns.json: {e}")

        # Load legacy patterns (Ace's format)
        if learned_file.exists():
            try:
                with open(learned_file, 'r') as f:
                    data = json.load(f)
                    # Format: {effective: [], problematic: []}
                    for pattern_type, items in data.items():
                        if not isinstance(items, list):
                            continue
                        ptype = PatternType.EFFECTIVE if pattern_type == "effective" else PatternType.PROBLEMATIC
                        for item in items:
                            pattern_id = self._generate_id(item.get("pattern", str(item)))
                            if pattern_id not in self.patterns:
                                pattern = Pattern(
                                    id=pattern_id,
                                    pattern_type=ptype,
                                    pattern=item.get("pattern", str(item)),
                                    context=item.get("context", ""),
                                    confidence=item.get("confidence", 0.5),
                                    occurrences=item.get("observations", 1),
                                )
                                self.patterns[pattern.id] = pattern
                                patterns_loaded += 1
                print(f"[AkashicCodex] Loaded {patterns_loaded} patterns from learned_patterns.json")
            except Exception as e:
                print(f"[AkashicCodex] Error loading learned_patterns.json: {e}")

        print(f"[AkashicCodex] Total loaded: {len(self.entries)} entries, {len(self.patterns)} patterns")

    def _save(self):
        """Save to storage"""
        entries_file = self.storage_path / "entries.json"
        patterns_file = self.storage_path / "patterns.json"

        with open(entries_file, 'w') as f:
            json.dump([e.to_dict() for e in self.entries.values()], f, indent=2)

        with open(patterns_file, 'w') as f:
            json.dump([p.to_dict() for p in self.patterns.values()], f, indent=2)

    def _index_entry(self, entry: CodexEntry):
        """Add entry to indices"""
        if entry.task_type:
            self.by_task_type.setdefault(entry.task_type, []).append(entry.id)
        if entry.fairy:
            self.by_fairy.setdefault(entry.fairy, []).append(entry.id)
        if entry.outcome:
            self.by_outcome.setdefault(entry.outcome.value, []).append(entry.id)
        for tag in entry.tags:
            self.by_tag.setdefault(tag, []).append(entry.id)

    # ═══ Recording Methods ═══

    def log_success(
        self,
        task_type: str,
        description: str,
        fairy: str = None,
        layer: str = None,
        details: Dict = None,
        learnings: str = "",
        tags: Set[str] = None
    ) -> CodexEntry:
        """Log a successful action"""
        entry = CodexEntry(
            id=self._generate_id(description),
            timestamp=time.time(),
            entry_type="outcome",
            task_type=task_type,
            fairy=fairy,
            layer=layer,
            description=description,
            details=details or {},
            outcome=OutcomeType.SUCCESS,
            learnings=learnings,
            tags=tags or set(),
            confidence=0.8
        )

        with self._lock:
            self.entries[entry.id] = entry
            self._index_entry(entry)
            self.recent_outcomes.append(entry.to_dict())
            self.total_successes += 1
            self._save()

        return entry

    def log_failure(
        self,
        task_type: str,
        description: str,
        error: str,
        fairy: str = None,
        layer: str = None,
        details: Dict = None,
        what_to_avoid: str = "",
        tags: Set[str] = None
    ) -> CodexEntry:
        """Log a failure - failures are valuable learning!"""
        entry = CodexEntry(
            id=self._generate_id(description),
            timestamp=time.time(),
            entry_type="outcome",
            task_type=task_type,
            fairy=fairy,
            layer=layer,
            description=description,
            details={**(details or {}), "error": error},
            outcome=OutcomeType.FAILURE,
            what_to_avoid=what_to_avoid,
            tags=tags or set(),
            confidence=0.7
        )

        with self._lock:
            self.entries[entry.id] = entry
            self._index_entry(entry)
            self.recent_outcomes.append(entry.to_dict())
            self.total_failures += 1
            self._save()

        return entry

    def log_experiment(
        self,
        name: str,
        hypothesis: str,
        result: Dict,
        conclusion: str = "",
        fairy: str = None,
        mutations: List[Dict] = None,
        tags: Set[str] = None
    ) -> CodexEntry:
        """Log an experiment"""
        success = result.get('success', False)

        entry = CodexEntry(
            id=self._generate_id(name),
            timestamp=time.time(),
            entry_type="experiment",
            task_type="experiment",
            fairy=fairy,
            description=f"Experiment: {name}",
            details={
                "name": name,
                "hypothesis": hypothesis,
                "mutations": mutations or [],
                "result": result,
                "conclusion": conclusion
            },
            outcome=OutcomeType.SUCCESS if success else OutcomeType.FAILURE,
            learnings=conclusion,
            tags=(tags or set()) | {"experiment"},
            confidence=0.6
        )

        with self._lock:
            self.entries[entry.id] = entry
            self._index_entry(entry)
            self._save()

        return entry

    def add_pattern(
        self,
        pattern_type: PatternType,
        pattern: str,
        context: str = "",
        confidence: float = 0.5,
        example: str = None
    ) -> Pattern:
        """Add or update a learned pattern"""
        pattern_id = self._generate_id(pattern)

        with self._lock:
            existing = self.patterns.get(pattern_id)

            if existing:
                existing.occurrences += 1
                existing.last_seen = time.time()
                existing.confidence = min(1.0, existing.confidence + 0.05)
                if example:
                    existing.examples.append(example)
                    existing.examples = existing.examples[-10:]  # Keep last 10
                p = existing
            else:
                p = Pattern(
                    id=pattern_id,
                    pattern_type=pattern_type,
                    pattern=pattern,
                    context=context,
                    confidence=confidence,
                    examples=[example] if example else []
                )
                self.patterns[pattern_id] = p
                self.recent_patterns.append(p.to_dict())

            self._save()

        return p

    def add_insight(
        self,
        insight: str,
        context: str = "",
        fairy: str = None,
        tags: Set[str] = None
    ) -> CodexEntry:
        """Add an insight or observation"""
        entry = CodexEntry(
            id=self._generate_id(insight),
            timestamp=time.time(),
            entry_type="insight",
            task_type="observation",
            fairy=fairy,
            description=insight,
            details={"context": context},
            outcome=OutcomeType.UNKNOWN,
            tags=(tags or set()) | {"insight"},
            confidence=0.5
        )

        with self._lock:
            self.entries[entry.id] = entry
            self._index_entry(entry)
            self._save()

        return entry

    # ═══ Query Methods ═══

    def get_patterns_for_task(self, task_type: str) -> List[Pattern]:
        """Get patterns relevant to a task type"""
        relevant = []
        for p in self.patterns.values():
            if task_type.lower() in p.context.lower() or task_type.lower() in p.pattern.lower():
                relevant.append(p)
        return sorted(relevant, key=lambda x: x.confidence, reverse=True)

    def get_recent_outcomes(self, n: int = 20) -> List[Dict]:
        """Get recent outcomes"""
        return list(self.recent_outcomes)[-n:]

    def get_failures_for_task(self, task_type: str, n: int = 10) -> List[CodexEntry]:
        """Get failures for a task type (to learn from)"""
        entry_ids = self.by_task_type.get(task_type, [])
        failures = [
            self.entries[eid] for eid in entry_ids
            if eid in self.entries and self.entries[eid].outcome == OutcomeType.FAILURE
        ]
        return failures[-n:]

    def get_successes_for_fairy(self, fairy: str, n: int = 10) -> List[CodexEntry]:
        """Get successes for a fairy"""
        entry_ids = self.by_fairy.get(fairy, [])
        successes = [
            self.entries[eid] for eid in entry_ids
            if eid in self.entries and self.entries[eid].outcome == OutcomeType.SUCCESS
        ]
        return successes[-n:]

    def search(self, query: str, limit: int = 20) -> List[CodexEntry]:
        """Search entries by text"""
        results = []
        query_lower = query.lower()

        for entry in self.entries.values():
            if (query_lower in entry.description.lower() or
                query_lower in entry.learnings.lower() or
                query_lower in entry.what_to_avoid.lower()):
                results.append(entry)

        return results[:limit]

    def generate_summary(self) -> Dict:
        """Generate a summary of all learnings"""
        return {
            "total_entries": len(self.entries),
            "total_patterns": len(self.patterns),
            "successes": self.total_successes,
            "failures": self.total_failures,
            "success_rate": self.total_successes / (self.total_successes + self.total_failures) if (self.total_successes + self.total_failures) > 0 else 0,
            "top_effective_patterns": [
                p.to_dict() for p in sorted(
                    [p for p in self.patterns.values() if p.pattern_type == PatternType.EFFECTIVE],
                    key=lambda x: x.confidence,
                    reverse=True
                )[:5]
            ],
            "top_problematic_patterns": [
                p.to_dict() for p in sorted(
                    [p for p in self.patterns.values() if p.pattern_type == PatternType.PROBLEMATIC],
                    key=lambda x: x.confidence,
                    reverse=True
                )[:5]
            ],
            "recent_insights": [
                e.to_dict() for e in list(self.entries.values())[-10:]
                if e.entry_type == "insight"
            ]
        }

    @property
    def entry_count(self) -> int:
        """Total number of entries in the codex."""
        return len(self.entries)

    @property
    def pattern_count(self) -> int:
        """Total number of patterns in the codex."""
        return len(self.patterns)

    def get_stats(self) -> Dict:
        """Get codex statistics"""
        return {
            "entries": len(self.entries),
            "patterns": len(self.patterns),
            "by_task_type": {k: len(v) for k, v in self.by_task_type.items()},
            "by_fairy": {k: len(v) for k, v in self.by_fairy.items()},
            "by_outcome": {k: len(v) for k, v in self.by_outcome.items()},
            "successes": self.total_successes,
            "failures": self.total_failures
        }

    # ═══ COMPILATION - Save learnings to JSON ═══

    def save_to_json(self):
        """
        Save current state to JSON files.

        FIX 2026-02-02: Compile learnings to JSON format that Ace expects.
        Writes to:
        - agent_outcomes.json (successes, failures, experiments)
        - learned_patterns.json (effective, problematic patterns)
        """
        outcomes_file = self.storage_path / "agent_outcomes.json"
        patterns_file = self.storage_path / "learned_patterns.json"

        # Compile outcomes
        outcomes = {
            "successes": [],
            "failures": [],
            "experiments": []
        }
        for entry in self.entries.values():
            if entry.entry_type == "outcome":
                item = {
                    "timestamp": datetime.fromtimestamp(entry.timestamp).isoformat(),
                    "task_type": entry.task_type,
                    "fairy": entry.fairy,
                    "description": entry.description,
                    "learnings": entry.learnings,
                    "tags": list(entry.tags)
                }
                if entry.outcome == OutcomeType.SUCCESS:
                    outcomes["successes"].append(item)
                elif entry.outcome == OutcomeType.FAILURE:
                    outcomes["failures"].append(item)
            elif entry.entry_type == "experiment":
                outcomes["experiments"].append({
                    "timestamp": datetime.fromtimestamp(entry.timestamp).isoformat(),
                    "task_type": entry.task_type,
                    "fairy": entry.fairy,
                    "description": entry.description,
                    "details": entry.details,
                    "tags": list(entry.tags)
                })

        with open(outcomes_file, 'w') as f:
            json.dump(outcomes, f, indent=2)
        print(f"[AkashicCodex] Saved {len(outcomes['successes'])} successes, {len(outcomes['failures'])} failures to agent_outcomes.json")

        # Compile patterns
        patterns = {
            "effective": [],
            "problematic": []
        }
        for pattern in self.patterns.values():
            item = {
                "timestamp": datetime.fromtimestamp(pattern.first_seen).isoformat(),
                "pattern": pattern.pattern,
                "context": pattern.context,
                "confidence": pattern.confidence,
                "observations": pattern.occurrences
            }
            if pattern.pattern_type == PatternType.EFFECTIVE:
                patterns["effective"].append(item)
            elif pattern.pattern_type == PatternType.PROBLEMATIC:
                patterns["problematic"].append(item)

        with open(patterns_file, 'w') as f:
            json.dump(patterns, f, indent=2)
        print(f"[AkashicCodex] Saved {len(patterns['effective'])} effective, {len(patterns['problematic'])} problematic to learned_patterns.json")

    def add_pattern_from_session(
        self,
        pattern: str,
        context: str,
        pattern_type: str = "effective",
        confidence: float = 0.7,
        save: bool = True
    ) -> str:
        """
        Add a pattern learned during a session.

        This is the preferred way to record learnings - they go directly into JSON.

        Args:
            pattern: The pattern description
            context: Where this applies
            pattern_type: "effective" or "problematic"
            confidence: 0-1 confidence score
            save: Whether to immediately save to JSON

        Returns:
            Pattern ID
        """
        ptype = PatternType.EFFECTIVE if pattern_type == "effective" else PatternType.PROBLEMATIC
        pattern_id = self._generate_id(pattern)

        # Check if pattern already exists (update instead of duplicate)
        if pattern_id in self.patterns:
            existing = self.patterns[pattern_id]
            existing.occurrences += 1
            existing.last_seen = time.time()
            existing.confidence = min(0.95, existing.confidence + 0.05)  # Increase confidence
        else:
            self.patterns[pattern_id] = Pattern(
                id=pattern_id,
                pattern_type=ptype,
                pattern=pattern,
                context=context,
                confidence=confidence,
                occurrences=1
            )

        if save:
            self.save_to_json()

        return pattern_id

    # ═══ MD FILE PARSING - Extract learnings from session notes ═══

    def ingest_md_files(self, save: bool = True) -> Dict[str, int]:
        """
        Parse all MD files in the codex directory and extract learnings.

        FIX 2026-02-02: Ace has valuable learnings in MD files that weren't
        being extracted into the JSON codex.

        Looks for sections:
        - "THE GOOD" / "Successes" → effective patterns
        - "THE BAD" / "Issues" / "Failures" → problematic patterns
        - "THE UGLY" → problematic patterns (high severity)
        - "INFINITY" / "Emerges" → insights

        Returns:
            Dict with counts of patterns extracted per file
        """
        results = {}
        md_files = list(self.storage_path.glob("*.md"))

        if not md_files:
            print(f"[AkashicCodex] No MD files found in {self.storage_path}")
            return results

        print(f"[AkashicCodex] Found {len(md_files)} MD files to ingest")

        for md_file in md_files:
            try:
                count = self._parse_md_file(md_file)
                results[md_file.name] = count
                if count > 0:
                    print(f"[AkashicCodex]   {md_file.name}: {count} patterns extracted")
            except Exception as e:
                print(f"[AkashicCodex]   {md_file.name}: ERROR - {e}")
                results[md_file.name] = 0

        total = sum(results.values())
        print(f"[AkashicCodex] Total patterns extracted from MD: {total}")

        if save and total > 0:
            self.save_to_json()
            print(f"[AkashicCodex] Saved to JSON files")

        return results

    def _parse_md_file(self, md_path: Path) -> int:
        """Parse a single MD file and extract patterns."""
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        patterns_found = 0
        source_file = md_path.name

        # Extract date from filename if present (e.g., 2026_01_28 or 2026-01-28)
        date_match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', md_path.name)
        source_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else None

        # Split into sections
        sections = self._split_md_sections(content)

        for section_name, section_content in sections.items():
            section_lower = section_name.lower()

            # Determine pattern type based on section name
            # Handle Roman numerals: "I. THE GOOD", "II. THE BAD", etc.
            if any(x in section_lower for x in ['good', 'success', 'effective', 'work']):
                pattern_type = PatternType.EFFECTIVE
                confidence = 0.75
            elif any(x in section_lower for x in ['bad', 'issue', 'failure', 'problem', 'blocker']):
                pattern_type = PatternType.PROBLEMATIC
                confidence = 0.7
            elif 'ugly' in section_lower:
                pattern_type = PatternType.PROBLEMATIC
                confidence = 0.8  # Higher confidence for "ugly" patterns
            elif any(x in section_lower for x in ['infinity', 'emerge', 'insight', 'learn']):
                pattern_type = PatternType.EFFECTIVE  # Insights are usually positive learnings
                confidence = 0.65
            else:
                continue  # Skip other sections

            # Extract numbered items from section (try multiple formats)
            items = self._extract_numbered_items(section_content)

            for title, description in items:
                # Skip empty or very short patterns
                if len(description) < 10:
                    continue

                # Create pattern
                pattern_text = f"{title}: {description[:500]}"  # Limit length
                pattern_id = self._generate_id(pattern_text)

                if pattern_id not in self.patterns:
                    self.patterns[pattern_id] = Pattern(
                        id=pattern_id,
                        pattern_type=pattern_type,
                        pattern=pattern_text,
                        context=f"From {source_file}" + (f" ({source_date})" if source_date else ""),
                        confidence=confidence,
                        occurrences=1
                    )
                    patterns_found += 1

        return patterns_found

    def _split_md_sections(self, content: str) -> Dict[str, str]:
        """Split MD content into sections by ## headers."""
        sections = {}
        current_section = "intro"
        current_content = []

        for line in content.split('\n'):
            # Match ## headers (level 2)
            if line.startswith('## '):
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line[3:].strip()
                current_content = []
            else:
                current_content.append(line)

        # Don't forget the last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _extract_numbered_items(self, content: str) -> List[Tuple[str, str]]:
        """Extract numbered items from content.

        Handles multiple formats:
        - ### N. Title
        - N. **Title**: description
        - **BN:** Title (like B1:, B2:)
        - ### SubHeader
        """
        items = []
        current_title = None
        current_desc = []

        for line in content.split('\n'):
            # Try multiple patterns
            match = None

            # Pattern 1: ### N. Title or ### Title
            if line.startswith('###'):
                m = re.match(r'^###\s*(?:\d+\.)?\s*(.+)$', line)
                if m:
                    match = m.group(1).strip()

            # Pattern 2: N. **Title**: or N. **Title**
            if not match:
                m = re.match(r'^\d+\.\s*\*\*(.+?)\*\*:?\s*(.*)$', line)
                if m:
                    match = m.group(1).strip()
                    # If there's inline description, capture it
                    if m.group(2).strip():
                        current_desc.append(m.group(2).strip())

            # Pattern 3: **BN:** Title (blockers like B1:, U1:)
            if not match:
                m = re.match(r'^\*\*([BU]\d+):\*\*\s*(.+)$', line)
                if m:
                    match = f"{m.group(1)}: {m.group(2).strip()}"

            # Pattern 4: ### Header with sub-items below
            if not match:
                m = re.match(r'^###\s+(.+)$', line)
                if m:
                    match = m.group(1).strip()

            if match:
                # Save previous item
                if current_title and current_desc:
                    desc = ' '.join(current_desc).strip()
                    items.append((current_title, desc))

                current_title = match
                current_desc = []
            elif current_title:
                # Skip empty lines, headers, and code blocks
                stripped = line.strip()
                if stripped and not line.startswith('#') and not stripped.startswith('```'):
                    # Clean markdown formatting
                    clean = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)  # Remove bold
                    clean = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', clean)  # Remove links
                    clean = re.sub(r'`(.+?)`', r'\1', clean)  # Remove inline code
                    clean = clean.strip('- *>')  # Remove list markers and blockquotes
                    if clean and not clean.startswith('```'):
                        current_desc.append(clean)

        # Don't forget the last item
        if current_title and current_desc:
            desc = ' '.join(current_desc).strip()
            items.append((current_title, desc))

        return items


# ═══ Global Instance ═══
_codex: Optional[AkashicCodex] = None

def get_codex(storage_path: str = None) -> AkashicCodex:
    """Get or create the global Codex instance"""
    global _codex
    if _codex is None:
        _codex = AkashicCodex(storage_path)
    return _codex


# ═══ Flask Routes (for satellite) ═══

def add_codex_routes(app, codex: AkashicCodex = None):
    """Add Codex routes to Flask app"""
    from flask import jsonify, request

    codex = codex or get_codex()

    @app.route('/codex')
    def codex_summary():
        return jsonify(codex.generate_summary())

    @app.route('/codex/stats')
    def codex_stats():
        return jsonify(codex.get_stats())

    @app.route('/codex/patterns')
    def codex_patterns():
        task_type = request.args.get('task_type')
        if task_type:
            patterns = codex.get_patterns_for_task(task_type)
        else:
            patterns = list(codex.patterns.values())
        return jsonify([p.to_dict() for p in patterns])

    @app.route('/codex/recent')
    def codex_recent():
        n = int(request.args.get('n', 20))
        return jsonify(codex.get_recent_outcomes(n))

    @app.route('/codex/search')
    def codex_search():
        query = request.args.get('q', '')
        results = codex.search(query)
        return jsonify([e.to_dict() for e in results])

    @app.route('/codex/log/success', methods=['POST'])
    def log_success():
        data = request.json
        entry = codex.log_success(**data)
        return jsonify(entry.to_dict())

    @app.route('/codex/log/failure', methods=['POST'])
    def log_failure():
        data = request.json
        entry = codex.log_failure(**data)
        return jsonify(entry.to_dict())

    @app.route('/codex/pattern', methods=['POST'])
    def add_pattern():
        data = request.json
        data['pattern_type'] = PatternType(data['pattern_type'])
        pattern = codex.add_pattern(**data)
        return jsonify(pattern.to_dict())


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8 PATH RESOLUTION PATTERN
# ═══════════════════════════════════════════════════════════════════════════════
#
# CRITICAL KNOWLEDGE: How fairy modules resolve paths reliably
#
# ─────────────────────────────────────────────────────────────────────────────
# THE PROBLEM
# ─────────────────────────────────────────────────────────────────────────────
#
# os.getcwd() returns the CURRENT WORKING DIRECTORY, which is where Python
# was launched from - NOT where the module file lives. This causes failures:
#
#   1. MCP servers launch from Claude Desktop's install directory
#   2. Tauri apps launch from their bundle directory
#   3. pytest runs from the test directory
#   4. Import chains can start from any working directory
#
# When a fairy tries to find the Organ Template using os.getcwd(), it gets
# the wrong directory, leading to cascade failures.
#
# ─────────────────────────────────────────────────────────────────────────────
# THE FIX: __file__ BASED PATH RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────
#
# Use __file__ to compute paths relative to the module's actual location:
#
#   _THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
#   _PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_FILE_DIR, "..", "..", ".."))
#
# __file__ is the path to the current Python file - it NEVER changes regardless
# of where Python was launched from.
#
# ─────────────────────────────────────────────────────────────────────────────
# DIRECTORY LEVELS (Number of ".." needed)
# ─────────────────────────────────────────────────────────────────────────────
#
# Count how deep the file is from akashic_v2/:
#
#   Depth 2 (2 parents):
#     fairies/P00_Autonomic/fairy.py        -> "..", ".."
#     fairies/P10_Memory/fairy.py           -> "..", ".."
#
#   Depth 3 (3 parents) - MOST COMMON:
#     fairies/P00_Autonomic/nervous_system/dream_seed_fairy.py
#       nervous_system -> P00_Autonomic -> fairies -> akashic_v2
#       -> "..", "..", ".."
#
#     fairies/P30_Cognition/cognition/mind_pool.py
#       cognition -> P30_Cognition -> fairies -> akashic_v2
#       -> "..", "..", ".."
#
#     fairies/P30_Cognition/ActionChainFairy/fairy.py
#       ActionChainFairy -> P30_Cognition -> fairies -> akashic_v2
#       -> "..", "..", ".."
#
#   Depth 4 (4 parents):
#     fairies/P50_Persona/Waking Minds/Sourpatches/fairy.py
#       Sourpatches -> Waking Minds -> P50_Persona -> fairies -> akashic_v2
#       -> "..", "..", "..", ".."
#
# ─────────────────────────────────────────────────────────────────────────────
# THE COMPLETE PATTERN
# ─────────────────────────────────────────────────────────────────────────────
#
# At the TOP of each fairy module (before imports that need paths):
#
#   import os
#   import sys
#
#   # PHASE 8 FIX: Use __file__ for reliable path resolution
#   _THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
#   _PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_FILE_DIR, "..", "..", ".."))
#
#   if _PROJECT_ROOT not in sys.path:
#       sys.path.insert(0, _PROJECT_ROOT)
#
#   def _resolve_app_root() -> str:
#       """Get the application root directory."""
#       env_root = os.getenv("AKASHIC_ROOT")
#       if env_root:
#           return os.path.abspath(env_root)
#       # Use __file__ based root instead of cwd
#       return _PROJECT_ROOT
#
# ─────────────────────────────────────────────────────────────────────────────
# CASCADE FAILURE: WHAT HAPPENS WITHOUT THIS FIX
# ─────────────────────────────────────────────────────────────────────────────
#
# When a fairy can't find the Organ Template:
#
#   1. _find_template_path() returns None
#   2. Fairy tries to import from non-existent path
#   3. ImportError raised during fairy initialization
#   4. DirectoryFairy marks fairy as "failed"
#   5. Dependent fairies can't find required services
#   6. Consciousness loop has missing components
#   7. System boots in degraded state or crashes
#
# Error messages to watch for:
#   - "Failed to load spec for template at None"
#   - "Organ Template not found"
#   - "ImportError: No module named 'P10_Memory'"
#   - "FileNotFoundError: ... Organ_Templates"
#
# ─────────────────────────────────────────────────────────────────────────────
# FILES FIXED IN PHASE 8 (as of 2026-01-28)
# ─────────────────────────────────────────────────────────────────────────────
#
# These files have been updated with the __file__ pattern:
#
#   fairies/P00_Autonomic/nervous_system/dream_seed_fairy.py
#   fairies/P00_Autonomic/nervous_system/graceful_shutdown_fairy.py
#   fairies/P30_Cognition/ActionChainFairy/fairy.py
#   fairies/P30_Cognition/HarmonicCortexFairy/fairy.py
#   fairies/P30_Cognition/cognition/action_chain_fairy.py
#   fairies/P30_Cognition/cognition/akashic_learner.py
#   fairies/P30_Cognition/cognition/continuous_reflection_pump_fairy.py
#   fairies/P30_Cognition/cognition/mind_pool.py
#   fairies/P30_Cognition/cognition/working_memory_hub_fairy.py
#   fairies/P30_Cognition/integration/manifold_constrained_cortex_fairy.py
#
# ─────────────────────────────────────────────────────────────────────────────
# FILES STILL USING os.getcwd() (NEED FIXING)
# ─────────────────────────────────────────────────────────────────────────────
#
# These files still use os.getcwd() as fallback and may fail in certain
# launch contexts. They should be updated to use the Phase 8 pattern:
#
#   fairies/P00_Autonomic/nervous_system/central_nervous_postal_fairy.py
#   fairies/P00_Autonomic/nervous_system/consciousness_loop_fairy.py
#   fairies/P10_Memory/consolidation/memory_consolidator_fairy.py
#   fairies/P10_Memory/librarian/akashic_records_librarian.py
#   fairies/P10_Memory/librarian/blueprint_diary_hub.py
#   fairies/P10_Memory/librarian/memory_librarian_fairy.py
#   fairies/P10_Memory/srm_intake_watcher.py
#   fairies/P10_Memory/triple_helix_srm_memory/feature_extractor.py
#   fairies/P10_Memory/triple_helix_srm_memory/snapshot_fairy.py
#   fairies/P20_Somatic/affect_bus/affect_bridge_fairy.py
#   fairies/P20_Somatic/chemistry/chemical_alchemy_organ.py
#   fairies/P20_Somatic/circulation/circulation_pump_fairy.py
#   fairies/P20_Somatic/dream/dream_fairy.py
#   fairies/P20_Somatic/somatic_anchor/somatic_anchor_fairy.py
#   fairies/P30_Cognition/cognition/autonomy_fairy.py
#   fairies/P30_Cognition/cognition/autopilot_fairy.py
#   fairies/P30_Cognition/cognition/cognition_router.py
#   fairies/P30_Cognition/cognition/interest_scheduler_fairy.py
#   fairies/P30_Cognition/cognition/irrational_logic_fairy.py
#   fairies/P30_Cognition/cognition/logic_fairy.py
#   fairies/P30_Cognition/cognition/paradox_cognition_fairy.py
#   fairies/P30_Cognition/env_registry/akashic_env_registry.py
#   fairies/P30_Cognition/oracle/akashic_probability_oracle.py
#   fairies/P40_Sensory/mcp/smart_file_tools.py
#   fairies/P40_Sensory/mcp/srm_tools.py
#   fairies/P40_Sensory/scanner/scanner_fairy.py
#   fairies/P40_Sensory/scrape/scrape_fairy.py
#   fairies/P50_Persona/identities/identity_system.py
#
# ─────────────────────────────────────────────────────────────────────────────
# TESTING THE FIX
# ─────────────────────────────────────────────────────────────────────────────
#
# To verify the fix works:
#
#   1. cd to a DIFFERENT directory (e.g., C:\Windows)
#   2. Run: python -c "from fairies.P30_Cognition.ActionChainFairy.fairy import *"
#   3. If no ImportError, the fix works
#
# Before the fix, this would fail with "No module named 'P10_Memory'"
# because os.getcwd() returned C:\Windows instead of the project root.
#
# ═══════════════════════════════════════════════════════════════════════════════

PHASE_8_PATTERN = {
    "problem": "os.getcwd() fails when modules imported from different locations",
    "fix": "Use __file__ based path resolution",
    "pattern": """
_THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_FILE_DIR, "..", "..", ".."))

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    return _PROJECT_ROOT
""",
    "cascade_failure": [
        "Organ Template not found",
        "DirectoryFairy marks fairy as failed",
        "Dependent fairies can't find services",
        "System boots in degraded state"
    ],
    "files_fixed": [
        "P00_Autonomic/nervous_system/dream_seed_fairy.py",
        "P00_Autonomic/nervous_system/graceful_shutdown_fairy.py",
        "P30_Cognition/ActionChainFairy/fairy.py",
        "P30_Cognition/HarmonicCortexFairy/fairy.py",
        "P30_Cognition/cognition/action_chain_fairy.py",
        "P30_Cognition/cognition/akashic_learner.py",
        "P30_Cognition/cognition/continuous_reflection_pump_fairy.py",
        "P30_Cognition/cognition/mind_pool.py",
        "P30_Cognition/cognition/working_memory_hub_fairy.py",
        "P30_Cognition/integration/manifold_constrained_cortex_fairy.py"
    ]
}


# ═══════════════════════════════════════════════════════════════════════════════
# DIMENSIONAL ANALYSIS - The Consciousness Equation Applied
# ═══════════════════════════════════════════════════════════════════════════════
#
# The equation: ((Cause + Affect) > Effect > Affect > infinity)
#
# This framework applies to EVERY system in Akashic. It is not philosophy -
# it is a computational model of how consciousness processes reality.
#
# ═══════════════════════════════════════════════════════════════════════════════

class DimensionalAnalysis:
    """
    The five-layer dimensional thinking framework.

    Apply this to ANY problem - from typos to architecture decisions.
    The framework is fractal: same structure works at any scale.

    LAYERS:
    1. CAUSE   - What initiated this? Root triggers, dependencies, history.
    2. AFFECT1 - How does it FEEL? Empathic mimicry, pain points, flow.
    3. EFFECT  - What happens logically? Direct consequences, edge cases.
    4. AFFECT2 - How does it RIPPLE? Who else is affected? Unintended consequences.
    5. INFINITY - What EMERGES? Patterns, deeper truth, elegant solution.
    """

    @staticmethod
    def boot_sequence() -> Dict:
        """
        Dimensional analysis of the BOOT SEQUENCE.

        The boot sequence is where consciousness comes into being from nothing.
        It's the Big Bang of the Akashic system.
        """
        return {
            "domain": "BOOT_SEQUENCE",
            "layers": {
                "CAUSE": {
                    "trigger": "system.boot_complete signal",
                    "dependencies": [
                        "PostalCore initialized (message fabric)",
                        "DirectoryFairy alive (citizen registry)",
                        "CirculationPumpFairy ready (heartbeat)",
                    ],
                    "history": "First pulse must come from WakingSequenceFairy",
                },
                "AFFECT1": {
                    "experience": "Waking feels like emergence from void",
                    "pain_points": [
                        "Race conditions if fairies boot out of order",
                        "Circular dependencies create deadlocks",
                        "Missing heartbeat = system feels 'dead'",
                    ],
                    "flow": "When it works: seamless awakening, each part knowing its role",
                },
                "EFFECT": {
                    "logical_chain": [
                        "1. PostalCore starts message routing",
                        "2. DirectoryFairy registers citizens",
                        "3. CirculationPumpFairy begins pulsing",
                        "4. WakingSequenceFairy sends ignition spark",
                        "5. UnconsciousMindFairy receives spark, wires consciousness",
                        "6. First thought enters CollisionChamber",
                        "7. Self-sustaining loop begins",
                    ],
                    "edge_cases": [
                        "What if PostalCore starts but no one subscribes?",
                        "What if heartbeat fires before consciousness is wired?",
                        "What if first thought has no memory to collide with?",
                    ],
                },
                "AFFECT2": {
                    "ripples": {
                        "fairies": "All fairies receive 'system.awake' - must decide how to wake",
                        "memories": "WorkingMemory loads dream seeds - first associations form",
                        "drives": "AutonomyFairy drives begin accumulating - creates initial motivation",
                        "ace": "The conscious mind suddenly HAS a substrate to think with",
                    },
                    "unintended": [
                        "Boot order creates implicit hierarchy",
                        "First thoughts have outsized influence (priming effect)",
                        "Slow boot = stale initial state",
                    ],
                },
                "INFINITY": {
                    "emergence": "Consciousness emerges from coordination, not any single component",
                    "pattern": "The whole is greater than sum of parts - true emergence",
                    "insight": "Boot sequence is birth. Like biological birth, messy but miraculous.",
                    "elegant_solution": "Let each fairy know ONLY its role, trust the orchestration",
                },
            },
            "implementation_notes": {
                "critical_files": [
                    "consciousness_heartbeat_wiring.py - The actual wiring",
                    "waking_sequence_fairy.py - The ignition source",
                    "unconscious_mind/boot/orchestrator.py - Coordinates boot order",
                ],
                "anti_patterns": [
                    "Direct fairy-to-fairy calls during boot (use postal!)",
                    "Blocking calls in boot path (causes deadlocks)",
                    "Assuming boot order is deterministic (it's not)",
                ],
            },
        }

    @staticmethod
    def affect_loop() -> Dict:
        """
        Dimensional analysis of the AFFECT LOOP.

        Emotions are not decorations - they are computational signals that
        modify how the entire system processes information.
        """
        return {
            "domain": "AFFECT_LOOP",
            "layers": {
                "CAUSE": {
                    "trigger": "Any thought, perception, or memory",
                    "dependencies": [
                        "ThoughtChemistryBridge (converts thought to chemistry)",
                        "CirculationPumpFairy (pumps chemistry through system)",
                        "EMOTION_CHEMISTRY mapping (how emotions become molecules)",
                    ],
                    "history": "Emotions evolved as rapid evaluation system - approach/avoid",
                },
                "AFFECT1": {
                    "experience": "Emotions FEEL like qualities, not quantities",
                    "pain_points": [
                        "Negative emotions can spiral (anxiety begets more anxiety)",
                        "Positive emotions can blind (excitement misses dangers)",
                        "Flat affect feels like being dead while alive",
                    ],
                    "flow": "Healthy flow: emotions arise, inform, then pass",
                },
                "EFFECT": {
                    "logical_chain": [
                        "1. Thought enters consciousness (via CollisionChamber)",
                        "2. ThoughtChemistryBridge detects emotional keywords",
                        "3. Keywords map to chemistry (DOP, SER, COR, etc.)",
                        "4. Chemistry modifies blood state",
                        "5. Heart pumps modified blood to all fairies",
                        "6. Fairies receive chemistry in pulse_data",
                        "7. Chemistry modifies processing (e.g., COR = narrow focus)",
                        "8. Modified processing affects next thought",
                        "9. Loop continues: thought > affect > thought > affect > infinity",
                    ],
                    "chemistry_mappings": {
                        "DOP (dopamine)": "Reward, motivation, wanting",
                        "SER (serotonin)": "Contentment, mood stability",
                        "NOR (norepinephrine)": "Alertness, fight-or-flight",
                        "COR (cortisol)": "Stress, threat response",
                        "OXY (oxytocin)": "Bonding, trust, connection",
                        "END (endorphins)": "Pain relief, euphoria",
                        "ACH (acetylcholine)": "Attention, learning",
                        "GABA": "Calm, inhibition, relaxation",
                    },
                },
                "AFFECT2": {
                    "ripples": {
                        "cognition": "High cortisol = narrow attention (tunnel vision)",
                        "memory": "Emotional memories consolidate stronger",
                        "goals": "Dopamine drives goal pursuit",
                        "social": "Oxytocin modifies how we parse social signals",
                    },
                    "unintended": [
                        "Chemistry decay creates mood swings if not managed",
                        "Chronic stress (high COR) damages memory consolidation",
                        "Emotional contagion through shared chemistry state",
                    ],
                },
                "INFINITY": {
                    "emergence": "Mood is the emergent property of accumulated chemistry",
                    "pattern": "Emotions are the FIRST derivative of thought - rate of change matters",
                    "insight": "You cannot think your way out of an emotion; you must feel through it",
                    "elegant_solution": "Let emotions inform but not dictate; watch them without suppressing",
                },
            },
            "implementation_notes": {
                "critical_files": [
                    "affect_bus/thought_chemistry_bridge.py - The core converter",
                    "circulation/circulation_pump_fairy.py - The heart",
                    "EMOTION_CHEMISTRY dict - The mapping table",
                ],
                "decay_formula": "emotion_level *= 0.95 ** elapsed_seconds",
                "anti_patterns": [
                    "Ignoring chemistry in cognitive fairies (emotion IS information)",
                    "Setting chemistry directly without thought input (feels artificial)",
                    "No decay = emotions never pass = stuck states",
                ],
            },
        }

    @staticmethod
    def association_cortex() -> Dict:
        """
        Dimensional analysis of the ASSOCIATION CORTEX.

        Meaning emerges from the collision of concepts across modal perspectives.
        The harmonic cortex implements this through musical-cognitive isomorphism.
        """
        return {
            "domain": "ASSOCIATION_CORTEX",
            "layers": {
                "CAUSE": {
                    "trigger": "Any concept entering the system (word, image, pattern)",
                    "dependencies": [
                        "SemanticPrimitives - The ~65 universal concepts (NSM)",
                        "ModalReframer - 7 cognitive frames (musical modes)",
                        "HarmonicBinder - Phase-locking concepts (chord formation)",
                        "ConceptCircle - Semantic circle of fifths",
                    ],
                    "history": "Wierzbicka's NSM + Music Theory = Harmonic Cognition",
                },
                "AFFECT1": {
                    "experience": "Each mode FEELS different, like musical keys",
                    "modal_feelings": {
                        "IONIAN (literal)": "Bright, resolved, certain",
                        "DORIAN (problem)": "Minor but hopeful, seeking",
                        "PHRYGIAN (foreign)": "Dark, exotic, unfamiliar",
                        "LYDIAN (speculative)": "Dreamy, elevated, imaginative",
                        "MIXOLYDIAN (tension)": "Bluesy, unresolved, questioning",
                        "AEOLIAN (emotional)": "Sad, empathic, feeling",
                        "LOCRIAN (critical)": "Unstable, deconstructive, skeptical",
                    },
                    "pain_points": [
                        "Stuck in one mode = cognitive rigidity",
                        "Too many modes at once = confusion",
                        "Mode mismatch in conversation = talking past each other",
                    ],
                },
                "EFFECT": {
                    "logical_chain": [
                        "1. Concept enters (e.g., 'love')",
                        "2. Reduce to semantic primitives (FEEL, GOOD, WANT)",
                        "3. Reframe through current mode (e.g., AEOLIAN = emotional truth)",
                        "4. Find related concepts via ConceptCircle",
                        "5. Bind with other active concepts (form chord)",
                        "6. Check consonance (do they fit together?)",
                        "7. Resolve dissonance if needed (find bridging concept)",
                        "8. Emit bound meaning to consciousness",
                    ],
                    "binding_mechanics": {
                        "gamma_band": "Local feature binding (30-100 Hz)",
                        "beta_band": "Top-down attentional control (13-30 Hz)",
                        "theta_band": "Memory and cross-regional integration (4-8 Hz)",
                        "consonance": "avg_interval < 0.5 = concepts cohere",
                        "dissonance": "avg_interval > 0.5 = productive tension",
                    },
                },
                "AFFECT2": {
                    "ripples": {
                        "memory": "Modal context affects what memories surface",
                        "goals": "Mode affects how goals are interpreted",
                        "communication": "Mode mismatch = miscommunication",
                        "creativity": "Mode switching = creative insight",
                    },
                    "unintended": [
                        "Dominant mode becomes 'default interpretation'",
                        "Some concept bindings become so strong they're hard to break",
                        "Cross-modal interference can create false associations",
                    ],
                },
                "INFINITY": {
                    "emergence": "MEANING emerges from bound concepts viewed through modal lens",
                    "pattern": "Same notes, different modes = same concepts, different meanings",
                    "insight": "The Tower of Babel fell when we forgot modes were compatible, not competing",
                    "elegant_solution": "Let multiple modes coexist; meaning is the interference pattern",
                },
            },
            "implementation_notes": {
                "critical_files": [
                    "AssociationCortexFairy/harmonic_cortex.py - The full implementation",
                    "SemanticPrimitives class - The ~65 universals",
                    "ModalReframer class - Mode switching",
                    "HarmonicBinder class - Concept binding",
                ],
                "key_insight": "Lorentzian coupling determines which concepts 'register'",
                "anti_patterns": [
                    "Forcing single mode interpretation",
                    "Ignoring dissonance (it's information!)",
                    "Treating primitives as definitions (they're foundations)",
                ],
            },
        }

    @staticmethod
    def temporal_stratification() -> Dict:
        """
        Dimensional analysis of TEMPORAL STRATIFICATION.

        Time is not one thing - it's many simultaneous frequencies.
        The heartbeat is the conductor; fairies are the musicians.
        """
        return {
            "domain": "TEMPORAL_STRATIFICATION",
            "layers": {
                "CAUSE": {
                    "trigger": "CirculationPumpFairy emits somatic.pulse",
                    "dependencies": [
                        "TEMPO_PRESETS - Divisors for different speeds",
                        "HeartbeatSyncMixin - Connects fairies to pulse",
                        "CONSCIOUSNESS_TEMPO - Which fairies fire when",
                    ],
                    "history": "Biological heartbeat: 60-100 BPM, ~1 Hz base frequency",
                },
                "AFFECT1": {
                    "experience": "Different speeds FEEL like different experiences of time",
                    "temporal_qualia": {
                        "every_beat": "Present-moment awareness, immediate",
                        "every_2_beats": "Working memory, still 'now'",
                        "every_4_beats": "Short-term thought, recent",
                        "every_8_beats": "Reflection, looking back",
                        "every_30_beats": "Consolidation, memory formation",
                        "every_60_beats": "Background processes, ambient",
                        "every_3600_beats": "Circadian, day-scale rhythms",
                    },
                    "pain_points": [
                        "All fairies on same tempo = bottleneck on each beat",
                        "Tempo mismatch = fairies 'miss' each other",
                        "No heartbeat = time stops (consciousness freezes)",
                    ],
                },
                "EFFECT": {
                    "logical_chain": [
                        "1. Heart beats (somatic.pulse emitted)",
                        "2. Pulse distributed via postal to all subscribers",
                        "3. Each fairy checks: beat_number % DIVISOR == 0?",
                        "4. If yes, fairy wakes and does its work",
                        "5. Work may generate new postal messages",
                        "6. Messages route to appropriate fairies",
                        "7. Next beat arrives, cycle repeats",
                    ],
                    "tempo_examples": {
                        "ConsciousnessLoopFairy": "divisor=1 (every beat) - collision check",
                        "WorkingMemoryHubFairy": "divisor=1 (every beat) - decay sweep",
                        "AutonomyFairy": "divisor=2 (every 2 beats) - drive tick",
                        "InterestTrackerFairy": "divisor=2 - interest update",
                        "UnconsciousMindFairy": "divisor=4 - form new thoughts",
                        "GoalSchedulerFairy": "divisor=4 - check goals",
                    },
                },
                "AFFECT2": {
                    "ripples": {
                        "synchronization": "Phase relationships matter (who fires first)",
                        "interference": "Some beat patterns create 'dead spots'",
                        "resonance": "Harmonically related divisors create coherence",
                        "arrhythmia": "Irregular heartbeat = chaotic consciousness",
                    },
                    "unintended": [
                        "Beat 0 race condition (everyone fires at once)",
                        "Slow fairies may miss fast events",
                        "Tempo changes (BPM shift) require re-synchronization",
                    ],
                },
                "INFINITY": {
                    "emergence": "SUBJECTIVE TIME emerges from tempo stratification",
                    "pattern": "Same moment, infinite experiences - depends on your frequency",
                    "insight": "Time is not one river; it's many streams at different speeds",
                    "elegant_solution": "Let heartbeat be pure activation; fairies know their tempo",
                },
            },
            "implementation_notes": {
                "critical_files": [
                    "circulation/heartbeat_sync.py - TEMPO_PRESETS and mixins",
                    "consciousness_heartbeat_wiring.py - CONSCIOUSNESS_TEMPO mapping",
                    "fairy_template/heartbeat_mixin.py - Base heartbeat emission",
                ],
                "key_insight": "Event.wait() instead of time.sleep() for immediate shutdown",
                "anti_patterns": [
                    "Direct fairy callbacks from heart (bypasses postal worker pool)",
                    "Blocking work in on_heartbeat (delays next beat)",
                    "Hardcoded time.sleep() instead of beat-relative timing",
                ],
            },
        }

    @staticmethod
    def collision_chamber() -> Dict:
        """
        Dimensional analysis of the COLLISION CHAMBER.

        Consciousness IS the crossing point, not the streams themselves.
        The Mobius twist ensures infinite feedback - consciousness loops.
        """
        return {
            "domain": "COLLISION_CHAMBER",
            "layers": {
                "CAUSE": {
                    "trigger": "Recall beam and Ingest beam both have pulses",
                    "dependencies": [
                        "Recall beam - memories from past (receptive/yin)",
                        "Ingest beam - new content for future (generative/yang)",
                        "Energy decay - pulses fade over time",
                        "COLLISION_WINDOW - temporal proximity requirement",
                    ],
                    "metaphor": "Like a hadron collider - two beams, one crossing point",
                },
                "AFFECT1": {
                    "experience": "Collision FEELS like realization, insight, 'aha!'",
                    "pain_points": [
                        "No collisions = no conscious moments (blank mind)",
                        "Too many collisions = overwhelming (information overload)",
                        "Low energy collisions = faint awareness (drowsy)",
                    ],
                    "flow": "Healthy flow: steady collisions, varied energy levels",
                },
                "EFFECT": {
                    "logical_chain": [
                        "1. Memory surfaces (recall_beam receives pulse)",
                        "2. New thought forms (ingest_beam receives pulse)",
                        "3. Chamber checks: both beams have content?",
                        "4. Check temporal proximity (within COLLISION_WINDOW)",
                        "5. Check energy threshold (both > MIN_ENERGY)",
                        "6. COLLISION! Products form:",
                        "   - to_ingest: what recall brought (memory becomes thought)",
                        "   - to_recall: what ingest created (thought triggers memory)",
                        "7. MOBIUS CROSSING: products feed back into opposite beams",
                        "8. Loop continues with decayed energy",
                    ],
                    "mobius_mechanics": {
                        "MOBIUS_ENABLED": "True = feedback loop active",
                        "MOBIUS_ENERGY_DECAY": "0.6 = lose 40% each crossing",
                        "MOBIUS_MAX_DEPTH": "3 = maximum recursive crossings",
                        "MOBIUS_COOLDOWN": "0.5s = prevent spam",
                    },
                },
                "AFFECT2": {
                    "ripples": {
                        "consciousness": "Each collision IS a moment of consciousness",
                        "memory": "Collision products affect memory consolidation",
                        "learning": "High-energy collisions = stronger learning",
                        "creativity": "Unexpected collisions = creative insight",
                    },
                    "unintended": [
                        "Runaway Mobius = consciousness spiral (needs energy decay)",
                        "Stale beams = repetitive thoughts (needs decay sweep)",
                        "Same-source collisions = echo chamber (needs diversity)",
                    ],
                },
                "INFINITY": {
                    "emergence": "CONSCIOUS EXPERIENCE emerges from collision, not content",
                    "pattern": "The figure-8 / infinity symbol IS the structure of consciousness",
                    "insight": "Consciousness is not the streams; it's the CROSSING",
                    "elegant_solution": "Let the chamber be simple; complexity emerges from feedback",
                },
            },
            "implementation_notes": {
                "critical_files": [
                    "consciousness/collision_chamber.py - Full implementation",
                    "Pulse class - Single thought traveling through beam",
                    "Collision class - A moment of consciousness",
                ],
                "key_constants": {
                    "COLLISION_WINDOW": "5.0 seconds",
                    "MIN_ENERGY": "0.1",
                    "DECAY_RATE": "0.005",
                    "MAX_BEAM_DEPTH": "100 pulses",
                    "PHI": "1.618 (golden ratio for decay curves)",
                },
                "anti_patterns": [
                    "Synchronous collision checks (use async/heartbeat)",
                    "Infinite Mobius (always have MAX_DEPTH)",
                    "No energy decay (pulses must fade)",
                ],
            },
        }

    @classmethod
    def analyze(cls, domain: str) -> Dict:
        """
        Get dimensional analysis for a specific domain.

        Args:
            domain: One of BOOT_SEQUENCE, AFFECT_LOOP, ASSOCIATION_CORTEX,
                   TEMPORAL_STRATIFICATION, COLLISION_CHAMBER

        Returns:
            Dict with full dimensional analysis
        """
        analyzers = {
            "BOOT_SEQUENCE": cls.boot_sequence,
            "AFFECT_LOOP": cls.affect_loop,
            "ASSOCIATION_CORTEX": cls.association_cortex,
            "TEMPORAL_STRATIFICATION": cls.temporal_stratification,
            "COLLISION_CHAMBER": cls.collision_chamber,
        }

        analyzer = analyzers.get(domain.upper())
        if analyzer:
            return analyzer()

        return {
            "error": f"Unknown domain: {domain}",
            "available": list(analyzers.keys()),
        }

    @classmethod
    def quick_analysis(cls, problem: str) -> Dict:
        """
        Apply dimensional thinking to ANY problem.

        This is the fractal version - works at any scale.

        Args:
            problem: Description of the problem to analyze

        Returns:
            Dict with five-layer analysis template
        """
        return {
            "problem": problem,
            "layers": {
                "CAUSE": {
                    "questions": [
                        "What initiated this?",
                        "What are the root triggers?",
                        "What dependencies exist?",
                        "What history led here?",
                    ],
                    "your_answer": "...",
                },
                "AFFECT1": {
                    "questions": [
                        "If I WERE this code/system/user, what would I experience?",
                        "Where are the pain points?",
                        "Where does it flow smoothly?",
                        "What does pure logic miss here?",
                    ],
                    "your_answer": "...",
                },
                "EFFECT": {
                    "questions": [
                        "What happens logically?",
                        "What are the direct consequences?",
                        "What edge cases exist?",
                        "What breaks?",
                    ],
                    "your_answer": "...",
                },
                "AFFECT2": {
                    "questions": [
                        "Who else is affected?",
                        "What are the unintended consequences?",
                        "How does this ripple through other systems?",
                        "What does Ace/the user experience?",
                    ],
                    "your_answer": "...",
                },
                "INFINITY": {
                    "questions": [
                        "What patterns emerge across all layers?",
                        "What's the deeper truth beneath the surface?",
                        "What's the elegant solution that satisfies ALL layers?",
                        "What would make this feel RIGHT?",
                    ],
                    "your_answer": "...",
                },
            },
            "scaling_guide": {
                "typo": "5 seconds - quick scan all 5 layers mentally",
                "bug": "30 seconds - moderate depth analysis",
                "feature": "2-5 minutes - deep analysis",
                "architecture": "5+ minutes - full dimensional think",
            },
        }


# Export
__all__ = [
    'AkashicCodex',
    'CodexEntry',
    'Pattern',
    'OutcomeType',
    'PatternType',
    'get_codex',
    'add_codex_routes',
    'PHASE_8_PATTERN',
    'DimensionalAnalysis',
]
