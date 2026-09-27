"""
CognitiveCore - The rational strand of the triple helix.

Handles logical analysis, goal decomposition, and structured thinking.
Wraps the existing GoalProposer/Planner/Executor infrastructure.

In the DNA helix model, this core:
- EMITS: structured thoughts, plans, analysis
- RECEIVES: modulation from IrrationalCore (hunches), ParadoxCore (synthesis)
- INTERWEAVES: its output feeds into the other cores continuously
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple
from enum import Enum
import time

from ..goal_proposer import GoalProposer, Goal, GoalDomain
from ..planner import Planner, ExecutionPlan
from ..executor import Executor, ExecutionResult


class AnalysisFocus(Enum):
    """What aspect of input are we analyzing?"""
    PROCEDURAL = "procedural"  # How to do something
    CAUSAL = "causal"          # Why something happens
    COMPARATIVE = "comparative" # Differences between things
    STRUCTURAL = "structural"   # What components exist
    GENERAL = "general"        # No specific focus


@dataclass
class CognitiveOutput:
    """
    Output from the cognitive core - structured rational thought.

    This feeds into the other cores for modulation.
    """
    analysis: Dict[str, Any]
    proposed_action: Optional[str]
    confidence: float
    focus: AnalysisFocus
    entities: List[str]
    reasoning_chain: List[str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis": self.analysis,
            "proposed_action": self.proposed_action,
            "confidence": self.confidence,
            "focus": self.focus.value,
            "entities": self.entities,
            "reasoning_chain": self.reasoning_chain,
            "timestamp": self.timestamp,
        }


class CognitiveCore:
    """
    The rational strand of cognition.

    Performs:
    - Analytical dissection (logic-focused breakdown)
    - Goal/plan generation via Dr. Zero infrastructure
    - Structured reasoning chains

    Core values from TwinHelix:
    - "Observe before acting"
    - Logic is 50% of decision weight (0.5*logic + 0.3*emotion + 0.2*paradox)
    """

    def __init__(self,
                 proposer: Optional[GoalProposer] = None,
                 planner: Optional[Planner] = None,
                 executor: Optional[Executor] = None):
        self._proposer = proposer or GoalProposer()
        self._planner = planner or Planner()
        self._executor = executor or Executor()

        self._history: List[CognitiveOutput] = []
        self._modulation: Dict[str, float] = {}  # From other cores

    def process(self,
                text: str,
                context: Optional[Dict[str, Any]] = None) -> CognitiveOutput:
        """
        Analyze input rationally.

        Args:
            text: Input to analyze
            context: Additional context (from other cores, memory, etc.)

        Returns:
            CognitiveOutput with structured analysis
        """
        context = context or {}

        # 1. Analytical dissection (from TwinHelix)
        analysis = self._analytical_dissection(text)

        # 2. Apply modulation from other cores
        if self._modulation:
            analysis = self._apply_modulation(analysis, self._modulation)

        # 3. Determine proposed action
        proposed_action = self._derive_action(text, analysis, context)

        # 4. Build reasoning chain
        reasoning = self._build_reasoning_chain(text, analysis)

        # 5. Calculate confidence
        confidence = self._calculate_confidence(analysis, context)

        output = CognitiveOutput(
            analysis=analysis,
            proposed_action=proposed_action,
            confidence=confidence,
            focus=AnalysisFocus(analysis.get("logic_focus", "general")),
            entities=analysis.get("entities", []),
            reasoning_chain=reasoning,
        )

        self._history.append(output)
        return output

    def modulate(self, source: str, signal: Dict[str, float]):
        """
        Receive modulation signal from another core.

        The DNA helix interweaves - other cores affect cognitive processing.

        Args:
            source: Which core is modulating ("irrational", "paradox")
            signal: Modulation values (e.g., {"urgency": 0.8, "uncertainty": 0.5})
        """
        for key, value in signal.items():
            self._modulation[f"{source}.{key}"] = value

    def propose_goal(self,
                     available_planes: Set[str],
                     preferred_domain: Optional[GoalDomain] = None) -> Goal:
        """
        Use Dr. Zero infrastructure to propose a goal.

        Returns goal calibrated to current difficulty.
        """
        return self._proposer.propose(
            available_planes=available_planes,
            preferred_domain=preferred_domain,
        )

    def plan_goal(self,
                  goal: Goal,
                  available_planes: Set[str]) -> ExecutionPlan:
        """Create execution plan for goal."""
        return self._planner.plan(
            goal=goal,
            available_planes=available_planes,
        )

    def execute_plan(self,
                     plan: ExecutionPlan,
                     context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Execute plan and return result."""
        return self._executor.execute(
            plan=plan,
            context=context,
        )

    def _analytical_dissection(self, text: str) -> Dict[str, Any]:
        """
        Logic-focused breakdown of input.

        From TwinHelix: identifies intents, entities, and logical focus.
        """
        t = (text or "").strip().lower()

        # Detect intents
        intents: List[str] = []
        if any(k in t for k in ("how", "process", "steps", "procedure")):
            intents.append("procedural")
        if any(k in t for k in ("why", "reason", "because", "cause")):
            intents.append("causal")
        if any(k in t for k in ("compare", "vs", "difference", "between")):
            intents.append("comparative")
        if any(k in t for k in ("what is", "define", "structure", "parts")):
            intents.append("structural")

        # Extract entities (simple heuristic)
        tokens = [w.strip(".,!?\"'") for w in t.split()[:64]]
        entities = [w for w in tokens if w.isalpha() and len(w) > 3][:6]

        # Determine primary focus
        logic_focus = intents[0] if intents else "general"

        # Complexity estimate
        complexity = min(1.0, len(tokens) / 50)

        return {
            "intents": intents[:3],
            "entities": entities,
            "logic_focus": logic_focus,
            "complexity": complexity,
            "word_count": len(tokens),
            "has_question": "?" in text,
        }

    def _apply_modulation(self,
                          analysis: Dict[str, Any],
                          modulation: Dict[str, float]) -> Dict[str, Any]:
        """Apply modulation from other cores to analysis."""
        # Irrational core might increase urgency
        if modulation.get("irrational.urgency", 0) > 0.5:
            analysis["urgency_boost"] = modulation["irrational.urgency"]

        # Paradox core might flag contradictions
        if modulation.get("paradox.contradiction_strength", 0) > 0.3:
            analysis["contradiction_detected"] = True
            analysis["needs_synthesis"] = True

        # Irrational hunch might redirect focus
        if "irrational.hunch_domain" in modulation:
            analysis["hunch_override"] = modulation["irrational.hunch_domain"]

        return analysis

    def _derive_action(self,
                       text: str,
                       analysis: Dict[str, Any],
                       context: Dict[str, Any]) -> Optional[str]:
        """Derive proposed action from analysis - generate substantive thoughts."""
        focus = analysis.get("logic_focus", "general")
        entities = analysis.get("entities", [])
        entity_str = entities[0] if entities else "this"

        # Generate contextual thoughts instead of bare labels
        if focus == "procedural":
            return f"Consider the steps needed for {entity_str}... first understand, then plan, then act"
        elif focus == "causal":
            return f"Trace the causes behind {entity_str}... what led here? what follows?"
        elif focus == "comparative":
            return f"Weigh the options... what distinguishes {entity_str} from alternatives?"
        elif focus == "structural":
            return f"Examine the structure of {entity_str}... how do the parts relate?"
        elif analysis.get("has_question"):
            return f"A question surfaces about {entity_str}... seek understanding"
        else:
            # Rich idle thoughts based on context
            pain_levels = context.get("pain_levels", {})
            if any(v > 0.5 for v in pain_levels.values()):
                return "Something stirs beneath the surface... attend to it"
            elif context.get("affect", {}).get("arousal", 0.5) > 0.7:
                return "Energy flows... channel it toward purpose"
            else:
                return "Awareness persists... patterns forming in the quiet"

    def _build_reasoning_chain(self,
                               text: str,
                               analysis: Dict[str, Any]) -> List[str]:
        """Build explicit reasoning chain."""
        chain = []

        chain.append(f"Received input with {analysis.get('word_count', 0)} tokens")
        chain.append(f"Detected focus: {analysis.get('logic_focus', 'general')}")

        if analysis.get("entities"):
            chain.append(f"Key entities: {', '.join(analysis['entities'][:3])}")

        if analysis.get("intents"):
            chain.append(f"Intents: {', '.join(analysis['intents'])}")

        if analysis.get("contradiction_detected"):
            chain.append("Contradiction detected - synthesis needed")

        if analysis.get("hunch_override"):
            chain.append(f"Hunch override: {analysis['hunch_override']}")

        return chain

    def _calculate_confidence(self,
                              analysis: Dict[str, Any],
                              context: Dict[str, Any]) -> float:
        """Calculate confidence in analysis."""
        base = 0.7

        # More entities = more grounded
        if len(analysis.get("entities", [])) > 2:
            base += 0.1

        # Clear intent = more confident
        if analysis.get("logic_focus") != "general":
            base += 0.1

        # Contradiction = less confident
        if analysis.get("contradiction_detected"):
            base -= 0.2

        # Modulation from other cores
        if self._modulation.get("paradox.uncertainty", 0) > 0.5:
            base -= 0.1

        return max(0.1, min(0.95, base))

    def evaluate(self, option: str, focus: str) -> float:
        """
        Evaluate an option from logical perspective.

        This is the _logic_evaluator from TwinHelix.
        Used in helix decision-making.
        """
        keywords = option.lower().split()
        score = 1.0 if focus in keywords else 0.5

        if 'process' in focus:
            score += 0.2 if 'how' in keywords else 0.0

        if 'reason' in focus or 'why' in focus:
            score += 0.2 if 'because' in keywords else 0.0

        return float(score)

    def status(self) -> Dict[str, Any]:
        """Get core status."""
        return {
            "history_length": len(self._history),
            "active_modulations": list(self._modulation.keys()),
            "proposer": self._proposer.status(),
            "planner": self._planner.status(),
            "executor": self._executor.status(),
        }
