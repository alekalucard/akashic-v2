# learning_trace.py — Learning Trace Infrastructure
# ═══════════════════════════════════════════════════════════════════════════════
# INFRA: This is foundational infrastructure, not app-level functionality.
#
# Learning Traces are the crystallized output of reflection. When a reflection
# has been pondered enough and patterns emerge, it becomes a Learning Trace -
# a persistent record that can be:
#   - Stored in SRM_Intake as memory cards
#   - Used by other fairies to learn from past experience
#   - Applied to future similar situations
#
# Biological analog: Long-term potentiation - the strengthening of synaptic
# connections that forms the basis of learning and memory.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import uuid
import json
import hashlib
import threading
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union
from pathlib import Path
from datetime import datetime, timezone

from .reflection_pool import Reflection


@dataclass
class LearningTrace:
    """
    A learning trace - crystallized knowledge from reflection.
    
    Unlike raw reflections, learning traces are:
    - Actionable: They include what to do differently
    - Transferable: Other fairies can apply them
    - Persistent: They're written to memory cards
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # Source tracking
    source_reflection_id: str = ""
    source_fairy: str = ""
    source_action: str = ""
    
    # The learning
    pattern: str = ""                        # What pattern was observed
    insight: str = ""                        # What was learned
    recommendation: str = ""                 # What to do next time
    confidence: float = 0.5                  # 0-1, how confident in this learning
    
    # Applicability
    applies_to: List[str] = field(default_factory=list)  # Which fairies/actions this applies to
    conditions: List[str] = field(default_factory=list)  # When this learning applies
    contraindications: List[str] = field(default_factory=list)  # When NOT to apply
    
    # Affect metadata (inherited from reflection)
    affect: Dict[str, Any] = field(default_factory=lambda: {
        "valence": 0.0,
        "arousal": 0.0,
        "resonance": [],
    })
    
    # Lifecycle
    created_at: float = field(default_factory=time.time)
    applied_count: int = 0                   # How many times this was applied
    success_count: int = 0                   # How many times application was successful
    last_applied_at: Optional[float] = None
    
    # Linkage
    related_traces: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    # First Ethic compliance
    first_ethic: Dict[str, Any] = field(default_factory=lambda: {
        "frame": "first_ethic",
        "principles": {
            "absorption_is_not_identity": True,
            "knowledge_is_perspective": True,
            "bias_is_telemetry": True,
            "choose_what_to_integrate": True,
        },
        "integration_guidance": "learn_not_become",
    })
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of applying this trace."""
        if self.applied_count == 0:
            return 0.0
        return self.success_count / self.applied_count
    
    @property
    def effective_confidence(self) -> float:
        """
        Confidence adjusted by application history.
        More applications with high success = higher effective confidence.
        """
        if self.applied_count == 0:
            return self.confidence
        
        # Bayesian-ish update
        prior = self.confidence
        evidence = self.success_rate
        weight = min(1.0, self.applied_count / 10.0)  # Cap influence at 10 applications
        
        return prior * (1 - weight) + evidence * weight
    
    def mark_applied(self, success: bool = True):
        """Mark this trace as having been applied."""
        self.applied_count += 1
        if success:
            self.success_count += 1
        self.last_applied_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_reflection_id": self.source_reflection_id,
            "source_fairy": self.source_fairy,
            "source_action": self.source_action,
            "pattern": self.pattern,
            "insight": self.insight,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "applies_to": self.applies_to,
            "conditions": self.conditions,
            "contraindications": self.contraindications,
            "affect": self.affect,
            "created_at": self.created_at,
            "applied_count": self.applied_count,
            "success_count": self.success_count,
            "last_applied_at": self.last_applied_at,
            "related_traces": self.related_traces,
            "tags": self.tags,
            "first_ethic": self.first_ethic,
        }
    
    def to_memory_card(self) -> Dict[str, Any]:
        """
        Convert to SRM_Intake memory card format.
        
        This is the format that gets written to /SRM_Intake/ for
        the memory system to absorb.
        """
        return {
            "kind": "learning.trace",
            "data": {
                "pattern": self.pattern,
                "insight": self.insight,
                "recommendation": self.recommendation,
                "confidence": self.confidence,
                "source_fairy": self.source_fairy,
                "source_action": self.source_action,
                "applies_to": self.applies_to,
                "conditions": self.conditions,
                "learned_at": datetime.fromtimestamp(
                    self.created_at, tz=timezone.utc
                ).isoformat(),
            },
            "meta": {
                "type": "learning_trace",
                "trace_id": self.id,
                "reflection_id": self.source_reflection_id,
                "applied_count": self.applied_count,
                "success_rate": self.success_rate,
            },
            "affect": self.affect,
            "first_ethic": self.first_ethic,
            "ts": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LearningTrace":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def from_reflection(
        cls,
        reflection: Reflection,
        *,
        insight: str = "",
        recommendation: str = "",
        confidence: float = 0.5,
    ) -> "LearningTrace":
        """
        Create a learning trace from a crystallized reflection.
        
        This is the typical path: reflection marinates → crystallizes → becomes trace.
        """
        # Derive pattern from reflection
        pattern = reflection.observation
        if reflection.delta:
            pattern = f"{pattern} [Delta: {reflection.delta}]"
        
        # Use reflection's hypothesis as insight if none provided
        if not insight and reflection.hypothesis:
            insight = reflection.hypothesis
        
        return cls(
            source_reflection_id=reflection.id,
            source_fairy=reflection.source_fairy,
            source_action=reflection.source_action,
            pattern=pattern,
            insight=insight,
            recommendation=recommendation,
            confidence=confidence,
            applies_to=[reflection.source_fairy],
            conditions=[f"action:{reflection.source_action}"] if reflection.source_action else [],
            affect=reflection.affect.copy() if reflection.affect else {},
            tags=reflection.tags.copy() if reflection.tags else [],
        )


class TraceEmitter:
    """
    Handles emitting learning traces to the memory system.
    
    Responsibilities:
    - Convert traces to memory cards
    - Write to SRM_Intake directory
    - Optionally publish to postal system
    - Track emission history
    """
    
    def __init__(
        self,
        srm_intake_path: Optional[str] = None,
        post_office: Optional[Any] = None,
        emit_to_file: bool = True,
        emit_to_postal: bool = True,
    ):
        self._srm_path = srm_intake_path
        self._post = post_office
        self._emit_file = emit_to_file
        self._emit_postal = emit_to_postal
        self._lock = threading.Lock()
        self._emitted: List[str] = []  # Track emitted trace IDs
        
        # Resolve SRM path if not provided
        if not self._srm_path:
            self._srm_path = self._find_srm_intake()
    
    def _find_srm_intake(self) -> Optional[str]:
        """Find the SRM_Intake directory."""
        # Check environment variable
        env_path = os.getenv("SRM_INTAKE_PATH")
        if env_path and os.path.isdir(env_path):
            return env_path
        
        # Check relative paths
        candidates = [
            "SRM_Intake",
            "../SRM_Intake",
            "../../SRM_Intake",
            "P10_Memory/SRM_Intake",
            "../P10_Memory/SRM_Intake",
        ]
        
        for cand in candidates:
            if os.path.isdir(cand):
                return os.path.abspath(cand)
        
        return None
    
    def emit(self, trace: LearningTrace) -> Dict[str, Any]:
        """
        Emit a learning trace to the memory system.
        
        Returns a dict with emission results.
        """
        results = {
            "trace_id": trace.id,
            "emitted_file": False,
            "emitted_postal": False,
            "file_path": None,
            "errors": [],
        }
        
        with self._lock:
            # Emit to file
            if self._emit_file and self._srm_path:
                try:
                    card = trace.to_memory_card()
                    
                    # Generate filename with date subdirectory
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    date_dir = os.path.join(self._srm_path, date_str)
                    os.makedirs(date_dir, exist_ok=True)
                    
                    # Filename: learning.trace-{trace_id}.json
                    filename = f"learning.trace-{trace.id}.json"
                    filepath = os.path.join(date_dir, filename)
                    
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(card, f, indent=2, ensure_ascii=False)
                    
                    results["emitted_file"] = True
                    results["file_path"] = filepath
                    
                except Exception as e:
                    results["errors"].append(f"file_emit: {e}")
            
            # Emit to postal system
            if self._emit_postal and self._post:
                try:
                    self._post.route("SRM_INTAKE", {
                        "opcode": "LEARNING_TRACE",
                        "payload": trace.to_memory_card(),
                    })
                    results["emitted_postal"] = True
                except Exception as e:
                    results["errors"].append(f"postal_emit: {e}")
            
            self._emitted.append(trace.id)
        
        return results
    
    def emit_from_reflection(
        self,
        reflection: Reflection,
        *,
        insight: str = "",
        recommendation: str = "",
        confidence: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Create and emit a learning trace from a reflection in one step.
        """
        trace = LearningTrace.from_reflection(
            reflection,
            insight=insight,
            recommendation=recommendation,
            confidence=confidence,
        )
        return self.emit(trace)
    
    def get_emitted_count(self) -> int:
        """Get count of traces emitted this session."""
        with self._lock:
            return len(self._emitted)
    
    def set_srm_path(self, path: str):
        """Set the SRM_Intake path."""
        with self._lock:
            self._srm_path = path
    
    def set_post_office(self, post: Any):
        """Set the postal system reference."""
        with self._lock:
            self._post = post


# ═══════════════════════════════════════════════════════════════════════════════
# Global emitter instance
# ═══════════════════════════════════════════════════════════════════════════════

_global_emitter: Optional[TraceEmitter] = None
_emitter_lock = threading.Lock()

def get_trace_emitter() -> TraceEmitter:
    """Get or create the global trace emitter."""
    global _global_emitter
    with _emitter_lock:
        if _global_emitter is None:
            _global_emitter = TraceEmitter()
        return _global_emitter

def set_trace_emitter(emitter: TraceEmitter):
    """Set a custom global trace emitter."""
    global _global_emitter
    with _emitter_lock:
        _global_emitter = emitter
