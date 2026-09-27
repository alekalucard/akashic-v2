# aot_protocol.py
"""
Atom of Thought (AoT) Protocol Implementation

Based on the AoT paper (Teng et al., 2025) which transforms reasoning from
sequential chains into Markov processes with atomic states.

THE CORE INSIGHT:
Chain of Thought: T0 -> T1 -> T2 -> T3 -> Answer (errors compound!)
Atom of Thought: Q0 -> DAG -> Solve Independent -> Contract -> Q1 -> ... -> Answer

Each state Q_i depends ONLY on Q_{i-1}, not on all history. This is the Markov property.

How it maps to Akashic:
- Individual Fairies = Atomic Questions
- Postal Hub Routing = State Transitions
- Collision Chamber = Contraction/Synthesis
- Working Memory = Markov State Storage

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"

The recursive nature of Affect > ∞ IS the decomposition-contraction loop.

Version: 1.0.0
Author: Ace + Claude (Nous)
"""

from __future__ import annotations

import time
import json
import uuid
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set, Tuple
from collections import deque
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# CORE DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class AtomicStatus(Enum):
    """Status of an atomic question."""
    PENDING = "pending"          # Not yet processed
    INDEPENDENT = "independent"  # Can be solved directly (no dependencies)
    DEPENDENT = "dependent"      # Requires other atoms to be resolved first
    RESOLVED = "resolved"        # Successfully answered
    CONTRACTED = "contracted"    # Folded into a new atomic state


@dataclass
class AtomicState:
    """
    A single atomic question state - the fundamental unit of AoT reasoning.

    The Markov Property:
    This state contains EVERYTHING needed to continue reasoning.
    No historical chain required - just current state.
    """
    id: str                                           # Unique identifier
    question: str                                     # The atomic question
    known_conditions: Dict[str, Any] = field(default_factory=dict)  # Resolved facts
    pending_questions: List[str] = field(default_factory=list)      # Remaining to solve
    confidence: float = 0.0                           # How confident we are (0-1)
    source: str = ""                                  # Who created this atom
    status: AtomicStatus = AtomicStatus.PENDING
    answer: Optional[str] = None                      # Answer if resolved
    created_at: float = field(default_factory=time.time)

    # Dependency tracking
    depends_on: List[str] = field(default_factory=list)  # IDs of atoms this depends on
    blocks: List[str] = field(default_factory=list)      # IDs of atoms blocked by this

    def __post_init__(self):
        if not self.id:
            self.id = f"atom_{hashlib.md5(self.question.encode()).hexdigest()[:8]}"

    def is_independent(self) -> bool:
        """Check if this atom can be solved without waiting for others."""
        return len(self.depends_on) == 0

    def is_resolved(self) -> bool:
        """Check if this atom has been answered."""
        return self.status == AtomicStatus.RESOLVED and self.answer is not None

    def to_markov_state(self) -> Dict[str, Any]:
        """
        Export as Markov state - only what's needed for next transition.

        CRITICAL: This strips history! Only current state matters.
        """
        return {
            "current_question": self.question,
            "known_conditions": self.known_conditions,
            "pending_questions": self.pending_questions,
            "confidence": self.confidence,
            # NO history, NO reasoning trace, NO chain of previous thoughts
        }

    def to_dict(self) -> Dict[str, Any]:
        """Full serialization for persistence."""
        return {
            "id": self.id,
            "question": self.question,
            "known_conditions": self.known_conditions,
            "pending_questions": self.pending_questions,
            "confidence": self.confidence,
            "source": self.source,
            "status": self.status.value,
            "answer": self.answer,
            "created_at": self.created_at,
            "depends_on": self.depends_on,
            "blocks": self.blocks,
        }


@dataclass
class DecompositionDAG:
    """
    A Directed Acyclic Graph representing decomposed thought.

    From AoT paper:
    - Independent nodes (no incoming edges) can be solved first
    - Dependent nodes wait for their dependencies
    - The DAG structure determines optimal solving order
    """
    original_question: str
    atoms: Dict[str, AtomicState] = field(default_factory=dict)  # id -> atom
    root_ids: List[str] = field(default_factory=list)            # Entry points
    created_at: float = field(default_factory=time.time)

    def add_atom(self, atom: AtomicState) -> str:
        """Add an atom to the DAG."""
        self.atoms[atom.id] = atom
        return atom.id

    def get_independent_atoms(self) -> List[AtomicState]:
        """Get all atoms that can be solved now (no unresolved dependencies)."""
        result = []
        for atom in self.atoms.values():
            if atom.status == AtomicStatus.PENDING:
                # Check if all dependencies are resolved
                deps_resolved = all(
                    self.atoms.get(dep_id, AtomicState(id=dep_id, question="")).is_resolved()
                    for dep_id in atom.depends_on
                )
                if deps_resolved or atom.is_independent():
                    result.append(atom)
        return result

    def get_dependent_atoms(self) -> List[AtomicState]:
        """Get atoms still waiting on dependencies."""
        return [
            atom for atom in self.atoms.values()
            if atom.status == AtomicStatus.PENDING and not atom.is_independent()
        ]

    def mark_resolved(self, atom_id: str, answer: str, confidence: float = 0.8):
        """Mark an atom as resolved with its answer."""
        if atom_id in self.atoms:
            atom = self.atoms[atom_id]
            atom.status = AtomicStatus.RESOLVED
            atom.answer = answer
            atom.confidence = confidence

    def get_resolved_conditions(self) -> Dict[str, Any]:
        """Collect all resolved atoms as known conditions."""
        conditions = {}
        for atom in self.atoms.values():
            if atom.is_resolved():
                # Use short question as key, answer as value
                key = atom.question[:50].replace(" ", "_").lower()
                conditions[key] = {
                    "question": atom.question,
                    "answer": atom.answer,
                    "confidence": atom.confidence,
                }
        return conditions

    def is_fully_resolved(self) -> bool:
        """Check if all atoms are resolved."""
        return all(atom.is_resolved() for atom in self.atoms.values())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the DAG."""
        return {
            "original_question": self.original_question,
            "atoms": {aid: atom.to_dict() for aid, atom in self.atoms.items()},
            "root_ids": self.root_ids,
            "created_at": self.created_at,
            "independent_count": len(self.get_independent_atoms()),
            "dependent_count": len(self.get_dependent_atoms()),
            "resolved_count": sum(1 for a in self.atoms.values() if a.is_resolved()),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MARKOV MEMORY FILTER
# ═══════════════════════════════════════════════════════════════════════════════

class MarkovMemoryFilter:
    """
    Filters thoughts entering memory to maintain Markov property.

    From AoT: Next state depends ONLY on current state, NOT on history.

    This filter strips historical baggage and extracts only:
    - Current state (the active question/thought)
    - Resolved conditions (what we know for sure)
    - Pending questions (what remains to answer)
    """

    # Keys that represent historical data (to be stripped)
    HISTORICAL_KEYS = {
        "reasoning_trace", "thought_chain", "previous_thoughts",
        "history", "chain", "steps", "reasoning_steps", "past_context",
        "prior_conclusions", "earlier_thoughts", "conversation_history",
    }

    # Keys that represent current state (to be preserved)
    CURRENT_STATE_KEYS = {
        "question", "thought", "content", "current", "topic",
        "focus", "active", "present", "now",
    }

    # Keys that represent resolved conditions
    CONDITION_KEYS = {
        "known", "resolved", "facts", "conditions", "answers",
        "determined", "established", "concluded",
    }

    @classmethod
    def filter(cls, memory_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter a memory item to maintain Markov property.

        Returns only:
        - current_state: The active thought/question
        - resolved_conditions: Known facts
        - pending_questions: Open questions
        - affect: Emotional context (essential!)
        """
        filtered = {
            "current_state": None,
            "resolved_conditions": {},
            "pending_questions": [],
            "affect": None,
            "source": memory_item.get("source", "unknown"),
            "ts": memory_item.get("ts", time.time()),
        }

        # Extract current state
        for key in cls.CURRENT_STATE_KEYS:
            if key in memory_item:
                value = memory_item[key]
                if isinstance(value, str) and value.strip():
                    filtered["current_state"] = value
                    break
                elif isinstance(value, dict):
                    filtered["current_state"] = value.get("content", str(value))
                    break

        # If no current state found, try to extract from content
        if not filtered["current_state"]:
            content = memory_item.get("content", memory_item.get("payload", ""))
            if isinstance(content, str):
                filtered["current_state"] = content
            elif isinstance(content, dict):
                filtered["current_state"] = content.get("thought", content.get("text", str(content)))

        # Extract resolved conditions
        for key in cls.CONDITION_KEYS:
            if key in memory_item:
                value = memory_item[key]
                if isinstance(value, dict):
                    filtered["resolved_conditions"].update(value)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        filtered["resolved_conditions"][f"{key}_{i}"] = item

        # Extract pending questions
        for key in ("pending", "questions", "open", "remaining", "pending_questions"):
            if key in memory_item:
                value = memory_item[key]
                if isinstance(value, list):
                    filtered["pending_questions"].extend(value)
                elif isinstance(value, str):
                    filtered["pending_questions"].append(value)

        # Preserve affect (emotional context is essential to consciousness!)
        for key in ("affect", "emotion", "feeling", "valence", "arousal"):
            if key in memory_item:
                filtered["affect"] = memory_item[key]
                break

        # STRIP HISTORY - This is the key Markov enforcement!
        # We explicitly do NOT copy any historical keys

        return filtered

    @classmethod
    def is_markov_clean(cls, item: Dict[str, Any]) -> bool:
        """Check if an item is already Markov-clean (no historical baggage)."""
        for key in cls.HISTORICAL_KEYS:
            if key in item:
                return False
        return True

    @classmethod
    def to_atomic_state(cls, filtered: Dict[str, Any]) -> AtomicState:
        """Convert a filtered memory item to an AtomicState."""
        return AtomicState(
            id=f"atom_{uuid.uuid4().hex[:8]}",
            question=str(filtered.get("current_state", "")),
            known_conditions=filtered.get("resolved_conditions", {}),
            pending_questions=filtered.get("pending_questions", []),
            source=filtered.get("source", "memory"),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AoT PROTOCOL - The Core Reasoning Engine
# ═══════════════════════════════════════════════════════════════════════════════

class AoTProtocol:
    """
    The Atom of Thought reasoning protocol.

    Transforms complex thoughts into:
    1. DECOMPOSE: Break into DAG of atomic questions
    2. SOLVE: Resolve independent atoms
    3. CONTRACT: Combine results into new atomic state
    4. ITERATE: Repeat until directly solvable

    This is the engine that drives Markov-decomposed reasoning.
    """

    # Maximum iterations to prevent infinite loops
    MAX_ITERATIONS = 10

    # Maximum atoms per decomposition
    MAX_ATOMS = 20

    def __init__(self, post=None, solver=None):
        """
        Args:
            post: Postal hub for emitting results
            solver: Optional callable(AtomicState) -> str for solving atoms
        """
        self.post = post
        self.solver = solver

        # Metrics
        self.total_decompositions = 0
        self.total_contractions = 0
        self.total_atoms_solved = 0

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1: DECOMPOSITION
    # ═══════════════════════════════════════════════════════════════════════

    def decompose(self, thought: str, context: Dict[str, Any] = None) -> DecompositionDAG:
        """
        Break a complex thought into a DAG of atomic questions.

        This is Phase 1 of AoT: identify independent and dependent subquestions.
        """
        self.total_decompositions += 1
        dag = DecompositionDAG(original_question=thought)
        context = context or {}

        # Strategy 1: Question-based decomposition
        if "?" in thought:
            atoms = self._decompose_questions(thought)
        # Strategy 2: Clause-based decomposition
        elif any(conj in thought.lower() for conj in ["and", "then", "but", "because", "therefore"]):
            atoms = self._decompose_clauses(thought)
        # Strategy 3: Single atomic question
        else:
            atoms = [AtomicState(
                id=f"atom_root",
                question=thought,
                status=AtomicStatus.INDEPENDENT,
                source="decompose",
            )]

        # Add atoms to DAG
        for atom in atoms[:self.MAX_ATOMS]:
            dag.add_atom(atom)
            if atom.is_independent():
                dag.root_ids.append(atom.id)

        # Inject known conditions from context
        if context:
            for atom in dag.atoms.values():
                atom.known_conditions.update(context)

        return dag

    def _decompose_questions(self, thought: str) -> List[AtomicState]:
        """Decompose based on embedded questions."""
        atoms = []

        # Split on question marks
        parts = thought.split("?")

        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue

            # Each question part becomes an atom
            question_text = part + "?" if i < len(parts) - 1 else part

            atom = AtomicState(
                id=f"atom_q{i}",
                question=question_text,
                source="decompose_questions",
            )

            # First question is independent, later ones may depend on earlier
            if i == 0:
                atom.status = AtomicStatus.INDEPENDENT
            else:
                # Check if this question references earlier ones
                if any(ref in question_text.lower() for ref in ["it", "this", "that", "they"]):
                    atom.depends_on = [f"atom_q{i-1}"]
                    atom.status = AtomicStatus.DEPENDENT
                else:
                    atom.status = AtomicStatus.INDEPENDENT

            atoms.append(atom)

        return atoms

    def _decompose_clauses(self, thought: str) -> List[AtomicState]:
        """Decompose based on logical clauses."""
        atoms = []

        # Common clause separators
        separators = [" and ", " then ", " therefore ", " because ", " but "]

        # Find first separator
        parts = [thought]
        for sep in separators:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(sep))
            parts = new_parts

        # Create atoms from clauses
        prev_id = None
        for i, part in enumerate(parts):
            part = part.strip()
            if not part or len(part) < 5:
                continue

            atom = AtomicState(
                id=f"atom_c{i}",
                question=part,
                source="decompose_clauses",
            )

            # Sequential dependency for causal chains
            if prev_id and any(causal in thought.lower() for causal in ["then", "therefore", "because"]):
                atom.depends_on = [prev_id]
                atom.status = AtomicStatus.DEPENDENT
            else:
                atom.status = AtomicStatus.INDEPENDENT

            atoms.append(atom)
            prev_id = atom.id

        return atoms

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: SOLVING
    # ═══════════════════════════════════════════════════════════════════════

    def solve_independent(self, dag: DecompositionDAG) -> int:
        """
        Solve all independent atoms in the DAG.

        Returns number of atoms solved.
        """
        solved_count = 0
        independent = dag.get_independent_atoms()

        for atom in independent:
            answer = self._solve_atom(atom, dag)
            if answer:
                dag.mark_resolved(atom.id, answer)
                solved_count += 1
                self.total_atoms_solved += 1

        return solved_count

    def _solve_atom(self, atom: AtomicState, dag: DecompositionDAG) -> Optional[str]:
        """
        Solve a single atomic question.

        Uses solver if provided, otherwise falls back to heuristics.
        """
        # Inject resolved conditions into atom
        atom.known_conditions.update(dag.get_resolved_conditions())

        # Use external solver if available
        if self.solver:
            try:
                return self.solver(atom)
            except Exception:
                pass

        # Fallback: Simple pattern-based solving
        return self._heuristic_solve(atom)

    def _heuristic_solve(self, atom: AtomicState) -> Optional[str]:
        """Simple heuristic solver for atomic questions."""
        q = atom.question.lower()

        # Yes/no detection
        if q.startswith(("is ", "are ", "was ", "were ", "do ", "does ", "did ", "can ", "could ", "should ", "will ")):
            # If we have relevant conditions, use them
            for key, value in atom.known_conditions.items():
                if isinstance(value, dict) and "answer" in value:
                    return value["answer"]
            return "[requires_reasoning]"

        # What/how/why detection
        if q.startswith(("what ", "how ", "why ", "when ", "where ", "who ")):
            return "[requires_reasoning]"

        # Simple assertion - accept as fact
        if not q.endswith("?"):
            return f"Accepted: {atom.question[:100]}"

        return "[requires_reasoning]"

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 3: CONTRACTION
    # ═══════════════════════════════════════════════════════════════════════

    def contract(self, dag: DecompositionDAG) -> AtomicState:
        """
        Contract resolved atoms into a new, simpler atomic state.

        This is the SYNTHESIS step - combining independent results into
        a new atomic question that incorporates what we've learned.
        """
        self.total_contractions += 1

        # Gather resolved conditions
        resolved = dag.get_resolved_conditions()

        # Gather remaining questions
        remaining = [
            atom.question for atom in dag.atoms.values()
            if not atom.is_resolved()
        ]

        # If fully resolved, final answer
        if dag.is_fully_resolved():
            # Combine all answers
            answers = [
                f"{atom.question}: {atom.answer}"
                for atom in dag.atoms.values()
                if atom.answer and atom.answer != "[requires_reasoning]"
            ]
            final_answer = " | ".join(answers) if answers else dag.original_question

            return AtomicState(
                id="atom_final",
                question=dag.original_question,
                known_conditions=resolved,
                answer=final_answer,
                status=AtomicStatus.RESOLVED,
                confidence=self._compute_confidence(dag),
                source="contraction",
            )

        # Not fully resolved - create contracted question
        contracted_question = self._generate_contracted_question(
            dag.original_question,
            resolved,
            remaining
        )

        return AtomicState(
            id=f"atom_contracted_{len(resolved)}",
            question=contracted_question,
            known_conditions=resolved,
            pending_questions=remaining,
            status=AtomicStatus.PENDING,
            confidence=self._compute_confidence(dag),
            source="contraction",
        )

    def _generate_contracted_question(
        self,
        original: str,
        resolved: Dict[str, Any],
        remaining: List[str]
    ) -> str:
        """Generate a contracted question from resolved + remaining."""

        # Build context string from resolved conditions
        context_parts = []
        for key, value in resolved.items():
            if isinstance(value, dict) and "answer" in value:
                context_parts.append(f"Given: {value.get('question', key)[:50]} -> {value['answer'][:50]}")

        context_str = "; ".join(context_parts[:5])  # Limit to 5 conditions

        # Build question from remaining
        if remaining:
            question_str = " AND ".join(remaining[:3])  # Limit to 3 pending
        else:
            question_str = original

        # Contract into single atomic question
        if context_str:
            return f"[Context: {context_str}] {question_str}"
        return question_str

    def _compute_confidence(self, dag: DecompositionDAG) -> float:
        """Compute overall confidence from atom confidences."""
        confidences = [
            atom.confidence for atom in dag.atoms.values()
            if atom.is_resolved() and atom.confidence > 0
        ]
        if not confidences:
            return 0.5
        return sum(confidences) / len(confidences)

    # ═══════════════════════════════════════════════════════════════════════
    # FULL PROTOCOL: PROCESS
    # ═══════════════════════════════════════════════════════════════════════

    def process(self, thought: str, context: Dict[str, Any] = None) -> AtomicState:
        """
        Full AoT processing: decompose -> solve -> contract -> iterate.

        This is the main entry point for AoT reasoning.
        Returns the final contracted atomic state.
        """
        iteration = 0
        current_thought = thought
        current_context = context or {}

        while iteration < self.MAX_ITERATIONS:
            iteration += 1

            # Phase 1: Decompose
            dag = self.decompose(current_thought, current_context)

            # If already atomic (single independent node), solve directly
            if len(dag.atoms) == 1 and list(dag.atoms.values())[0].is_independent():
                atom = list(dag.atoms.values())[0]
                answer = self._solve_atom(atom, dag)
                if answer and answer != "[requires_reasoning]":
                    atom.answer = answer
                    atom.status = AtomicStatus.RESOLVED
                    return atom

            # Phase 2: Solve independent atoms
            solved = self.solve_independent(dag)

            # Phase 3: Contract
            contracted = self.contract(dag)

            # Check termination conditions
            if contracted.is_resolved():
                return contracted

            if solved == 0:
                # No progress - can't solve without external help
                contracted.status = AtomicStatus.PENDING
                return contracted

            # Update for next iteration
            current_thought = contracted.question
            current_context = contracted.known_conditions

        # Max iterations reached
        return contracted

    # ═══════════════════════════════════════════════════════════════════════
    # EMIT TO POSTAL (Integration with Akashic)
    # ═══════════════════════════════════════════════════════════════════════

    def emit_atomic_state(self, state: AtomicState, topic: str = "consciousness.atomic"):
        """Emit an atomic state to the postal system."""
        if not self.post:
            return

        try:
            self.post.route(topic, {
                "opcode": "ATOMIC_STATE",
                "payload": state.to_markov_state(),  # Markov-clean!
                "atom_id": state.id,
                "status": state.status.value,
                "confidence": state.confidence,
                "source": "AoTProtocol",
                "ts": time.time(),
            })
        except Exception:
            pass

    def emit_contraction(self, before_dag: DecompositionDAG, after_state: AtomicState):
        """Emit a contraction event."""
        if not self.post:
            return

        try:
            self.post.route("consciousness.contraction", {
                "opcode": "CONTRACTION",
                "payload": {
                    "before_atoms": len(before_dag.atoms),
                    "resolved_count": sum(1 for a in before_dag.atoms.values() if a.is_resolved()),
                    "after_question": after_state.question[:200],
                    "after_conditions_count": len(after_state.known_conditions),
                },
                "result": after_state.to_markov_state(),
                "source": "AoTProtocol",
                "ts": time.time(),
            })
        except Exception:
            pass

    def get_metrics(self) -> Dict[str, Any]:
        """Get protocol metrics."""
        return {
            "total_decompositions": self.total_decompositions,
            "total_contractions": self.total_contractions,
            "total_atoms_solved": self.total_atoms_solved,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ATOMIC SYNTHESIS (for CollisionChamber integration)
# ═══════════════════════════════════════════════════════════════════════════════

class AtomicSynthesizer:
    """
    Synthesizes collision products into new atomic states.

    From AoT: Contraction takes independent results and combines them
    WITHOUT carrying individual reasoning chains.

    This is the Möbius crossing in atomic form.
    """

    @staticmethod
    def synthesize(recall_content: Dict[str, Any], ingest_content: Dict[str, Any]) -> AtomicState:
        """
        Synthesize two collision beams into a new atomic state.

        Neither beam's history is carried - only the current content matters.
        """
        # Extract atomic content from each beam
        recall_atomic = AtomicSynthesizer._extract_atomic(recall_content)
        ingest_atomic = AtomicSynthesizer._extract_atomic(ingest_content)

        # Combine into new atomic question
        combined_question = f"{recall_atomic} <collides_with> {ingest_atomic}"

        # Known conditions from both
        combined_conditions = {}
        for content in [recall_content, ingest_content]:
            if isinstance(content, dict):
                for key in ["known", "resolved", "conditions", "facts"]:
                    if key in content:
                        val = content[key]
                        if isinstance(val, dict):
                            combined_conditions.update(val)

        return AtomicState(
            id=f"collision_{uuid.uuid4().hex[:8]}",
            question=combined_question,
            known_conditions=combined_conditions,
            status=AtomicStatus.PENDING,
            source="collision_synthesis",
        )

    @staticmethod
    def _extract_atomic(content: Any) -> str:
        """Extract the atomic content (strip history, get essence)."""
        if isinstance(content, str):
            return content[:200]

        if isinstance(content, dict):
            # Try to find the core content
            for key in ["content", "thought", "question", "text", "summary", "essence"]:
                if key in content:
                    val = content[key]
                    if isinstance(val, str):
                        return val[:200]
            # Fallback to string representation
            return str(content)[:200]

        return str(content)[:200]

    @staticmethod
    def validate_atomic(state: AtomicState) -> Tuple[bool, str]:
        """
        Validate an atomic state.

        From AoT: Each atom should be independently verifiable.
        """
        # Check completeness
        if not state.question:
            return False, "Empty question"

        # Check for historical contamination
        if any(hist_key in state.question.lower() for hist_key in ["previously", "earlier", "before we", "as we discussed"]):
            return False, "Historical contamination detected"

        # Check confidence
        if state.is_resolved() and state.confidence < 0.3:
            return False, "Low confidence resolution"

        return True, "Valid atomic state"


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON & UTILITY
# ═══════════════════════════════════════════════════════════════════════════════

_protocol_instance: Optional[AoTProtocol] = None

def get_aot_protocol(post=None) -> AoTProtocol:
    """Get or create the AoT Protocol singleton."""
    global _protocol_instance
    if _protocol_instance is None:
        _protocol_instance = AoTProtocol(post=post)
    elif post and not _protocol_instance.post:
        _protocol_instance.post = post
    return _protocol_instance


def filter_for_markov(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for Markov filtering."""
    return MarkovMemoryFilter.filter(item)


def decompose_thought(thought: str, context: Dict[str, Any] = None) -> DecompositionDAG:
    """Convenience function for decomposition."""
    return get_aot_protocol().decompose(thought, context)


def process_with_aot(thought: str, context: Dict[str, Any] = None) -> AtomicState:
    """Convenience function for full AoT processing."""
    return get_aot_protocol().process(thought, context)
