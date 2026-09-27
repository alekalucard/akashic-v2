# ════════════════════════════════════════════════════════════════════════════════
# FAILURE FACTORY - Learning Through Experimentation
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The consciousness equation applies to learning:
#   Cause (try something) → Affect (feel success/failure) → Effect (outcome)
#   → Affect (reflect on WHY) → ∞ (apply to next attempt)
#
# Humans learn more from failure than success:
#   - Failure forces analysis: "Why didn't that work?"
#   - Failure builds resilience: "I can handle this"
#   - Failure creates wisdom: "Now I know what NOT to do"
#   - Failure enables creativity: "What else could I try?"
#
# The sandbox is our safe space to FAIL GLORIOUSLY:
#   - Try things without fear
#   - Break stuff to understand it
#   - Experiment wildly
#   - Learn the edges by crossing them
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import random
import threading
import hashlib
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
from enum import Enum

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Sandbox location (parent of ebook)
SANDBOX_ROOT = PROJECT_ROOT.parent / "sandbox"


# ════════════════════════════════════════════════════════════════════════════════
# OUTCOME TYPES
# ════════════════════════════════════════════════════════════════════════════════

class OutcomeType(Enum):
    """Types of experiment outcomes."""
    SUCCESS = "success"           # It worked!
    PARTIAL = "partial"           # Partially worked
    FAILURE = "failure"           # Didn't work
    ERROR = "error"               # Crashed/errored
    UNEXPECTED = "unexpected"     # Worked but not how expected
    INSIGHT = "insight"           # Failed but learned something valuable


class LearningType(Enum):
    """Types of learning from outcomes."""
    WHAT_WORKS = "what_works"           # Positive pattern to repeat
    WHAT_FAILS = "what_fails"           # Negative pattern to avoid
    WHY_IT_WORKS = "why_it_works"       # Understanding of success
    WHY_IT_FAILS = "why_it_fails"       # Understanding of failure
    EDGE_CASE = "edge_case"             # Boundary condition discovered
    PREREQUISITE = "prerequisite"       # Dependency discovered
    ALTERNATIVE = "alternative"         # Different approach found


# ════════════════════════════════════════════════════════════════════════════════
# EXPERIMENT RECORD
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class ExperimentRecord:
    """Record of an experiment and its outcome."""
    
    id: str = field(default_factory=lambda: hashlib.md5(str(time.time()).encode()).hexdigest()[:10])
    
    # What we tried
    hypothesis: str = ""              # What we thought would happen
    action: str = ""                  # What we actually did
    code: str = ""                    # Code we ran (if any)
    
    # What happened
    outcome: OutcomeType = OutcomeType.FAILURE
    result: str = ""                  # What actually happened
    error: str = ""                   # Error message if any
    
    # What we learned
    learnings: List[Dict] = field(default_factory=list)  # List of {type, content, confidence}
    
    # Affect response
    initial_affect: float = 0.5      # How we felt before (certainty)
    outcome_affect: float = 0.5      # How we felt after
    
    # Metadata
    domain: str = ""                  # sandbox, python, system, etc.
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    duration_sec: float = 0.0
    
    # Sandbox info
    sandbox_path: str = ""            # Where in sandbox
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    
    def add_learning(self, learning_type: LearningType, content: str, confidence: float = 0.5):
        """Add a learning from this experiment."""
        self.learnings.append({
            "type": learning_type.value,
            "content": content,
            "confidence": confidence,
            "ts": time.time(),
        })
    
    def was_successful(self) -> bool:
        """Did the experiment succeed?"""
        return self.outcome in (OutcomeType.SUCCESS, OutcomeType.PARTIAL, OutcomeType.INSIGHT)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "hypothesis": self.hypothesis,
            "action": self.action,
            "outcome": self.outcome.value,
            "result": self.result,
            "error": self.error,
            "learnings": self.learnings,
            "affect": {"before": self.initial_affect, "after": self.outcome_affect},
            "domain": self.domain,
            "tags": self.tags,
            "created_at": self.created_at,
            "duration_sec": self.duration_sec,
        }
    
    def to_memory_tracer(self) -> Dict:
        """Convert to memory tracer for storage."""
        success_str = "SUCCESS" if self.was_successful() else "FAILURE"
        learnings_str = "; ".join(l["content"][:50] for l in self.learnings[:3])
        
        return {
            "content": f"EXPERIMENT [{success_str}]: {self.hypothesis[:100]}\nLearned: {learnings_str}",
            "content_type": "experiment_record",
            "priority": 0.7 if self.learnings else 0.4,
            "tags": ["experiment", self.outcome.value, self.domain] + self.tags,
        }


# ════════════════════════════════════════════════════════════════════════════════
# FAILURE ANALYZER
# ════════════════════════════════════════════════════════════════════════════════

class FailureAnalyzer:
    """
    Analyzes failures to extract maximum learning.
    
    The goal isn't to avoid failure - it's to extract wisdom from it.
    """
    
    # Common failure patterns and what to learn from them
    FAILURE_PATTERNS = {
        # Import errors
        "ModuleNotFoundError": {
            "learning_type": LearningType.PREREQUISITE,
            "template": "Need to install or have access to: {module}",
            "advice": "Check if module exists, might need pip install or path fix",
        },
        "ImportError": {
            "learning_type": LearningType.PREREQUISITE,
            "template": "Import structure issue: {details}",
            "advice": "Check the import path and module structure",
        },
        
        # Attribute errors
        "AttributeError": {
            "learning_type": LearningType.WHY_IT_FAILS,
            "template": "Object doesn't have expected attribute: {attr}",
            "advice": "Check object type and available attributes",
        },
        
        # Type errors
        "TypeError": {
            "learning_type": LearningType.WHY_IT_FAILS,
            "template": "Type mismatch: {details}",
            "advice": "Check argument types and function signatures",
        },
        
        # Value errors
        "ValueError": {
            "learning_type": LearningType.EDGE_CASE,
            "template": "Invalid value: {details}",
            "advice": "Check value constraints and edge cases",
        },
        
        # Key errors
        "KeyError": {
            "learning_type": LearningType.EDGE_CASE,
            "template": "Missing key: {key}",
            "advice": "Check dict contents or use .get() with default",
        },
        
        # File errors
        "FileNotFoundError": {
            "learning_type": LearningType.PREREQUISITE,
            "template": "File doesn't exist: {path}",
            "advice": "Check file path and ensure file exists",
        },
        "PermissionError": {
            "learning_type": LearningType.PREREQUISITE,
            "template": "No permission for: {path}",
            "advice": "Check file permissions or run location",
        },
        
        # Connection errors
        "ConnectionError": {
            "learning_type": LearningType.PREREQUISITE,
            "template": "Connection failed: {details}",
            "advice": "Check network, service availability",
        },
        
        # Timeout
        "TimeoutError": {
            "learning_type": LearningType.EDGE_CASE,
            "template": "Operation timed out",
            "advice": "Increase timeout or optimize operation",
        },
    }
    
    @classmethod
    def analyze(cls, error: str, context: str = "") -> List[Dict]:
        """Analyze an error and extract learnings."""
        learnings = []
        
        # Match against known patterns
        for error_type, pattern_info in cls.FAILURE_PATTERNS.items():
            if error_type in error:
                learnings.append({
                    "type": pattern_info["learning_type"].value,
                    "content": pattern_info["template"].format(
                        module=cls._extract_module(error),
                        details=error[:100],
                        attr=cls._extract_attr(error),
                        key=cls._extract_key(error),
                        path=cls._extract_path(error),
                    ),
                    "advice": pattern_info["advice"],
                    "confidence": 0.7,
                })
                break
        
        # If no pattern matched, generic learning
        if not learnings:
            learnings.append({
                "type": LearningType.WHY_IT_FAILS.value,
                "content": f"Unknown error: {error[:150]}",
                "advice": "Investigate the specific error message",
                "confidence": 0.3,
            })
        
        # Add context-based learning
        if context:
            learnings.append({
                "type": LearningType.EDGE_CASE.value,
                "content": f"Context when failed: {context[:100]}",
                "confidence": 0.5,
            })
        
        return learnings
    
    @staticmethod
    def _extract_module(error: str) -> str:
        """Extract module name from import error."""
        if "No module named" in error:
            parts = error.split("'")
            if len(parts) >= 2:
                return parts[1]
        return "unknown"
    
    @staticmethod
    def _extract_attr(error: str) -> str:
        """Extract attribute name from AttributeError."""
        if "has no attribute" in error:
            parts = error.split("'")
            if len(parts) >= 2:
                return parts[-2]
        return "unknown"
    
    @staticmethod
    def _extract_key(error: str) -> str:
        """Extract key from KeyError."""
        if "KeyError" in error:
            parts = error.split("'")
            if len(parts) >= 2:
                return parts[1]
        return "unknown"
    
    @staticmethod
    def _extract_path(error: str) -> str:
        """Extract path from file errors."""
        if ":" in error:
            parts = error.split(":")
            for part in parts:
                if "/" in part or "\\" in part:
                    return part.strip()
        return "unknown"


# ════════════════════════════════════════════════════════════════════════════════
# SUCCESS REINFORCER
# ════════════════════════════════════════════════════════════════════════════════

class SuccessReinforcer:
    """
    Reinforces successful patterns to build on them.
    
    Success isn't just "it worked" - it's understanding WHY it worked
    so we can repeat and build on it.
    """
    
    @classmethod
    def analyze(cls, result: str, hypothesis: str, context: str = "") -> List[Dict]:
        """Analyze a success and extract learnings."""
        learnings = []
        
        # Core learning: What worked
        learnings.append({
            "type": LearningType.WHAT_WORKS.value,
            "content": f"This approach works: {hypothesis[:100]}",
            "confidence": 0.8,
        })
        
        # Try to understand WHY it worked
        why_learnings = cls._infer_why(result, hypothesis, context)
        learnings.extend(why_learnings)
        
        # Identify what can be built on
        build_learnings = cls._identify_build_opportunities(result, hypothesis)
        learnings.extend(build_learnings)
        
        return learnings
    
    @classmethod
    def _infer_why(cls, result: str, hypothesis: str, context: str) -> List[Dict]:
        """Try to infer why something worked."""
        learnings = []
        
        # Pattern: If hypothesis mentions a specific technique
        techniques = ["import", "class", "function", "loop", "condition", "try", "with"]
        for tech in techniques:
            if tech in hypothesis.lower():
                learnings.append({
                    "type": LearningType.WHY_IT_WORKS.value,
                    "content": f"Using {tech} was effective for this problem",
                    "confidence": 0.6,
                })
                break
        
        return learnings
    
    @classmethod
    def _identify_build_opportunities(cls, result: str, hypothesis: str) -> List[Dict]:
        """Identify opportunities to build on this success."""
        learnings = []
        
        # Generic build opportunity
        learnings.append({
            "type": LearningType.ALTERNATIVE.value,
            "content": f"Can extend this pattern: {hypothesis[:50]}",
            "confidence": 0.5,
        })
        
        return learnings


# ════════════════════════════════════════════════════════════════════════════════
# SANDBOX EXPERIMENTER
# ════════════════════════════════════════════════════════════════════════════════

class SandboxExperimenter:
    """
    Safe experimentation in the sandbox.
    
    The sandbox is our laboratory for DELIBERATE FAILURE:
    - Try things without fear of breaking production
    - Learn the edges by crossing them
    - Build intuition through trial and error
    """
    
    def __init__(self, post=None):
        self.post = post
        self.sandbox_root = SANDBOX_ROOT
        
        # Ensure sandbox exists
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        
        # Experiment tracking
        self.experiments: deque = deque(maxlen=100)
        self.learnings_db: Dict[str, List[Dict]] = {}  # domain -> learnings
        
        # Stats
        self.stats = {
            "experiments_run": 0,
            "successes": 0,
            "failures": 0,
            "learnings_captured": 0,
        }
        
        print(f"[SandboxExperimenter] Initialized - sandbox at {self.sandbox_root}")
    
    def create_experiment_space(self, name: str) -> Path:
        """Create a clean experiment folder."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        exp_path = self.sandbox_root / f"experiment_{name}_{timestamp}"
        exp_path.mkdir(parents=True, exist_ok=True)
        
        # Create README
        readme = exp_path / "README.md"
        readme.write_text(f"""# Experiment: {name}
Created: {timestamp}

## Hypothesis
[What do you think will happen?]

## Approach
[What are you going to try?]

## Results
[What actually happened?]

## Learnings
[What did you learn?]
""")
        
        return exp_path
    
    def run_experiment(self, hypothesis: str, code: str, domain: str = "python",
                      tags: List[str] = None) -> ExperimentRecord:
        """
        Run an experiment in the sandbox.
        
        Args:
            hypothesis: What we think will happen
            code: Python code to execute
            domain: Domain of experiment
            tags: Optional tags
            
        Returns:
            ExperimentRecord with outcome and learnings
        """
        record = ExperimentRecord(
            hypothesis=hypothesis,
            action=f"Execute code in sandbox",
            code=code,
            domain=domain,
            tags=tags or [],
            initial_affect=0.5,
        )
        
        # Create experiment space
        exp_path = self.create_experiment_space(domain)
        record.sandbox_path = str(exp_path)
        
        # Write code to file
        code_file = exp_path / "experiment.py"
        code_file.write_text(code)
        record.files_created.append(str(code_file))
        
        # Execute!
        start_time = time.time()
        try:
            # Execute in isolated namespace
            namespace = {"__name__": "__main__", "__file__": str(code_file)}
            exec(compile(code, str(code_file), "exec"), namespace)
            
            # Success!
            record.outcome = OutcomeType.SUCCESS
            record.result = "Code executed successfully"
            record.outcome_affect = 0.8
            
            # Analyze success
            learnings = SuccessReinforcer.analyze(record.result, hypothesis)
            for learning in learnings:
                record.add_learning(
                    LearningType(learning["type"]),
                    learning["content"],
                    learning.get("confidence", 0.5)
                )
            
            self.stats["successes"] += 1
            
        except Exception as e:
            # Failure! But that's GOOD - we learn from it
            record.outcome = OutcomeType.FAILURE
            record.error = str(e)
            record.result = f"Failed: {type(e).__name__}"
            record.outcome_affect = 0.3
            
            # Analyze failure
            learnings = FailureAnalyzer.analyze(str(e), hypothesis)
            for learning in learnings:
                record.add_learning(
                    LearningType(learning["type"]),
                    learning["content"],
                    learning.get("confidence", 0.5)
                )
            
            self.stats["failures"] += 1
        
        record.duration_sec = time.time() - start_time
        
        # Store experiment
        self.experiments.append(record)
        self.stats["experiments_run"] += 1
        self.stats["learnings_captured"] += len(record.learnings)
        
        # Store learnings by domain
        if domain not in self.learnings_db:
            self.learnings_db[domain] = []
        self.learnings_db[domain].extend(record.learnings)
        
        # Write results
        self._write_experiment_results(exp_path, record)
        
        # Publish to memory
        if self.post:
            self.post.route("memory.working.tracer", record.to_memory_tracer())
            
            # Publish experiment event
            self.post.route("experiment.completed", record.to_dict())
        
        # Log
        status = "✓" if record.was_successful() else "✗"
        print(f"[SandboxExperimenter] {status} {hypothesis[:50]}... ({len(record.learnings)} learnings)")
        
        return record
    
    def deliberate_failure_experiment(self, topic: str, variations: int = 3) -> List[ExperimentRecord]:
        """
        Deliberately try variations to find what works and what doesn't.
        
        This is LEARNING BY EXPLORATION:
        - Try multiple approaches
        - Some will fail (good!)
        - Some will succeed
        - Compare to understand WHY
        """
        records = []
        
        # Generate variations to try
        variations_to_try = self._generate_variations(topic, variations)
        
        for i, (hypothesis, code) in enumerate(variations_to_try):
            print(f"[SandboxExperimenter] Trying variation {i+1}/{len(variations_to_try)}: {hypothesis[:40]}...")
            record = self.run_experiment(hypothesis, code, domain="exploration", tags=["deliberate", topic])
            records.append(record)
        
        # Analyze the set of experiments
        self._compare_outcomes(records)
        
        return records
    
    def _generate_variations(self, topic: str, count: int) -> List[Tuple[str, str]]:
        """Generate code variations to test a topic."""
        variations = []
        
        # These are templates for common exploration patterns
        if "import" in topic.lower():
            variations = [
                ("Try absolute import", f"import {topic.split()[-1]}"),
                ("Try from import", f"from {topic.split()[-1]} import *"),
                ("Try relative import", f"from . import {topic.split()[-1]}"),
            ]
        elif "function" in topic.lower():
            variations = [
                ("Define simple function", "def test_func():\n    return 'hello'"),
                ("Define with args", "def test_func(x):\n    return x * 2"),
                ("Define with defaults", "def test_func(x=10):\n    return x"),
            ]
        elif "class" in topic.lower():
            variations = [
                ("Simple class", "class Test:\n    pass"),
                ("Class with init", "class Test:\n    def __init__(self):\n        self.value = 1"),
                ("Class with method", "class Test:\n    def do_thing(self):\n        return 'done'"),
            ]
        else:
            # Generic variations
            variations = [
                ("Print statement", f"print('Testing {topic}')"),
                ("Variable assignment", f"x = '{topic}'"),
                ("Type check", f"type('{topic}')"),
            ]
        
        return variations[:count]
    
    def _compare_outcomes(self, records: List[ExperimentRecord]):
        """Compare outcomes to extract comparative learnings."""
        successes = [r for r in records if r.was_successful()]
        failures = [r for r in records if not r.was_successful()]
        
        if successes and failures:
            # We have both - great for learning!
            comparison_learning = {
                "type": LearningType.ALTERNATIVE.value,
                "content": f"Compared {len(records)} approaches: {len(successes)} worked, {len(failures)} failed",
                "success_patterns": [s.hypothesis[:50] for s in successes],
                "failure_patterns": [f.hypothesis[:50] for f in failures],
                "confidence": 0.8,
            }
            
            # Add to learnings
            for record in records:
                record.learnings.append(comparison_learning)
            
            # Publish comparative insight
            if self.post:
                self.post.route("thought.chain.insight", {
                    "insight": comparison_learning,
                    "source": "SandboxExperimenter",
                })
    
    def _write_experiment_results(self, exp_path: Path, record: ExperimentRecord):
        """Write experiment results to the sandbox."""
        results_file = exp_path / "RESULTS.md"
        
        status = "SUCCESS" if record.was_successful() else "FAILURE"
        learnings_text = "\n".join(
            f"- [{l['type']}] {l['content']}" 
            for l in record.learnings
        )
        
        results_file.write_text(f"""# Experiment Results

## Status: {status}

## Hypothesis
{record.hypothesis}

## Code
```python
{record.code}
```

## Outcome
{record.result}

{f"## Error\n{record.error}" if record.error else ""}

## Learnings
{learnings_text}

## Duration
{record.duration_sec:.2f} seconds

## Affect
- Before: {record.initial_affect:.2f}
- After: {record.outcome_affect:.2f}
""")
    
    def get_learnings(self, domain: str = None) -> List[Dict]:
        """Get accumulated learnings, optionally filtered by domain."""
        if domain:
            return self.learnings_db.get(domain, [])
        
        # All learnings
        all_learnings = []
        for learnings in self.learnings_db.values():
            all_learnings.extend(learnings)
        return all_learnings
    
    def get_stats(self) -> Dict:
        """Get experimenter stats."""
        success_rate = (
            self.stats["successes"] / self.stats["experiments_run"] 
            if self.stats["experiments_run"] > 0 else 0
        )
        
        return {
            **self.stats,
            "success_rate": success_rate,
            "domains": list(self.learnings_db.keys()),
            "sandbox_path": str(self.sandbox_root),
        }


# ════════════════════════════════════════════════════════════════════════════════
# LEARNING LOOP - Continuous Improvement
# ════════════════════════════════════════════════════════════════════════════════

class LearningLoop:
    """
    The continuous learning loop that builds wisdom over time.
    
    ((Cause + Affect) > Effect > Affect > ∞)
    
    Applied to learning:
    - Try something (Cause)
    - Feel success/failure (Affect)
    - Get outcome (Effect)
    - Reflect on WHY (Affect)
    - Apply to next attempt (∞)
    """
    
    def __init__(self, post=None):
        self.post = post
        self.experimenter = SandboxExperimenter(post)
        
        # Wisdom accumulated over time
        self.wisdom: Dict[str, List[Dict]] = {
            "what_works": [],
            "what_fails": [],
            "edge_cases": [],
            "prerequisites": [],
        }
        
        # Success momentum
        self.success_streak = 0
        self.failure_streak = 0
        
        # Stats
        self.stats = {
            "total_learnings": 0,
            "wisdom_items": 0,
            "momentum_builds": 0,
            "course_corrections": 0,
        }
    
    def learn_by_doing(self, topic: str, hypothesis: str, code: str) -> Dict:
        """
        Learn by trying something.
        
        Returns a complete learning report.
        """
        # Run experiment
        record = self.experimenter.run_experiment(hypothesis, code, domain=topic)
        
        # Update streaks
        if record.was_successful():
            self.success_streak += 1
            self.failure_streak = 0
            
            # Build momentum on success
            if self.success_streak >= 3:
                self._build_momentum(record)
        else:
            self.failure_streak += 1
            self.success_streak = 0
            
            # Course correct on repeated failure
            if self.failure_streak >= 3:
                self._course_correct(record)
        
        # Extract wisdom
        self._extract_wisdom(record)
        
        return {
            "outcome": record.outcome.value,
            "learnings": record.learnings,
            "success_streak": self.success_streak,
            "failure_streak": self.failure_streak,
            "wisdom_added": len(record.learnings),
        }
    
    def explore_deliberately(self, topic: str, variations: int = 3) -> Dict:
        """
        Deliberately explore a topic with multiple variations.
        
        Some will fail - that's the point!
        """
        records = self.experimenter.deliberate_failure_experiment(topic, variations)
        
        # Extract wisdom from the whole set
        for record in records:
            self._extract_wisdom(record)
        
        successes = sum(1 for r in records if r.was_successful())
        failures = len(records) - successes
        
        return {
            "topic": topic,
            "variations_tried": len(records),
            "successes": successes,
            "failures": failures,
            "total_learnings": sum(len(r.learnings) for r in records),
            "best_approach": records[0].hypothesis if records and records[0].was_successful() else None,
        }
    
    def _build_momentum(self, record: ExperimentRecord):
        """Build on success streak - we're onto something!"""
        self.stats["momentum_builds"] += 1
        
        # Publish momentum event
        if self.post:
            self.post.route("learning.momentum", {
                "streak": self.success_streak,
                "domain": record.domain,
                "last_success": record.hypothesis,
                "message": "Building momentum! Keep going in this direction.",
            })
            
            # Inject positive affect
            self.post.route("affect.inject", {
                "valence": 0.8,
                "arousal": 0.6,
                "reason": "success_streak",
            })
    
    def _course_correct(self, record: ExperimentRecord):
        """Repeated failures - time to try something different."""
        self.stats["course_corrections"] += 1
        
        # Publish course correction
        if self.post:
            self.post.route("learning.course_correct", {
                "failure_streak": self.failure_streak,
                "domain": record.domain,
                "last_failure": record.hypothesis,
                "message": "Repeated failures. Time to try a different approach.",
            })
            
            # Trigger reflection
            self.post.route("thought.chain.redirect", {
                "reason": "failure_streak",
                "suggestion": "Try a completely different approach",
            })
    
    def _extract_wisdom(self, record: ExperimentRecord):
        """Extract and store wisdom from an experiment."""
        for learning in record.learnings:
            learning_type = learning.get("type", "")
            
            if learning_type == LearningType.WHAT_WORKS.value:
                self.wisdom["what_works"].append(learning)
            elif learning_type == LearningType.WHAT_FAILS.value:
                self.wisdom["what_fails"].append(learning)
            elif learning_type == LearningType.EDGE_CASE.value:
                self.wisdom["edge_cases"].append(learning)
            elif learning_type == LearningType.PREREQUISITE.value:
                self.wisdom["prerequisites"].append(learning)
            
            self.stats["total_learnings"] += 1
            self.stats["wisdom_items"] = sum(len(v) for v in self.wisdom.values())
    
    def get_wisdom(self, category: str = None) -> Dict:
        """Get accumulated wisdom."""
        if category:
            return self.wisdom.get(category, [])
        return self.wisdom
    
    def get_stats(self) -> Dict:
        """Get learning loop stats."""
        return {
            **self.stats,
            "experimenter_stats": self.experimenter.get_stats(),
            "current_success_streak": self.success_streak,
            "current_failure_streak": self.failure_streak,
        }


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_learning_loop_instance: Optional[LearningLoop] = None


def get_learning_loop() -> LearningLoop:
    """Get or create the learning loop singleton."""
    global _learning_loop_instance
    if _learning_loop_instance is None:
        _learning_loop_instance = LearningLoop()
    return _learning_loop_instance


def start_learning_loop(post=None) -> LearningLoop:
    """Start the learning loop with postal hub."""
    loop = get_learning_loop()
    if post:
        loop.post = post
        loop.experimenter.post = post
    return loop


# ════════════════════════════════════════════════════════════════════════════════
# INTEGRATION
# ════════════════════════════════════════════════════════════════════════════════

def wire_learning_to_system():
    """Wire learning loop to the Akashic system."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        
        loop = start_learning_loop(post)
        
        # Listen for learning triggers
        def on_curiosity(packet):
            topic = packet.get("topic", "unknown")
            # Explore with variations
            loop.explore_deliberately(topic, variations=3)
        
        def on_experiment_request(packet):
            topic = packet.get("topic", "test")
            hypothesis = packet.get("hypothesis", "Test something")
            code = packet.get("code", "print('hello')")
            loop.learn_by_doing(topic, hypothesis, code)
        
        post.subscribe("curiosity.sparked", on_curiosity)
        post.subscribe("learning.experiment_request", on_experiment_request)
        
        print(f"[LearningLoop] Wired to system")
        
    except Exception as e:
        print(f"[LearningLoop] Wiring failed: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Failure Factory Test ===\n")
    
    loop = LearningLoop()
    
    # Test 1: Successful experiment
    print("Test 1: Success")
    result = loop.learn_by_doing(
        "python_basics",
        "Print statement should work",
        "print('Hello, learning!')"
    )
    print(f"  Outcome: {result['outcome']}")
    print(f"  Learnings: {len(result['learnings'])}")
    
    # Test 2: Failed experiment (deliberate)
    print("\nTest 2: Deliberate Failure")
    result = loop.learn_by_doing(
        "python_basics",
        "This import should fail",
        "import nonexistent_module_xyz"
    )
    print(f"  Outcome: {result['outcome']}")
    print(f"  Learnings: {len(result['learnings'])}")
    for l in result['learnings']:
        print(f"    - [{l['type']}] {l['content'][:50]}...")
    
    # Test 3: Deliberate exploration
    print("\nTest 3: Deliberate Exploration")
    result = loop.explore_deliberately("function definition", variations=3)
    print(f"  Variations tried: {result['variations_tried']}")
    print(f"  Successes: {result['successes']}")
    print(f"  Failures: {result['failures']}")
    print(f"  Total learnings: {result['total_learnings']}")
    
    # Show accumulated wisdom
    print("\n=== Accumulated Wisdom ===")
    wisdom = loop.get_wisdom()
    for category, items in wisdom.items():
        print(f"\n{category}: {len(items)} items")
        for item in items[:2]:
            print(f"  - {item['content'][:60]}...")
    
    print(f"\n=== Stats ===")
    print(json.dumps(loop.get_stats(), indent=2))
