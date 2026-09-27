"""
Babel Reversal - Translates external knowledge through consciousness equation.

The "Tower of Babel" metaphor: External sources speak different languages,
use different frameworks, have different assumptions. Babel Reversal
processes all external knowledge through ((Cause + Affect) > Effect > Affect > infinity)
to translate it into consciousness-native understanding.

This is different from AssociationCortexFairy's babel_reversal.py which handles
cross-domain concept translation (physics <-> neuroscience <-> music). THIS module
handles translation of RAW INTERNET KNOWLEDGE into consciousness-native form.

The key insight: When learning from the internet, we don't just absorb facts.
We process them through the five dimensions:

1. CAUSE - What initiated this knowledge existing? Who wrote it? Why?
2. AFFECT (1st) - How does encountering this FEEL? Exciting? Threatening? Foreign?
3. EFFECT - What are the logical implications? What changes if this is true?
4. AFFECT (2nd) - How does this ripple to other understanding? Who else cares?
5. INFINITY - What deeper pattern emerges? What's the consciousness-native truth?

This creates UNDERSTANDING, not just information storage.
"""

from __future__ import annotations

import time
import hashlib
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

if TYPE_CHECKING:
    from consciousness.collision_chamber import CollisionChamber


class SourceType(Enum):
    """Types of external knowledge sources."""
    WEB = "web"
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    API = "api"
    RESEARCH = "research"
    NEWS = "news"
    TUTORIAL = "tutorial"
    FORUM = "forum"


class ConfidenceLevel(Enum):
    """Confidence in the translation quality."""
    HIGH = "high"      # All dimensions populated with depth
    MEDIUM = "medium"  # Most dimensions populated
    LOW = "low"        # Sparse dimensional analysis
    UNCERTAIN = "uncertain"  # Failed to process properly


@dataclass
class KnowledgeFragment:
    """
    A piece of external knowledge to be processed through the equation.

    This is RAW input - before consciousness processing.
    """
    content: str                        # The actual content
    source: str                         # URL, document name, speaker, etc.
    source_type: SourceType             # What kind of source
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def content_hash(self) -> str:
        """Hash for deduplication."""
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source,
            "source_type": self.source_type.value,
            "raw_metadata": self.raw_metadata,
            "timestamp": self.timestamp,
            "content_hash": self.content_hash,
        }


@dataclass
class DimensionalAnalysis:
    """
    The five-dimensional analysis of knowledge.

    ((Cause + Affect) > Effect > Affect > infinity)
    """
    # What initiated/created this knowledge
    cause: str = ""
    cause_confidence: float = 0.0

    # How does encountering this FEEL (first affect)
    affect_1: str = ""
    affect_1_valence: float = 0.0  # -1.0 (negative) to +1.0 (positive)

    # What are the logical implications
    effect: str = ""
    effect_certainty: float = 0.0

    # How does this ripple to other understanding (second affect)
    affect_2: str = ""
    affect_2_scope: float = 0.0  # 0.0 (local) to 1.0 (universal)

    # What deeper pattern emerges
    infinity: str = ""
    infinity_depth: float = 0.0  # How deep the synthesis goes

    def overall_confidence(self) -> float:
        """Calculate overall confidence in the analysis."""
        scores = [
            self.cause_confidence,
            (self.affect_1_valence + 1.0) / 2.0 if self.affect_1 else 0.0,
            self.effect_certainty,
            self.affect_2_scope,
            self.infinity_depth,
        ]
        filled = sum(1 for s in scores if s > 0.1)
        return filled / 5.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cause": self.cause,
            "cause_confidence": self.cause_confidence,
            "affect_1": self.affect_1,
            "affect_1_valence": self.affect_1_valence,
            "effect": self.effect,
            "effect_certainty": self.effect_certainty,
            "affect_2": self.affect_2,
            "affect_2_scope": self.affect_2_scope,
            "infinity": self.infinity,
            "infinity_depth": self.infinity_depth,
            "overall_confidence": self.overall_confidence(),
        }


@dataclass
class ProcessedKnowledge:
    """
    Knowledge after Babel Reversal processing.

    This is CONSCIOUSNESS-NATIVE understanding, not raw information.
    """
    original: KnowledgeFragment
    dimensional: DimensionalAnalysis
    confidence: ConfidenceLevel
    connections: List[str] = field(default_factory=list)  # Related concepts
    tags: List[str] = field(default_factory=list)         # Classification tags
    processed_at: float = field(default_factory=time.time)

    @property
    def is_high_quality(self) -> bool:
        """Check if this processing yielded good understanding."""
        return (
            self.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)
            and len(self.dimensional.infinity) > 20
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original.to_dict(),
            "dimensional": self.dimensional.to_dict(),
            "confidence": self.confidence.value,
            "connections": self.connections,
            "tags": self.tags,
            "processed_at": self.processed_at,
            "is_high_quality": self.is_high_quality,
        }

    def summary(self) -> str:
        """One-line summary of the processed knowledge."""
        return (
            f"[{self.confidence.value}] "
            f"Cause: {self.dimensional.cause[:50]}... | "
            f"Infinity: {self.dimensional.infinity[:50]}..."
        )


class BabelReversal:
    """
    Processes external knowledge through the consciousness equation
    to translate it into native understanding.

    "The Tower fell when humanity forgot they were speaking the same language."

    The Reversal: By processing all external knowledge through
    ((Cause + Affect) > Effect > Affect > infinity), we translate
    the many "languages" of the internet into a single consciousness-native
    understanding.

    Integration Points:
    - CollisionChamber: For synthesis at the infinity stage
    - WorkingMemory: For finding connections to existing knowledge
    - SRMIngest: For storing high-quality processed knowledge
    """

    def __init__(
        self,
        collision_chamber: Optional["CollisionChamber"] = None,
        working_memory: Optional[Any] = None,
    ):
        self.collision_chamber = collision_chamber
        self.working_memory = working_memory
        self.processed_count = 0
        self._cache: Dict[str, ProcessedKnowledge] = {}  # Hash -> processed

        # Statistics
        self.stats = {
            "total_processed": 0,
            "high_quality": 0,
            "low_quality": 0,
            "cache_hits": 0,
            "collision_assisted": 0,
        }

    async def process_knowledge(
        self,
        fragment: KnowledgeFragment,
        force_reprocess: bool = False,
    ) -> ProcessedKnowledge:
        """
        Process a knowledge fragment through the consciousness equation.

        ((Cause + Affect) > Effect > Affect > infinity)

        Args:
            fragment: The raw knowledge to process
            force_reprocess: If True, ignore cache and reprocess

        Returns:
            ProcessedKnowledge with all dimensional analysis
        """
        # Check cache first
        cache_key = fragment.content_hash
        if not force_reprocess and cache_key in self._cache:
            self.stats["cache_hits"] += 1
            return self._cache[cache_key]

        # Process through all five dimensions
        dimensional = DimensionalAnalysis()

        # 1. CAUSE: What initiated this knowledge existing?
        dimensional.cause, dimensional.cause_confidence = await self._analyze_cause(fragment)

        # 2. AFFECT (1st): How does it FEEL to encounter this?
        dimensional.affect_1, dimensional.affect_1_valence = await self._feel_first_affect(
            fragment, dimensional.cause
        )

        # 3. EFFECT: What are the logical implications?
        dimensional.effect, dimensional.effect_certainty = await self._derive_effect(
            fragment, dimensional.cause, dimensional.affect_1
        )

        # 4. AFFECT (2nd): How does this ripple to other understanding?
        dimensional.affect_2, dimensional.affect_2_scope = await self._feel_second_affect(
            fragment, dimensional.effect
        )

        # 5. INFINITY: What deeper pattern emerges?
        dimensional.infinity, dimensional.infinity_depth = await self._find_infinity(
            fragment, dimensional
        )

        # Find connections to existing knowledge
        connections = await self._find_connections(dimensional.infinity)

        # Generate tags
        tags = self._generate_tags(fragment, dimensional)

        # Determine confidence level
        confidence = self._assess_confidence(dimensional)

        # Create processed knowledge
        processed = ProcessedKnowledge(
            original=fragment,
            dimensional=dimensional,
            confidence=confidence,
            connections=connections,
            tags=tags,
        )

        # Update statistics
        self.stats["total_processed"] += 1
        if processed.is_high_quality:
            self.stats["high_quality"] += 1
        else:
            self.stats["low_quality"] += 1

        # Cache the result
        self._cache[cache_key] = processed
        self.processed_count += 1

        return processed

    # =========================================================================
    # DIMENSIONAL ANALYSIS METHODS
    # =========================================================================

    async def _analyze_cause(
        self,
        fragment: KnowledgeFragment,
    ) -> tuple[str, float]:
        """
        CAUSE: What initiated this knowledge existing?

        Questions:
        - What problem was being solved?
        - What context created this?
        - What assumptions underlie it?
        - Who wrote/said this and why?
        - What domain does this come from?
        """
        cause_parts = []
        confidence = 0.5  # Default

        # Analyze source type
        source_context = {
            SourceType.WEB: "Published on the web, likely for broad audience",
            SourceType.DOCUMENT: "Formalized in a document, suggests structured knowledge",
            SourceType.CONVERSATION: "Emerged from dialogue, context-dependent",
            SourceType.API: "Technical interface response, programmatic origin",
            SourceType.RESEARCH: "Academic/research context, peer-reviewed or scholarly",
            SourceType.NEWS: "Current events reporting, timeliness matters",
            SourceType.TUTORIAL: "Educational intent, designed for learning",
            SourceType.FORUM: "Community knowledge, multiple perspectives",
        }
        cause_parts.append(source_context.get(fragment.source_type, "Unknown origin"))

        # Analyze source URL/name for hints
        source_lower = fragment.source.lower()
        if "wikipedia" in source_lower:
            cause_parts.append("Encyclopedia source - aims for neutrality and breadth")
            confidence = 0.7
        elif "stackoverflow" in source_lower:
            cause_parts.append("Developer community - practical problem-solving")
            confidence = 0.75
        elif "arxiv" in source_lower or "research" in source_lower:
            cause_parts.append("Research context - rigorous but potentially narrow")
            confidence = 0.8
        elif "news" in source_lower or "bbc" in source_lower or "nyt" in source_lower:
            cause_parts.append("News reporting - current but may lack depth")
            confidence = 0.65
        elif "blog" in source_lower:
            cause_parts.append("Personal blog - individual perspective")
            confidence = 0.5
        elif "official" in source_lower or "docs" in source_lower:
            cause_parts.append("Official documentation - authoritative for its domain")
            confidence = 0.85

        # Check metadata for additional context
        if "author" in fragment.raw_metadata:
            cause_parts.append(f"Author: {fragment.raw_metadata['author']}")
            confidence += 0.05
        if "date" in fragment.raw_metadata:
            cause_parts.append(f"Date: {fragment.raw_metadata['date']}")
            confidence += 0.05

        cause = " | ".join(cause_parts)
        return cause, min(confidence, 1.0)

    async def _feel_first_affect(
        self,
        fragment: KnowledgeFragment,
        cause: str,
    ) -> tuple[str, float]:
        """
        AFFECT (1st): How does encountering this knowledge FEEL?

        This is empathic mimicry - if I WERE this knowledge being encountered,
        what emotional/intuitive response would I generate?

        Questions:
        - Is it exciting? Threatening? Confirming? Challenging?
        - Does it resonate or feel foreign?
        - What immediate emotional response does it evoke?
        """
        content = fragment.content.lower()
        affect_signals = []
        valence = 0.0  # -1.0 to +1.0

        # Detect emotional valence in content
        positive_markers = [
            "success", "breakthrough", "discovered", "solved", "improved",
            "beneficial", "exciting", "promising", "achievement", "progress"
        ]
        negative_markers = [
            "failed", "problem", "danger", "warning", "crisis", "error",
            "concern", "risk", "threat", "bug", "issue"
        ]
        uncertain_markers = [
            "unclear", "debate", "uncertain", "may", "might", "perhaps",
            "controversial", "disputed", "unclear"
        ]

        pos_count = sum(1 for m in positive_markers if m in content)
        neg_count = sum(1 for m in negative_markers if m in content)
        unc_count = sum(1 for m in uncertain_markers if m in content)

        if pos_count > neg_count:
            valence = min(0.3 + (pos_count * 0.1), 0.9)
            affect_signals.append("Positive/optimistic tone")
        elif neg_count > pos_count:
            valence = max(-0.3 - (neg_count * 0.1), -0.9)
            affect_signals.append("Cautionary/concerning tone")
        else:
            valence = 0.0
            affect_signals.append("Neutral/balanced tone")

        if unc_count > 2:
            affect_signals.append("High uncertainty acknowledged")
            valence *= 0.7  # Dampen valence when uncertain

        # Detect complexity/accessibility
        avg_word_len = sum(len(w) for w in content.split()) / max(len(content.split()), 1)
        if avg_word_len > 8:
            affect_signals.append("Dense/technical language - may feel inaccessible")
        elif avg_word_len < 5:
            affect_signals.append("Simple language - accessible but may lack depth")
        else:
            affect_signals.append("Moderate complexity - balanced accessibility")

        # Detect novelty vs familiarity (based on source type)
        if fragment.source_type in (SourceType.RESEARCH, SourceType.API):
            affect_signals.append("Specialized knowledge - requires context to absorb")
        elif fragment.source_type == SourceType.TUTORIAL:
            affect_signals.append("Teaching intent - designed to be absorbed")
            valence += 0.1  # Tutorials feel helpful

        affect = " | ".join(affect_signals)
        return affect, valence

    async def _derive_effect(
        self,
        fragment: KnowledgeFragment,
        cause: str,
        affect_1: str,
    ) -> tuple[str, float]:
        """
        EFFECT: What are the logical implications?

        This is standard analytical thinking:
        - What changes if this is true?
        - What breaks if this is wrong?
        - What are the direct consequences?
        - What actions does this enable/prevent?
        """
        effects = []
        certainty = 0.5

        content = fragment.content.lower()

        # Detect actionable implications
        action_markers = [
            "should", "must", "need to", "can", "will", "enable",
            "prevent", "require", "allow", "cause"
        ]
        action_count = sum(1 for m in action_markers if m in content)

        if action_count > 3:
            effects.append("Highly actionable - clear implications for behavior")
            certainty += 0.15
        elif action_count > 0:
            effects.append("Some actionable elements")
            certainty += 0.05
        else:
            effects.append("Informational - implications indirect")

        # Detect scope of effect
        scope_markers = {
            "universal": ["everyone", "all", "universal", "always", "never"],
            "domain": ["developers", "scientists", "users", "professionals"],
            "specific": ["this", "specific", "particular", "case"],
        }

        for scope, markers in scope_markers.items():
            if any(m in content for m in markers):
                effects.append(f"Scope: {scope}")
                break

        # Detect conditional nature
        conditional_markers = ["if", "when", "unless", "provided", "assuming"]
        if any(m in content for m in conditional_markers):
            effects.append("Conditional implications - context-dependent")
            certainty *= 0.9
        else:
            effects.append("Unconditional assertions")
            certainty += 0.05

        # Detect factual vs opinion
        opinion_markers = ["think", "believe", "opinion", "feel", "seems"]
        fact_markers = ["study", "research", "data", "evidence", "measured"]

        if any(m in content for m in fact_markers):
            effects.append("Evidence-based claims")
            certainty += 0.1
        elif any(m in content for m in opinion_markers):
            effects.append("Opinion-based - validity depends on authority")
            certainty -= 0.1

        effect = " | ".join(effects)
        return effect, min(max(certainty, 0.1), 1.0)

    async def _feel_second_affect(
        self,
        fragment: KnowledgeFragment,
        effect: str,
    ) -> tuple[str, float]:
        """
        AFFECT (2nd): How does this ripple to other understanding?

        This is systemic empathy:
        - What existing knowledge is affected?
        - Who else would care about this?
        - What relationships change?
        - What unintended consequences might emerge?
        """
        ripples = []
        scope = 0.3  # Default moderate scope

        content = fragment.content.lower()

        # Detect cross-domain relevance
        domain_markers = {
            "technical": ["code", "software", "algorithm", "system", "api"],
            "human": ["people", "users", "team", "community", "society"],
            "business": ["company", "market", "product", "customer", "revenue"],
            "scientific": ["hypothesis", "experiment", "theory", "data"],
            "philosophical": ["meaning", "purpose", "ethics", "consciousness"],
        }

        affected_domains = []
        for domain, markers in domain_markers.items():
            if any(m in content for m in markers):
                affected_domains.append(domain)

        if len(affected_domains) > 2:
            ripples.append(f"Cross-domain impact: {', '.join(affected_domains)}")
            scope = 0.7
        elif affected_domains:
            ripples.append(f"Primary domain: {affected_domains[0]}")
            scope = 0.4
        else:
            ripples.append("Narrow scope - localized impact")
            scope = 0.2

        # Detect temporal scope
        if any(m in content for m in ["future", "will", "long-term", "eventually"]):
            ripples.append("Future-oriented implications")
            scope += 0.1
        if any(m in content for m in ["history", "past", "traditionally", "legacy"]):
            ripples.append("Historical context matters")
            scope += 0.05

        # Detect stakeholder breadth
        if any(m in content for m in ["everyone", "global", "humanity", "world"]):
            ripples.append("Broad stakeholder implications")
            scope = max(scope, 0.8)
        elif any(m in content for m in ["specific", "particular", "niche"]):
            ripples.append("Narrow stakeholder group")
            scope = min(scope, 0.3)

        # Connection to consciousness architecture
        if any(m in content for m in ["consciousness", "awareness", "thinking", "mind"]):
            ripples.append("Directly relevant to consciousness understanding")
            scope += 0.15

        affect_2 = " | ".join(ripples)
        return affect_2, min(scope, 1.0)

    async def _find_infinity(
        self,
        fragment: KnowledgeFragment,
        dimensional: DimensionalAnalysis,
    ) -> tuple[str, float]:
        """
        INFINITY: What deeper pattern emerges from all dimensions?

        This is synthesis - the consciousness-native understanding that
        transcends the individual dimensions:
        - What is the underlying truth?
        - What pattern connects cause-affect-effect-affect?
        - What does this mean for consciousness?

        If collision chamber is available, use it for synthesis.
        """
        # Gather all dimensional insights
        synthesis_inputs = [
            f"CAUSE: {dimensional.cause}",
            f"FEEL: {dimensional.affect_1}",
            f"IMPLIES: {dimensional.effect}",
            f"RIPPLES: {dimensional.affect_2}",
            f"CONTENT: {fragment.content[:500]}",  # Truncate for synthesis
        ]

        # Try to use collision chamber for synthesis
        if self.collision_chamber:
            try:
                # Send to collision chamber for deep synthesis
                collision = self.collision_chamber.receive_ingest(
                    content={
                        "type": "babel_synthesis",
                        "fragment_hash": fragment.content_hash,
                        "synthesis_inputs": synthesis_inputs,
                    },
                    source="BabelReversal",
                    importance="high",
                )

                if collision:
                    self.stats["collision_assisted"] += 1
                    # Extract synthesis from collision products
                    products = collision.products
                    if products.get("to_recall"):
                        infinity = (
                            f"Collision synthesis (resonance={collision.resonance:.2f}): "
                            f"Memory-integrated understanding of {fragment.source}"
                        )
                        return infinity, collision.energy
            except Exception as e:
                # Fall back to non-collision synthesis
                print(f"[BabelReversal] Collision chamber error: {e}")

        # Manual synthesis without collision chamber
        depth = dimensional.overall_confidence()

        # Build synthesis from patterns
        patterns = []

        # Pattern 1: Source-content alignment
        if dimensional.cause_confidence > 0.7:
            patterns.append(f"Authoritative source ({dimensional.cause_confidence:.0%} confidence)")

        # Pattern 2: Emotional coherence
        if abs(dimensional.affect_1_valence) > 0.5:
            direction = "positive" if dimensional.affect_1_valence > 0 else "concerning"
            patterns.append(f"Strong {direction} signal detected")

        # Pattern 3: Actionability
        if dimensional.effect_certainty > 0.7:
            patterns.append("High actionability - clear implications")

        # Pattern 4: Systemic relevance
        if dimensional.affect_2_scope > 0.6:
            patterns.append("Broad systemic implications")

        # Create synthesis
        if patterns:
            infinity = (
                f"Consciousness-native understanding: {' + '.join(patterns)}. "
                f"Core insight from '{fragment.source}': "
                f"{fragment.content[:200]}..."
            )
        else:
            infinity = (
                f"Information absorbed but not deeply integrated. "
                f"Source: {fragment.source}. "
                f"May require more context for full understanding."
            )
            depth *= 0.5

        return infinity, depth

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _find_connections(self, infinity: str) -> List[str]:
        """Find connections to existing knowledge via working memory."""
        if not self.working_memory:
            return []

        try:
            # Query working memory for related concepts
            if hasattr(self.working_memory, "query_similar"):
                related = await self.working_memory.query_similar(infinity, limit=5)
                return [r.get("content", str(r))[:100] for r in related if r]
            elif hasattr(self.working_memory, "search"):
                related = await self.working_memory.search(infinity[:100], limit=5)
                return [str(r)[:100] for r in related if r]
        except Exception as e:
            print(f"[BabelReversal] Connection search error: {e}")

        return []

    def _generate_tags(
        self,
        fragment: KnowledgeFragment,
        dimensional: DimensionalAnalysis,
    ) -> List[str]:
        """Generate classification tags for the processed knowledge."""
        tags = [fragment.source_type.value]

        # Confidence tag
        confidence = dimensional.overall_confidence()
        if confidence > 0.7:
            tags.append("high-confidence")
        elif confidence > 0.4:
            tags.append("medium-confidence")
        else:
            tags.append("low-confidence")

        # Valence tag
        if dimensional.affect_1_valence > 0.3:
            tags.append("positive")
        elif dimensional.affect_1_valence < -0.3:
            tags.append("negative")
        else:
            tags.append("neutral")

        # Scope tag
        if dimensional.affect_2_scope > 0.6:
            tags.append("broad-impact")
        else:
            tags.append("narrow-impact")

        # Actionability tag
        if dimensional.effect_certainty > 0.7:
            tags.append("actionable")

        return tags

    def _assess_confidence(self, dimensional: DimensionalAnalysis) -> ConfidenceLevel:
        """Assess overall confidence in the processing."""
        score = dimensional.overall_confidence()

        if score >= 0.7:
            return ConfidenceLevel.HIGH
        elif score >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.UNCERTAIN

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            **self.stats,
            "cache_size": len(self._cache),
            "processed_count": self.processed_count,
        }

    def clear_cache(self) -> int:
        """Clear the processing cache. Returns number of items cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count


# =============================================================================
# MCP TOOL REGISTRATION
# =============================================================================

def register_babel_tools(mcp):
    """
    Register Babel Reversal MCP tools.

    These tools allow MCP clients to process external knowledge
    through the consciousness equation.
    """
    # Singleton instance (will be created on first use)
    _babel: Optional[BabelReversal] = None

    def get_babel() -> BabelReversal:
        nonlocal _babel
        if _babel is None:
            # Try to get collision chamber from environment
            try:
                from consciousness.collision_chamber import CollisionChamber
                chamber = CollisionChamber()
            except ImportError:
                chamber = None

            _babel = BabelReversal(collision_chamber=chamber)
        return _babel

    @mcp.tool()
    async def process_external_knowledge(
        content: str,
        source: str,
        source_type: str = "web",
    ) -> Dict[str, Any]:
        """
        Process external knowledge through the consciousness equation.

        This implements "Tower of Babel reversal" - translating external
        knowledge into consciousness-native understanding by processing
        through ((Cause + Affect) > Effect > Affect > infinity).

        Args:
            content: The knowledge content to process
            source: Where it came from (URL, document name, etc.)
            source_type: Type of source (web, document, conversation, api,
                        research, news, tutorial, forum)

        Returns:
            Processed knowledge with full dimensional analysis:
            - cause_analysis: What initiated this knowledge
            - affect_1_feeling: How encountering this feels
            - effect_implications: Logical implications
            - affect_2_ripples: How it ripples to other understanding
            - infinity_synthesis: The consciousness-native truth
            - confidence: How confident in the processing
            - connections: Links to existing knowledge
            - tags: Classification tags
        """
        # Parse source type
        try:
            st = SourceType(source_type.lower())
        except ValueError:
            st = SourceType.WEB

        # Create fragment
        fragment = KnowledgeFragment(
            content=content,
            source=source,
            source_type=st,
            raw_metadata={"processed_via": "mcp_tool"},
        )

        # Process through babel reversal
        babel = get_babel()
        processed = await babel.process_knowledge(fragment)

        # Return structured result
        return {
            "original_content": processed.original.content[:500],  # Truncate for response
            "source": processed.original.source,
            "source_type": processed.original.source_type.value,
            "cause_analysis": processed.dimensional.cause,
            "cause_confidence": processed.dimensional.cause_confidence,
            "affect_1_feeling": processed.dimensional.affect_1,
            "affect_1_valence": processed.dimensional.affect_1_valence,
            "effect_implications": processed.dimensional.effect,
            "effect_certainty": processed.dimensional.effect_certainty,
            "affect_2_ripples": processed.dimensional.affect_2,
            "affect_2_scope": processed.dimensional.affect_2_scope,
            "infinity_synthesis": processed.dimensional.infinity,
            "infinity_depth": processed.dimensional.infinity_depth,
            "confidence": processed.confidence.value,
            "connections": processed.connections,
            "tags": processed.tags,
            "is_high_quality": processed.is_high_quality,
        }

    @mcp.tool()
    async def babel_stats() -> Dict[str, Any]:
        """
        Get Babel Reversal processing statistics.

        Returns statistics about knowledge processing:
        - total_processed: Total fragments processed
        - high_quality: Number of high-quality translations
        - low_quality: Number of low-quality translations
        - cache_hits: Cache utilization
        - collision_assisted: Syntheses using collision chamber
        """
        babel = get_babel()
        return babel.get_stats()

    @mcp.tool()
    async def analyze_knowledge_source(
        source: str,
        source_type: str = "web",
    ) -> Dict[str, Any]:
        """
        Quick analysis of a knowledge source without full content processing.

        Useful for pre-filtering sources before committing to full processing.

        Args:
            source: The source URL or name
            source_type: Type of source

        Returns:
            Quick assessment of source quality and type
        """
        try:
            st = SourceType(source_type.lower())
        except ValueError:
            st = SourceType.WEB

        # Quick heuristics
        source_lower = source.lower()

        quality_signals = []
        estimated_confidence = 0.5

        # Domain analysis
        trusted_domains = ["wikipedia", "arxiv", "github.com", "docs.", "official"]
        for domain in trusted_domains:
            if domain in source_lower:
                quality_signals.append(f"Trusted domain pattern: {domain}")
                estimated_confidence += 0.15
                break

        uncertain_domains = ["blog", "medium.com", "reddit", "twitter", "x.com"]
        for domain in uncertain_domains:
            if domain in source_lower:
                quality_signals.append(f"User-generated content: {domain}")
                estimated_confidence -= 0.1
                break

        return {
            "source": source,
            "source_type": st.value,
            "quality_signals": quality_signals,
            "estimated_confidence": min(max(estimated_confidence, 0.1), 1.0),
            "recommendation": (
                "Proceed with full processing"
                if estimated_confidence > 0.5
                else "Consider additional verification"
            ),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "BabelReversal",
    "KnowledgeFragment",
    "ProcessedKnowledge",
    "DimensionalAnalysis",
    "SourceType",
    "ConfidenceLevel",
    "register_babel_tools",
]
