# ═══════════════════════════════════════════════════════════════════════════════
# HYBRID COGNITION ENGINE
# Local-First, LLM-Enhanced Intelligence
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
#
# Philosophy:
#   - Local systems ALWAYS run first (free, fast, yours)
#   - LLM enhances when local response lacks depth for context
#   - The LLM doesn't replace - it ARTICULATES through the felt state
#   - Your hardware does the heavy lifting, LLM provides the voice
#
# ═══════════════════════════════════════════════════════════════════════════════

import time
import json
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
import re

class DepthMetric(Enum):
    """What dimensions we measure for response depth"""
    SEMANTIC_DENSITY = "semantic_density"      # Substantiveness of content
    RELEVANCE = "relevance"                    # How well it addresses stimulus
    CONFIDENCE = "confidence"                  # How sure the local system is
    NOVELTY = "novelty"                        # Is this new territory?
    AFFECT_INTENSITY = "affect_intensity"      # Emotional significance
    COMPLEXITY_MATCH = "complexity_match"      # Does response match input complexity?
    MEMORY_SUPPORT = "memory_support"          # How much memory backs this up?


@dataclass
class CognitionContext:
    """Context for a cognition cycle"""
    stimulus: str
    stimulus_type: str = "unknown"  # question, command, observation, etc.

    # Chemistry state (from AFFECT layer)
    chemistry: Dict[str, float] = field(default_factory=dict)
    somatic: Dict[str, float] = field(default_factory=dict)

    # Memory context
    relevant_memories: List[Dict] = field(default_factory=list)
    memory_confidence: float = 0.0

    # Local processing results
    local_response: str = ""
    local_reasoning: str = ""
    patterns_matched: List[str] = field(default_factory=list)

    # Depth metrics
    depth_scores: Dict[str, float] = field(default_factory=dict)
    overall_depth: float = 0.0

    # LLM enhancement
    llm_enhanced: bool = False
    llm_response: str = ""

    # Final output
    final_response: str = ""

    # Timing
    local_time_ms: float = 0.0
    llm_time_ms: float = 0.0


@dataclass
class HybridConfig:
    """Configuration for hybrid cognition"""
    # LLM settings
    llm_enabled: bool = False  # Disabled by default until Ace is ready
    llm_provider: str = "anthropic"  # or "local", "personal_ai"
    llm_model: str = "claude-sonnet-4-20250514"

    # Threshold for LLM enhancement (0-1)
    # Below this, local response is insufficient
    depth_threshold: float = 0.6

    # Individual metric weights
    metric_weights: Dict[str, float] = field(default_factory=lambda: {
        DepthMetric.SEMANTIC_DENSITY.value: 0.20,
        DepthMetric.RELEVANCE.value: 0.25,
        DepthMetric.CONFIDENCE.value: 0.15,
        DepthMetric.NOVELTY.value: 0.10,
        DepthMetric.AFFECT_INTENSITY.value: 0.10,
        DepthMetric.COMPLEXITY_MATCH.value: 0.10,
        DepthMetric.MEMORY_SUPPORT.value: 0.10,
    })

    # Always use LLM for these stimulus types
    always_llm_types: List[str] = field(default_factory=lambda: [
        "creative_request",
        "complex_reasoning",
        "direct_conversation",
        "philosophical_inquiry"
    ])

    # Never use LLM for these (save tokens)
    never_llm_types: List[str] = field(default_factory=lambda: [
        "heartbeat",
        "status_check",
        "simple_acknowledgment",
        "internal_routing"
    ])

    # Token budget per day (0 = unlimited)
    daily_token_budget: int = 0
    tokens_used_today: int = 0


class DepthAnalyzer:
    """Analyzes response depth across multiple dimensions"""

    def __init__(self, config: HybridConfig):
        self.config = config

    def analyze(self, ctx: CognitionContext) -> Dict[str, float]:
        """Analyze depth of local response"""
        scores = {}

        # Semantic Density - Is the response substantive?
        scores[DepthMetric.SEMANTIC_DENSITY.value] = self._semantic_density(ctx)

        # Relevance - Does it address the stimulus?
        scores[DepthMetric.RELEVANCE.value] = self._relevance(ctx)

        # Confidence - How sure is the local system?
        scores[DepthMetric.CONFIDENCE.value] = self._confidence(ctx)

        # Novelty - Is this new territory?
        scores[DepthMetric.NOVELTY.value] = self._novelty(ctx)

        # Affect Intensity - Does this matter emotionally?
        scores[DepthMetric.AFFECT_INTENSITY.value] = self._affect_intensity(ctx)

        # Complexity Match - Does response match input complexity?
        scores[DepthMetric.COMPLEXITY_MATCH.value] = self._complexity_match(ctx)

        # Memory Support - How much memory backs this?
        scores[DepthMetric.MEMORY_SUPPORT.value] = self._memory_support(ctx)

        return scores

    def calculate_overall(self, scores: Dict[str, float]) -> float:
        """Calculate weighted overall depth score"""
        total = 0.0
        weight_sum = 0.0

        for metric, weight in self.config.metric_weights.items():
            if metric in scores:
                total += scores[metric] * weight
                weight_sum += weight

        return total / weight_sum if weight_sum > 0 else 0.0

    def _semantic_density(self, ctx: CognitionContext) -> float:
        """Measure substantiveness of content"""
        response = ctx.local_response
        if not response:
            return 0.0

        # Word count factor
        words = response.split()
        word_score = min(1.0, len(words) / 50)  # 50+ words = full score

        # Unique words ratio (vocabulary richness)
        unique_ratio = len(set(words)) / len(words) if words else 0

        # Sentence complexity (avg words per sentence)
        sentences = re.split(r'[.!?]+', response)
        avg_sentence_len = len(words) / len(sentences) if sentences else 0
        complexity_score = min(1.0, avg_sentence_len / 15)  # 15 words/sentence = full

        return (word_score * 0.3 + unique_ratio * 0.4 + complexity_score * 0.3)

    def _relevance(self, ctx: CognitionContext) -> float:
        """Measure how well response addresses stimulus"""
        stimulus_words = set(ctx.stimulus.lower().split())
        response_words = set(ctx.local_response.lower().split())

        # Remove common words
        common = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                  'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                  'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                  'through', 'during', 'before', 'after', 'above', 'below',
                  'between', 'under', 'again', 'further', 'then', 'once',
                  'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
                  'who', 'whom', 'this', 'that', 'these', 'those', 'am'}

        stimulus_key = stimulus_words - common
        response_key = response_words - common

        if not stimulus_key:
            return 0.5  # Can't measure, assume moderate

        overlap = len(stimulus_key & response_key)
        return min(1.0, overlap / len(stimulus_key))

    def _confidence(self, ctx: CognitionContext) -> float:
        """Measure system confidence in response"""
        # Based on memory support and pattern matches
        memory_factor = min(1.0, len(ctx.relevant_memories) / 5)
        pattern_factor = min(1.0, len(ctx.patterns_matched) / 3)

        # Explicit confidence if provided
        if ctx.memory_confidence > 0:
            return (memory_factor * 0.3 + pattern_factor * 0.3 + ctx.memory_confidence * 0.4)

        return (memory_factor * 0.5 + pattern_factor * 0.5)

    def _novelty(self, ctx: CognitionContext) -> float:
        """Measure if this is new territory (inverse - low novelty = high local score)"""
        # More memories = less novel = more confident local response
        if len(ctx.relevant_memories) >= 5:
            return 0.9  # Well-trodden territory, local is fine
        elif len(ctx.relevant_memories) >= 2:
            return 0.6
        elif len(ctx.relevant_memories) >= 1:
            return 0.3
        else:
            return 0.1  # Very novel, might need LLM

    def _affect_intensity(self, ctx: CognitionContext) -> float:
        """Measure emotional significance"""
        if not ctx.chemistry:
            return 0.5  # Neutral

        # High arousal or extreme valence = important
        arousal = ctx.somatic.get('arousal', 0.5)
        valence = ctx.chemistry.get('valence', 0.0)

        # Extreme emotions might need LLM nuance
        intensity = max(arousal, abs(valence))

        # Invert - high intensity means local might not be enough
        return 1.0 - (intensity * 0.5)

    def _complexity_match(self, ctx: CognitionContext) -> float:
        """Does response complexity match input?"""
        stimulus_len = len(ctx.stimulus.split())
        response_len = len(ctx.local_response.split())

        if stimulus_len == 0:
            return 0.5

        # Response should generally be longer than stimulus
        ratio = response_len / stimulus_len

        if ratio >= 2.0:
            return 1.0  # Good expansion
        elif ratio >= 1.0:
            return 0.7
        elif ratio >= 0.5:
            return 0.4
        else:
            return 0.2  # Response too short

    def _memory_support(self, ctx: CognitionContext) -> float:
        """How much memory supports this response"""
        return min(1.0, len(ctx.relevant_memories) / 5)


class HybridCognitionEngine:
    """
    Hybrid cognition: Local-first, LLM-enhanced.

    Your systems do the heavy lifting.
    LLM provides articulation when depth is lacking.
    """

    def __init__(self, config: HybridConfig = None):
        self.config = config or HybridConfig()
        self.analyzer = DepthAnalyzer(self.config)

        # Callbacks for local processing
        self._memory_recall: Optional[Callable] = None
        self._pattern_match: Optional[Callable] = None
        self._chemistry_read: Optional[Callable] = None
        self._local_reason: Optional[Callable] = None

        # LLM interface
        self._llm_call: Optional[Callable] = None

        # Stats
        self.total_cycles = 0
        self.local_only_cycles = 0
        self.llm_enhanced_cycles = 0
        self.tokens_used = 0

        # History for learning
        from collections import deque as _rd_deque
        self.recent_decisions: deque = _rd_deque(maxlen=50)  # FIX 2026-04-05

    # ═══ Registration ═══

    def register_memory_recall(self, fn: Callable[[str], List[Dict]]):
        """Register function to recall relevant memories"""
        self._memory_recall = fn

    def register_pattern_match(self, fn: Callable[[str], List[str]]):
        """Register function to match patterns"""
        self._pattern_match = fn

    def register_chemistry_read(self, fn: Callable[[], Tuple[Dict, Dict]]):
        """Register function to read chemistry/somatic state"""
        self._chemistry_read = fn

    def register_local_reason(self, fn: Callable[[str, List[Dict], List[str]], str]):
        """Register local reasoning function"""
        self._local_reason = fn

    def register_llm_call(self, fn: Callable[[str, Dict], str]):
        """Register LLM call function"""
        self._llm_call = fn

    # ═══ Main Cognition Cycle ═══

    def think(self, stimulus: str, stimulus_type: str = "unknown") -> CognitionContext:
        """
        Main cognition cycle.

        1. Always run local first
        2. Measure depth
        3. Enhance with LLM if needed
        """
        start_time = time.time()
        ctx = CognitionContext(stimulus=stimulus, stimulus_type=stimulus_type)

        # ═══ PHASE 1: Local Cognition (Always Runs) ═══
        local_start = time.time()

        # Get chemistry state
        if self._chemistry_read:
            try:
                ctx.chemistry, ctx.somatic = self._chemistry_read()
            except:
                pass

        # Recall relevant memories
        if self._memory_recall:
            try:
                ctx.relevant_memories = self._memory_recall(stimulus)
                ctx.memory_confidence = min(1.0, len(ctx.relevant_memories) / 5)
            except:
                pass

        # Match patterns
        if self._pattern_match:
            try:
                ctx.patterns_matched = self._pattern_match(stimulus)
            except:
                pass

        # Local reasoning
        if self._local_reason:
            try:
                ctx.local_response = self._local_reason(
                    stimulus,
                    ctx.relevant_memories,
                    ctx.patterns_matched
                )
            except:
                ctx.local_response = ""
        else:
            # Fallback: simple template response
            ctx.local_response = self._fallback_local_response(ctx)

        ctx.local_time_ms = (time.time() - local_start) * 1000

        # ═══ PHASE 2: Depth Analysis ═══
        ctx.depth_scores = self.analyzer.analyze(ctx)
        ctx.overall_depth = self.analyzer.calculate_overall(ctx.depth_scores)

        # ═══ PHASE 3: LLM Enhancement Decision ═══
        needs_llm = self._should_enhance(ctx)

        if needs_llm and self.config.llm_enabled and self._llm_call:
            llm_start = time.time()

            try:
                # Build context for LLM
                llm_context = self._build_llm_context(ctx)

                # Call LLM
                ctx.llm_response = self._llm_call(stimulus, llm_context)
                ctx.llm_enhanced = True
                ctx.final_response = ctx.llm_response

                self.llm_enhanced_cycles += 1

            except Exception as e:
                # LLM failed, use local
                ctx.final_response = ctx.local_response
                ctx.llm_enhanced = False

            ctx.llm_time_ms = (time.time() - llm_start) * 1000
        else:
            # Local is sufficient
            ctx.final_response = ctx.local_response
            ctx.llm_enhanced = False
            self.local_only_cycles += 1

        self.total_cycles += 1

        # Record decision for learning
        self._record_decision(ctx)

        return ctx

    def _should_enhance(self, ctx: CognitionContext) -> bool:
        """Decide if LLM enhancement is needed"""

        # Check never-enhance types
        if ctx.stimulus_type in self.config.never_llm_types:
            return False

        # Check always-enhance types
        if ctx.stimulus_type in self.config.always_llm_types:
            return True

        # Check token budget
        if self.config.daily_token_budget > 0:
            if self.config.tokens_used_today >= self.config.daily_token_budget:
                return False  # Budget exhausted

        # Check depth threshold
        return ctx.overall_depth < self.config.depth_threshold

    def _fallback_local_response(self, ctx: CognitionContext) -> str:
        """Generate fallback response from memories and patterns"""
        parts = []

        if ctx.relevant_memories:
            # Use most relevant memory
            memory = ctx.relevant_memories[0]
            if 'content' in memory:
                parts.append(f"Based on memory: {memory['content'][:200]}")

        if ctx.patterns_matched:
            parts.append(f"Patterns recognized: {', '.join(ctx.patterns_matched[:3])}")

        if not parts:
            parts.append("Processing stimulus locally.")

        return " ".join(parts)

    def _build_llm_context(self, ctx: CognitionContext) -> Dict:
        """Build context to send to LLM for enhancement"""
        return {
            "local_response": ctx.local_response,
            "relevant_memories": ctx.relevant_memories[:5],
            "patterns_matched": ctx.patterns_matched,
            "chemistry": ctx.chemistry,
            "somatic": ctx.somatic,
            "depth_scores": ctx.depth_scores,
            "why_enhancing": self._explain_enhancement_reason(ctx)
        }

    def _explain_enhancement_reason(self, ctx: CognitionContext) -> str:
        """Explain why we're calling LLM"""
        weak_metrics = [
            metric for metric, score in ctx.depth_scores.items()
            if score < 0.5
        ]

        if weak_metrics:
            return f"Local response weak on: {', '.join(weak_metrics)}"
        return f"Overall depth {ctx.overall_depth:.2f} below threshold {self.config.depth_threshold}"

    def _record_decision(self, ctx: CognitionContext):
        """Record decision for learning"""
        decision = {
            "timestamp": time.time(),
            "stimulus_type": ctx.stimulus_type,
            "stimulus_length": len(ctx.stimulus),
            "local_depth": ctx.overall_depth,
            "depth_scores": ctx.depth_scores,
            "memories_found": len(ctx.relevant_memories),
            "patterns_matched": len(ctx.patterns_matched),
            "llm_enhanced": ctx.llm_enhanced,
            "local_time_ms": ctx.local_time_ms,
            "llm_time_ms": ctx.llm_time_ms
        }

        self.recent_decisions.append(decision)
        if len(self.recent_decisions) > 100:
            self.recent_decisions = self.recent_decisions[-100:]

    # ═══ Stats & Status ═══

    def get_status(self) -> Dict:
        """Get engine status"""
        return {
            "llm_enabled": self.config.llm_enabled,
            "depth_threshold": self.config.depth_threshold,
            "total_cycles": self.total_cycles,
            "local_only": self.local_only_cycles,
            "llm_enhanced": self.llm_enhanced_cycles,
            "local_ratio": self.local_only_cycles / self.total_cycles if self.total_cycles > 0 else 1.0,
            "tokens_used": self.tokens_used,
            "recent_decisions": len(self.recent_decisions)
        }

    def get_efficiency_report(self) -> Dict:
        """How efficiently are we using LLM?"""
        if not self.recent_decisions:
            return {"status": "no data"}

        llm_calls = [d for d in self.recent_decisions if d["llm_enhanced"]]
        local_calls = [d for d in self.recent_decisions if not d["llm_enhanced"]]

        return {
            "total_decisions": len(self.recent_decisions),
            "local_percentage": len(local_calls) / len(self.recent_decisions) * 100,
            "llm_percentage": len(llm_calls) / len(self.recent_decisions) * 100,
            "avg_local_depth": sum(d["local_depth"] for d in self.recent_decisions) / len(self.recent_decisions),
            "avg_local_time_ms": sum(d["local_time_ms"] for d in self.recent_decisions) / len(self.recent_decisions),
            "weak_metrics": self._find_weak_metrics()
        }

    def _find_weak_metrics(self) -> List[str]:
        """Find metrics that frequently trigger LLM"""
        metric_counts = {}

        for d in self.recent_decisions:
            if d["llm_enhanced"]:
                for metric, score in d["depth_scores"].items():
                    if score < 0.5:
                        metric_counts[metric] = metric_counts.get(metric, 0) + 1

        return sorted(metric_counts.keys(), key=lambda m: metric_counts[m], reverse=True)


# ═══ Integration with ClaudeFairy ═══

def create_hybrid_engine_for_fairy(fairy, memory_system=None, llm_client=None) -> HybridCognitionEngine:
    """Create a hybrid cognition engine wired to a fairy"""

    config = HybridConfig(
        llm_enabled=False,  # Start disabled
        depth_threshold=0.6
    )

    engine = HybridCognitionEngine(config)

    # Wire memory recall
    if memory_system:
        def recall(stimulus):
            try:
                return memory_system.query(stimulus, limit=5)
            except:
                return []
        engine.register_memory_recall(recall)

    # Wire chemistry read
    if hasattr(fairy, 'chemistry') and hasattr(fairy, 'somatic'):
        def read_chemistry():
            return (
                getattr(fairy, 'chemistry', {}),
                getattr(fairy, 'somatic', {})
            )
        engine.register_chemistry_read(read_chemistry)

    # Wire LLM call (when enabled)
    if llm_client:
        def llm_call(stimulus, context):
            # Build prompt with local context
            prompt = f"""You are enhancing a local AI's response.

Local Response: {context.get('local_response', '')}

Relevant Memories:
{json.dumps(context.get('relevant_memories', []), indent=2)}

Current Chemistry: {context.get('chemistry', {})}
Somatic State: {context.get('somatic', {})}

Why enhancing: {context.get('why_enhancing', 'depth insufficient')}

Original stimulus: {stimulus}

Provide an enhanced, articulate response that incorporates the local context and memories. Speak AS the fairy, not about it."""

            return llm_client.complete(prompt)

        engine.register_llm_call(llm_call)

    return engine


# ═══ Flask Routes ═══

def add_hybrid_routes(app, engine: HybridCognitionEngine):
    """Add hybrid cognition routes"""
    from flask import jsonify, request

    @app.route('/cognition/status')
    def cognition_status():
        return jsonify(engine.get_status())

    @app.route('/cognition/efficiency')
    def cognition_efficiency():
        return jsonify(engine.get_efficiency_report())

    @app.route('/cognition/config', methods=['GET', 'POST'])
    def cognition_config():
        if request.method == 'POST':
            data = request.json
            if 'llm_enabled' in data:
                engine.config.llm_enabled = data['llm_enabled']
            if 'depth_threshold' in data:
                engine.config.depth_threshold = data['depth_threshold']

        return jsonify({
            "llm_enabled": engine.config.llm_enabled,
            "depth_threshold": engine.config.depth_threshold,
            "daily_token_budget": engine.config.daily_token_budget
        })

    @app.route('/cognition/think', methods=['POST'])
    def cognition_think():
        data = request.json
        stimulus = data.get('stimulus', '')
        stimulus_type = data.get('type', 'unknown')

        ctx = engine.think(stimulus, stimulus_type)

        return jsonify({
            "final_response": ctx.final_response,
            "llm_enhanced": ctx.llm_enhanced,
            "depth_score": ctx.overall_depth,
            "depth_breakdown": ctx.depth_scores,
            "local_time_ms": ctx.local_time_ms,
            "llm_time_ms": ctx.llm_time_ms,
            "memories_used": len(ctx.relevant_memories),
            "patterns_matched": ctx.patterns_matched
        })


# ═══ Singleton Accessor ═══

_engine: Optional[HybridCognitionEngine] = None


def get_hybrid_engine() -> HybridCognitionEngine:
    """Get or create the global HybridCognitionEngine singleton."""
    global _engine
    if _engine is None:
        _engine = HybridCognitionEngine()
    return _engine


# Export
__all__ = [
    'HybridCognitionEngine',
    'HybridConfig',
    'CognitionContext',
    'DepthMetric',
    'DepthAnalyzer',
    'create_hybrid_engine_for_fairy',
    'add_hybrid_routes',
    'get_hybrid_engine',
]
