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
from datetime import datetime
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
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
    
    def __init__(self, storage_path: str = None):
        self.storage_path = Path(storage_path or "P10_Memory/codex")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
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
        """Load existing entries from storage"""
        entries_file = self.storage_path / "entries.json"
        patterns_file = self.storage_path / "patterns.json"
        
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
            except Exception as e:
                print(f"[Codex] Error loading entries: {e}")
        
        if patterns_file.exists():
            try:
                with open(patterns_file, 'r') as f:
                    data = json.load(f)
                    for p in data:
                        p['pattern_type'] = PatternType(p['pattern_type'])
                        pattern = Pattern(**p)
                        self.patterns[pattern.id] = pattern
            except Exception as e:
                print(f"[Codex] Error loading patterns: {e}")
    
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


# Export
__all__ = [
    'AkashicCodex',
    'CodexEntry',
    'Pattern',
    'OutcomeType',
    'PatternType',
    'get_codex',
    'add_codex_routes'
]
