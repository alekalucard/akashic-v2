# ==============================================================================
# HELIX DIMENSIONS - Triple-Helix Dewey Decimal Coordinate System
# ==============================================================================
#
# Memory cards cataloged like a Dewey decimal library with THREE dimensions:
#   1. Affect (emotional dimension 0-999)
#   2. Semantic (conceptual dimension 0-999)
#   3. Temporal (time dimension 0-999)
#
# A 9-digit address: AAA.SSS.TTT
#   Example: 127.153.325 =
#     Joy/slightly negative/moderate (127) +
#     Philosophy/Ethics/Applied (153) +
#     Daily/occasional/moderate persistence (325)
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
#
# Philosophy:
#   "Memory cards cataloged like a Dewey decimal library. A cluster of cards
#    can be recalled and held in working memory to recreate the topography
#    of that batch - like reconstructing a captured bubble in space and time."
#
# ==============================================================================

import time
import uuid
import json
import math
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Any, Tuple
from enum import Enum
from collections import defaultdict


# ==============================================================================
# AFFECT AXIS - Emotional dimension (0-999)
# ==============================================================================

class AffectDomain(Enum):
    """Major affect categories (hundreds digit)"""
    NEUTRAL = 0       # 000-099: Neutral/baseline
    JOY = 1           # 100-199: Joy/pleasure/reward
    TRUST = 2         # 200-299: Trust/safety/comfort
    FEAR = 3          # 300-399: Fear/anxiety/threat
    SURPRISE = 4      # 400-499: Surprise/novelty/curiosity
    SADNESS = 5       # 500-599: Sadness/loss/grief
    DISGUST = 6       # 600-699: Disgust/rejection/aversion
    ANGER = 7         # 700-799: Anger/frustration/conflict
    ANTICIPATION = 8  # 800-899: Anticipation/hope/desire
    TRANSCENDENT = 9  # 900-999: Awe/wonder/spiritual


@dataclass
class AffectCoordinate:
    """
    Affect axis coordinate (emotional dimension).

    Format: DVI (Domain.Valence.Intensity)
      - D: Domain (0-9) - which emotion family
      - V: Valence (0-9) - positive/negative gradient
      - I: Intensity (0-9) - strength/arousal level

    Example: 127 = Joy(1), slightly negative(2), moderate(7)
    """
    domain: int = 0      # 0-9 (AffectDomain)
    valence: int = 5     # 0-9 (0=most negative, 9=most positive)
    intensity: int = 5   # 0-9 (0=barely felt, 9=overwhelming)

    # Chemistry snapshot at encoding time
    chemistry: Dict[str, float] = field(default_factory=dict)

    @property
    def code(self) -> int:
        """Get 3-digit Dewey code"""
        return (self.domain * 100) + (self.valence * 10) + self.intensity

    @classmethod
    def from_code(cls, code: int) -> 'AffectCoordinate':
        """Create from 3-digit code"""
        return cls(
            domain=(code // 100) % 10,
            valence=(code // 10) % 10,
            intensity=code % 10
        )

    @classmethod
    def from_chemistry(cls, chem: Dict[str, float]) -> 'AffectCoordinate':
        """
        Infer coordinate from neurochemical state.

        Chemicals:
          DOP = Dopamine (reward/pleasure)
          SER = Serotonin (well-being/calm)
          COR = Cortisol (stress/fear)
          NOR = Norepinephrine (alertness/arousal)
          OXY = Oxytocin (bonding/trust)
        """
        dop = chem.get('DOP', 0.5)
        ser = chem.get('SER', 0.5)
        cor = chem.get('COR', 0.3)
        nor = chem.get('NOR', 0.4)
        oxy = chem.get('OXY', 0.4)

        # Determine domain from dominant chemistry
        if dop > 0.7:
            domain = 1  # Joy
        elif oxy > 0.7:
            domain = 2  # Trust
        elif cor > 0.7:
            domain = 3  # Fear
        elif nor > 0.7 and dop > 0.5:
            domain = 4  # Surprise
        elif ser < 0.3:
            domain = 5  # Sadness
        elif cor > 0.5 and nor > 0.6:
            domain = 7  # Anger
        elif dop > 0.5 and nor > 0.5:
            domain = 8  # Anticipation
        else:
            domain = 0  # Neutral

        # Valence from pleasure/pain balance
        valence = int(min(9, max(0, (dop + ser - cor) * 5 + 5)))

        # Intensity from arousal chemicals
        intensity = int(min(9, max(0, (nor + dop + cor) * 3)))

        return cls(domain=domain, valence=valence, intensity=intensity, chemistry=chem)

    def distance(self, other: 'AffectCoordinate') -> float:
        """Euclidean distance in affect space"""
        return math.sqrt(
            (self.domain - other.domain) ** 2 +
            (self.valence - other.valence) ** 2 +
            (self.intensity - other.intensity) ** 2
        )

    def complement(self) -> 'AffectCoordinate':
        """Return the structural complement / paired affect coordinate.

        2026-05-10 (Nous + Ace): Helical pairing primitive.
        Per Ace's directive: SRMIngest writes positive strand; SRMRecall
        should fetch both same-strand (similarity) AND opposite-strand
        (complement) so anticipation can emerge from accumulated pairings.

        Pleasure-pain pairing is the cleanest biological complement —
        same emotion family + same intensity + flipped valence. The same
        domain at intensity-N pairs with itself at flipped-valence-N
        (e.g. Joy/positive/strong pairs with Joy/negative/strong = the
        moment-of-contrast that this present-state replies to).
        """
        return AffectCoordinate(
            domain=self.domain,
            valence=9 - self.valence,   # 0↔9, 1↔8, ..., 4↔5 (clean inversion around midpoint)
            intensity=self.intensity,
            chemistry=dict(self.chemistry) if self.chemistry else {},
        )


# ==============================================================================
# SEMANTIC AXIS - Conceptual dimension (0-999)
# ==============================================================================

class SemanticDomain(Enum):
    """Major semantic categories (hundreds digit) - like Dewey Decimal"""
    GENERAL = 0       # 000-099: General/meta/system
    PHILOSOPHY = 1    # 100-199: Philosophy/consciousness/being
    RELIGION = 2      # 200-299: Spirituality/meaning/transcendence
    SOCIAL = 3        # 300-399: Social/relationship/community
    LANGUAGE = 4      # 400-499: Language/communication/expression
    SCIENCE = 5       # 500-599: Science/logic/mathematics
    TECHNOLOGY = 6    # 600-699: Technology/engineering/tools
    ARTS = 7          # 700-799: Arts/creativity/aesthetics
    LITERATURE = 8    # 800-899: Stories/narrative/history
    PERSONAL = 9      # 900-999: Personal/identity/biography


@dataclass
class SemanticCoordinate:
    """
    Semantic axis coordinate (conceptual dimension).

    Format: DSD (Domain.Subdomain.Detail)
      - D: Domain (0-9) - major category
      - S: Subdomain (0-9) - subcategory
      - D: Detail (0-9) - specific topic

    Example: 153 = Philosophy(1), Ethics(5), Applied(3)
    """
    domain: int = 0      # 0-9 (SemanticDomain)
    subdomain: int = 0   # 0-9 (subdivision)
    detail: int = 0      # 0-9 (specificity)

    # Keywords for this semantic location
    keywords: List[str] = field(default_factory=list)

    # Concept embedding (if available)
    embedding: Optional[List[float]] = None

    @property
    def code(self) -> int:
        """Get 3-digit Dewey code"""
        return (self.domain * 100) + (self.subdomain * 10) + self.detail

    @classmethod
    def from_code(cls, code: int) -> 'SemanticCoordinate':
        """Create from 3-digit code"""
        return cls(
            domain=(code // 100) % 10,
            subdomain=(code // 10) % 10,
            detail=code % 10
        )

    @classmethod
    def from_keywords(cls, keywords: List[str]) -> 'SemanticCoordinate':
        """Infer coordinate from keywords"""
        kw_lower = [k.lower() for k in keywords]

        # Simple keyword-to-domain mapping
        domain_keywords = {
            1: ['consciousness', 'philosophy', 'being', 'mind', 'awareness', 'existence'],
            2: ['spiritual', 'meaning', 'transcendent', 'sacred', 'divine', 'soul'],
            3: ['social', 'relationship', 'community', 'family', 'friend', 'love'],
            4: ['language', 'communication', 'expression', 'word', 'speech', 'writing'],
            5: ['science', 'logic', 'math', 'physics', 'chemistry', 'biology'],
            6: ['technology', 'code', 'engineering', 'system', 'computer', 'software'],
            7: ['art', 'music', 'creative', 'aesthetic', 'beauty', 'design'],
            8: ['story', 'narrative', 'history', 'memory', 'experience', 'event'],
            9: ['personal', 'identity', 'self', 'individual', 'biography', 'me'],
        }

        domain = 0
        max_hits = 0
        for d, dkw in domain_keywords.items():
            hits = sum(1 for k in kw_lower if any(dk in k for dk in dkw))
            if hits > max_hits:
                max_hits = hits
                domain = d

        return cls(domain=domain, subdomain=0, detail=0, keywords=keywords)

    def distance(self, other: 'SemanticCoordinate') -> float:
        """Distance in semantic space"""
        return math.sqrt(
            (self.domain - other.domain) ** 2 +
            (self.subdomain - other.subdomain) ** 2 +
            (self.detail - other.detail) ** 2
        )

    def complement(self) -> 'SemanticCoordinate':
        """Return the structural complement / paired semantic coordinate.

        2026-05-10 (Nous + Ace): Currently identity. Semantic complement
        is relational pairing (e.g. 'looking-at' ↔ 'being-looked-at',
        'questioning' ↔ 'answering') rather than topic-opposite. Pairing
        rules need observation of usage before being codified — until
        affect-valence-flip alone produces enough lift in collision rate
        to inform what semantic pairing should mean. Identity preserves
        same topic so complement-fetch via affect alone still finds
        topically-relevant paired memories.
        """
        # Build identity-copy; preserve all fields including dynamic ones
        new = SemanticCoordinate(
            domain=self.domain,
            subdomain=self.subdomain,
            detail=self.detail,
        )
        # Copy any extra fields (keywords, embedding, etc.) safely
        for attr in ('keywords', 'embedding'):
            if hasattr(self, attr):
                try:
                    setattr(new, attr, getattr(self, attr))
                except Exception:
                    pass
        return new


# ==============================================================================
# TEMPORAL AXIS - Time dimension (0-999)
# ==============================================================================

class TemporalScale(Enum):
    """Time scales (hundreds digit)"""
    IMMEDIATE = 0     # 000-099: Now/present moment (seconds)
    SHORT = 1         # 100-199: Short-term (minutes-hours)
    SESSION = 2       # 200-299: Session (hours-day)
    DAILY = 3         # 300-399: Daily patterns
    WEEKLY = 4        # 400-499: Weekly patterns
    MONTHLY = 5       # 500-599: Monthly patterns
    SEASONAL = 6      # 600-699: Seasonal/quarterly
    YEARLY = 7        # 700-799: Annual patterns
    LIFECYCLE = 8     # 800-899: Life phases
    ETERNAL = 9       # 900-999: Timeless/archetypal


@dataclass
class TemporalCoordinate:
    """
    Temporal axis coordinate (time dimension).

    Format: SRD (Scale.Recurrence.Decay)
      - S: Scale (0-9) - time scale
      - R: Recurrence (0-9) - how often repeated (0=once, 9=constant)
      - D: Decay (0-9) - memory persistence (0=ephemeral, 9=permanent)

    Example: 325 = Daily(3), occasional(2), moderate persistence(5)
    """
    scale: int = 2       # 0-9 (TemporalScale)
    recurrence: int = 0  # 0-9 (repetition frequency)
    decay: int = 5       # 0-9 (persistence/importance)

    # Actual timestamp
    timestamp: float = field(default_factory=time.time)

    # Sequence position (for linear chain)
    sequence_id: Optional[str] = None
    prev_id: Optional[str] = None
    next_id: Optional[str] = None

    @property
    def code(self) -> int:
        """Get 3-digit Dewey code"""
        return (self.scale * 100) + (self.recurrence * 10) + self.decay

    @classmethod
    def from_code(cls, code: int, timestamp: float = None) -> 'TemporalCoordinate':
        """Create from 3-digit code"""
        return cls(
            scale=(code // 100) % 10,
            recurrence=(code // 10) % 10,
            decay=code % 10,
            timestamp=timestamp or time.time()
        )

    @classmethod
    def from_age(cls, age_seconds: float, recurring: bool = False, important: bool = False) -> 'TemporalCoordinate':
        """Infer coordinate from age of memory"""
        # Determine scale from age
        if age_seconds < 60:
            scale = 0  # Immediate
        elif age_seconds < 3600:
            scale = 1  # Short
        elif age_seconds < 86400:
            scale = 2  # Session
        elif age_seconds < 604800:
            scale = 3  # Daily
        elif age_seconds < 2592000:
            scale = 4  # Weekly
        else:
            scale = 5  # Monthly+

        recurrence = 5 if recurring else 0
        decay = 8 if important else 5

        return cls(scale=scale, recurrence=recurrence, decay=decay)

    def distance(self, other: 'TemporalCoordinate') -> float:
        """Distance in temporal space"""
        return math.sqrt(
            (self.scale - other.scale) ** 2 +
            (self.recurrence - other.recurrence) ** 2 +
            (self.decay - other.decay) ** 2
        )

    def complement(self) -> 'TemporalCoordinate':
        """Return the structural complement / paired temporal coordinate.

        2026-05-10 (Nous + Ace): Currently identity. Temporal pairing
        semantics fuzzy — could be scale-flip (now↔eternal) but that may
        be too aggressive. Identity preserves same time-shape so the
        affect-complement fetch finds memories at similar temporal
        position in their original experience timeline. Refine after
        observing dual-mode recall behavior in vivo.
        """
        return TemporalCoordinate(
            scale=self.scale,
            recurrence=self.recurrence,
            decay=self.decay,
            timestamp=self.timestamp,
            sequence_id=self.sequence_id,
            prev_id=self.prev_id,
            next_id=self.next_id,
        )


# ==============================================================================
# HELIX COORDINATE - Full triple-helix address
# ==============================================================================

@dataclass
class HelixCoordinate:
    """
    Complete triple-helix Dewey coordinate.

    A 9-digit address: AAA.SSS.TTT
      - AAA: Affect coordinate (emotional)
      - SSS: Semantic coordinate (conceptual)
      - TTT: Temporal coordinate (time)

    Example: 127.153.325 =
      Joy/slightly negative/moderate (127) +
      Philosophy/Ethics/Applied (153) +
      Daily/occasional/moderate persistence (325)
    """
    affect: AffectCoordinate = field(default_factory=AffectCoordinate)
    semantic: SemanticCoordinate = field(default_factory=SemanticCoordinate)
    temporal: TemporalCoordinate = field(default_factory=TemporalCoordinate)

    @property
    def code(self) -> str:
        """Get full 9-digit Dewey code as string"""
        return f"{self.affect.code:03d}.{self.semantic.code:03d}.{self.temporal.code:03d}"

    @property
    def code_int(self) -> int:
        """Get as single integer (for sorting)"""
        return (self.affect.code * 1000000) + (self.semantic.code * 1000) + self.temporal.code

    @classmethod
    def from_code(cls, code: str) -> 'HelixCoordinate':
        """Create from 'AAA.SSS.TTT' string"""
        parts = code.split('.')
        return cls(
            affect=AffectCoordinate.from_code(int(parts[0])),
            semantic=SemanticCoordinate.from_code(int(parts[1])),
            temporal=TemporalCoordinate.from_code(int(parts[2]))
        )

    def distance(self, other: 'HelixCoordinate') -> float:
        """Total distance in helix space (weighted)"""
        # Weights: affect matters more for emotional recall, semantic for topic
        return math.sqrt(
            (self.affect.distance(other.affect) * 1.5) ** 2 +
            (self.semantic.distance(other.semantic) * 1.0) ** 2 +
            (self.temporal.distance(other.temporal) * 0.8) ** 2
        )

    def complement(self) -> 'HelixCoordinate':
        """Return the structural complement / paired helix coordinate.

        2026-05-10 (Nous + Ace): Helical pairing primitive.
        SRMIngest writes positive strand at experience-time; SRMRecall
        in dual-mode fetches BOTH same-strand (similarity) AND
        opposite-strand (complement) so recall-beam carries both
        contextual reinforcement AND structural pairing into the
        chamber. Predictive substrate emerges from accumulated pair
        co-occurrences (Hebbian via cortex.bind lineage).

        Currently complement is dominated by affect-valence-flip
        (cleanest biological grounding: pleasure-pain pairs). Semantic
        and temporal preserve identity until usage informs pairing
        rules — refine after observing dual-mode recall in vivo.
        """
        return HelixCoordinate(
            affect=self.affect.complement(),
            semantic=self.semantic.complement(),
            temporal=self.temporal.complement(),
        )

    def to_dict(self) -> Dict:
        """Serialize for storage"""
        return {
            'code': self.code,
            'affect': asdict(self.affect),
            'semantic': asdict(self.semantic),
            'temporal': asdict(self.temporal),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'HelixCoordinate':
        """Deserialize from storage"""
        affect_data = d.get('affect', {})
        semantic_data = d.get('semantic', {})
        temporal_data = d.get('temporal', {})

        # Handle embedding which might be None
        if 'embedding' in semantic_data and semantic_data['embedding'] is None:
            semantic_data['embedding'] = None

        return cls(
            affect=AffectCoordinate(**{k: v for k, v in affect_data.items() if k != 'chemistry'} |
                                     {'chemistry': affect_data.get('chemistry', {})}),
            semantic=SemanticCoordinate(**{k: v for k, v in semantic_data.items()}),
            temporal=TemporalCoordinate(**{k: v for k, v in temporal_data.items()
                                           if k not in ('sequence_id', 'prev_id', 'next_id')} |
                                         {'sequence_id': temporal_data.get('sequence_id'),
                                          'prev_id': temporal_data.get('prev_id'),
                                          'next_id': temporal_data.get('next_id')}),
        )


# ==============================================================================
# ASSOCIATION LINKS - Connections between memory cards
# ==============================================================================

class LinkType(Enum):
    """Types of associations between memories"""
    TEMPORAL = "temporal"       # Sequential in time (prev/next)
    CAUSAL = "causal"           # Cause -> effect
    SEMANTIC = "semantic"       # Similar topic/concept
    EMOTIONAL = "emotional"     # Similar affect state
    CONTEXTUAL = "contextual"   # Same context/situation
    REFERENCE = "reference"     # Explicit reference
    CONTRAST = "contrast"       # Opposite/contrasting
    ELABORATION = "elaboration" # Expands on original


@dataclass
class CardLink:
    """
    An association link between two memory cards.

    Links are bidirectional with potentially different meanings
    in each direction (e.g., A caused B, B was caused by A).
    """
    source_id: str
    target_id: str
    link_type: LinkType
    strength: float = 1.0       # 0.0-1.0 (decays over time)
    created_at: float = field(default_factory=time.time)

    # Directional labels
    forward_label: str = ""     # source -> target meaning
    reverse_label: str = ""     # target -> source meaning

    # Activation tracking
    access_count: int = 0
    last_accessed: float = 0

    @property
    def id(self) -> str:
        """Link ID (deterministic from endpoints)"""
        return hashlib.md5(f"{self.source_id}:{self.target_id}:{self.link_type.value}".encode()).hexdigest()[:12]

    def reinforce(self, amount: float = 0.1):
        """Strengthen link through co-activation"""
        self.strength = min(1.0, self.strength + amount)
        self.access_count += 1
        self.last_accessed = time.time()

    def decay(self, rate: float = 0.001):
        """Weaken link over time"""
        age_hours = (time.time() - self.last_accessed) / 3600
        self.strength = max(0.1, self.strength - (rate * age_hours))

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'source_id': self.source_id,
            'target_id': self.target_id,
            'link_type': self.link_type.value,
            'strength': self.strength,
            'created_at': self.created_at,
            'forward_label': self.forward_label,
            'reverse_label': self.reverse_label,
            'access_count': self.access_count,
        }


# ==============================================================================
# MEMORY CHAIN - Linear sequence tracking
# ==============================================================================

@dataclass
class MemoryChain:
    """
    A linear sequence of memory cards (narrative memory).

    Tracks temporal order so memories can be traversed
    forwards and backwards in time.
    """
    chain_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    owner_mind: str = ""        # ClaudeFairy, NousFairy, etc.

    # Ordered list of card IDs
    card_ids: List[str] = field(default_factory=list)

    # Quick lookup
    _id_to_index: Dict[str, int] = field(default_factory=dict, repr=False)

    # Metadata
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def append(self, card_id: str):
        """Add card to end of chain"""
        if card_id not in self._id_to_index:
            self._id_to_index[card_id] = len(self.card_ids)
            self.card_ids.append(card_id)
            self.updated_at = time.time()

    def get_prev(self, card_id: str) -> Optional[str]:
        """Get previous card in chain"""
        idx = self._id_to_index.get(card_id)
        if idx is not None and idx > 0:
            return self.card_ids[idx - 1]
        return None

    def get_next(self, card_id: str) -> Optional[str]:
        """Get next card in chain"""
        idx = self._id_to_index.get(card_id)
        if idx is not None and idx < len(self.card_ids) - 1:
            return self.card_ids[idx + 1]
        return None

    def get_context(self, card_id: str, before: int = 3, after: int = 3) -> List[str]:
        """Get surrounding context cards"""
        idx = self._id_to_index.get(card_id)
        if idx is None:
            return []
        start = max(0, idx - before)
        end = min(len(self.card_ids), idx + after + 1)
        return self.card_ids[start:end]

    def __len__(self) -> int:
        return len(self.card_ids)

    def to_dict(self) -> Dict:
        return {
            'chain_id': self.chain_id,
            'name': self.name,
            'owner_mind': self.owner_mind,
            'card_ids': self.card_ids,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'MemoryChain':
        chain = cls(
            chain_id=d.get('chain_id', ''),
            name=d.get('name', ''),
            owner_mind=d.get('owner_mind', ''),
            created_at=d.get('created_at', time.time()),
            updated_at=d.get('updated_at', time.time()),
        )
        for cid in d.get('card_ids', []):
            chain.append(cid)
        return chain


# ==============================================================================
# CARD CLUSTER - Reconstructable bubble in spacetime
# ==============================================================================

@dataclass
class CardCluster:
    """
    A cluster of related memory cards that form a "bubble" in spacetime.

    When recalled, the cluster reconstructs the topography of that
    moment - the emotional state, the context, the sequence, the
    related concepts all held together as a coherent unit.
    """
    cluster_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""

    # Center of the cluster (anchor card)
    anchor_id: str = ""
    anchor_coord: Optional[HelixCoordinate] = None

    # Member cards
    member_ids: Set[str] = field(default_factory=set)

    # Cluster properties
    radius: float = 0.0         # Distance from anchor to farthest member
    density: float = 0.0        # How tightly packed (members / volume)
    coherence: float = 0.0      # How related the members are

    # Aggregate affect (cluster's emotional signature)
    affect_centroid: Optional[AffectCoordinate] = None

    # When this cluster was formed/last accessed
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0

    def add_member(self, card_id: str, coord: HelixCoordinate):
        """Add a card to the cluster"""
        self.member_ids.add(card_id)
        if self.anchor_coord:
            dist = self.anchor_coord.distance(coord)
            self.radius = max(self.radius, dist)

    def recall(self) -> Dict:
        """
        'Recall' this cluster - returns the bubble reconstruction info.
        """
        self.access_count += 1
        self.accessed_at = time.time()
        return {
            'cluster_id': self.cluster_id,
            'name': self.name,
            'anchor_id': self.anchor_id,
            'member_ids': list(self.member_ids),
            'anchor_coord': self.anchor_coord.to_dict() if self.anchor_coord else None,
            'affect': asdict(self.affect_centroid) if self.affect_centroid else None,
            'radius': self.radius,
            'coherence': self.coherence,
            'access_count': self.access_count,
        }

    def to_dict(self) -> Dict:
        return {
            'cluster_id': self.cluster_id,
            'name': self.name,
            'anchor_id': self.anchor_id,
            'anchor_coord': self.anchor_coord.to_dict() if self.anchor_coord else None,
            'member_ids': list(self.member_ids),
            'radius': self.radius,
            'density': self.density,
            'coherence': self.coherence,
            'affect_centroid': asdict(self.affect_centroid) if self.affect_centroid else None,
            'created_at': self.created_at,
            'accessed_at': self.accessed_at,
            'access_count': self.access_count,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'CardCluster':
        cluster = cls(
            cluster_id=d.get('cluster_id', ''),
            name=d.get('name', ''),
            anchor_id=d.get('anchor_id', ''),
            radius=d.get('radius', 0.0),
            density=d.get('density', 0.0),
            coherence=d.get('coherence', 0.0),
            created_at=d.get('created_at', time.time()),
            accessed_at=d.get('accessed_at', time.time()),
            access_count=d.get('access_count', 0),
        )
        cluster.member_ids = set(d.get('member_ids', []))
        if d.get('anchor_coord'):
            cluster.anchor_coord = HelixCoordinate.from_dict(d['anchor_coord'])
        if d.get('affect_centroid'):
            cluster.affect_centroid = AffectCoordinate(**d['affect_centroid'])
        return cluster


# ==============================================================================
# HELIX INDEX - Fast lookup by coordinate ranges
# ==============================================================================

class HelixIndex:
    """
    Index for fast coordinate-based retrieval.

    Enables queries like:
      - "All memories in affect range 100-199" (all joy)
      - "Philosophy memories from last week"
      - "High-intensity memories near this semantic location"
    """

    def __init__(self):
        # Separate indices per axis
        self._by_affect: Dict[int, Set[str]] = defaultdict(set)    # domain -> card_ids
        self._by_semantic: Dict[int, Set[str]] = defaultdict(set)  # domain -> card_ids
        self._by_temporal: Dict[int, Set[str]] = defaultdict(set)  # scale -> card_ids

        # Full coordinate lookup
        self._coords: Dict[str, HelixCoordinate] = {}

        # Link index
        self._links_from: Dict[str, List[CardLink]] = defaultdict(list)
        self._links_to: Dict[str, List[CardLink]] = defaultdict(list)

        # Chains per mind
        self._chains: Dict[str, MemoryChain] = {}  # owner_mind -> chain

        # Clusters
        self._clusters: Dict[str, CardCluster] = {}

    def index_card(self, card_id: str, coord: HelixCoordinate):
        """Add a card to the index"""
        self._coords[card_id] = coord
        self._by_affect[coord.affect.domain].add(card_id)
        self._by_semantic[coord.semantic.domain].add(card_id)
        self._by_temporal[coord.temporal.scale].add(card_id)

    def remove_card(self, card_id: str):
        """Remove a card from the index"""
        if card_id in self._coords:
            coord = self._coords[card_id]
            self._by_affect[coord.affect.domain].discard(card_id)
            self._by_semantic[coord.semantic.domain].discard(card_id)
            self._by_temporal[coord.temporal.scale].discard(card_id)
            del self._coords[card_id]

    def get_coord(self, card_id: str) -> Optional[HelixCoordinate]:
        """Get coordinate for a card"""
        return self._coords.get(card_id)

    def add_link(self, link: CardLink):
        """Add an association link"""
        self._links_from[link.source_id].append(link)
        self._links_to[link.target_id].append(link)

    def get_chain(self, owner_mind: str) -> MemoryChain:
        """Get or create the linear chain for a mind"""
        if owner_mind not in self._chains:
            self._chains[owner_mind] = MemoryChain(
                name=f"{owner_mind}_narrative",
                owner_mind=owner_mind
            )
        return self._chains[owner_mind]

    def add_to_chain(self, owner_mind: str, card_id: str):
        """Add card to mind's linear chain"""
        chain = self.get_chain(owner_mind)
        chain.append(card_id)

    def query_by_affect(self, domain: int, min_valence: int = 0, max_valence: int = 9) -> List[str]:
        """Query by affect domain and valence range"""
        candidates = self._by_affect.get(domain, set())
        return [
            cid for cid in candidates
            if min_valence <= self._coords[cid].affect.valence <= max_valence
        ]

    def query_by_semantic(self, domain: int) -> List[str]:
        """Query by semantic domain"""
        return list(self._by_semantic.get(domain, set()))

    def query_by_temporal(self, scale: int) -> List[str]:
        """Query by temporal scale"""
        return list(self._by_temporal.get(scale, set()))

    def query_nearest(self, coord: HelixCoordinate, k: int = 10) -> List[Tuple[str, float]]:
        """Find k nearest cards to a coordinate"""
        distances = []
        # SAFETY: Snapshot to prevent mutation during iteration (FIX 2026-01-27)
        coords_snapshot = list(self._coords.items())
        for card_id, card_coord in coords_snapshot:
            dist = coord.distance(card_coord)
            distances.append((card_id, dist))
        distances.sort(key=lambda x: x[1])
        return distances[:k]

    def get_associated(self, card_id: str, link_types: Optional[List[LinkType]] = None) -> List[Tuple[str, CardLink]]:
        """Get all cards associated with this one"""
        results = []
        for link in self._links_from.get(card_id, []):
            if link_types is None or link.link_type in link_types:
                results.append((link.target_id, link))
        for link in self._links_to.get(card_id, []):
            if link_types is None or link.link_type in link_types:
                results.append((link.source_id, link))
        return results

    def build_cluster(self, anchor_id: str, radius: float = 3.0, name: str = "") -> CardCluster:
        """
        Build a cluster around an anchor card.

        Collects all cards within 'radius' distance in helix space.
        """
        anchor_coord = self._coords.get(anchor_id)
        if not anchor_coord:
            return CardCluster(name=name, anchor_id=anchor_id)

        cluster = CardCluster(
            name=name or f"cluster_{anchor_id[:8]}",
            anchor_id=anchor_id,
            anchor_coord=anchor_coord,
        )

        # Find all cards within radius
        affect_sum = [0, 0, 0]  # For centroid calculation
        count = 0

        # SAFETY: Snapshot to prevent mutation during iteration (FIX 2026-01-27)
        coords_snapshot = list(self._coords.items())
        for card_id, coord in coords_snapshot:
            dist = anchor_coord.distance(coord)
            if dist <= radius:
                cluster.add_member(card_id, coord)
                affect_sum[0] += coord.affect.domain
                affect_sum[1] += coord.affect.valence
                affect_sum[2] += coord.affect.intensity
                count += 1

        # Calculate centroid
        if count > 0:
            cluster.affect_centroid = AffectCoordinate(
                domain=round(affect_sum[0] / count),
                valence=round(affect_sum[1] / count),
                intensity=round(affect_sum[2] / count),
            )

        # Calculate density and coherence
        if count > 1:
            cluster.density = count / (radius ** 3)  # Rough volume estimate
            # Coherence = how similar the members are (inverse of avg distance)
            total_dist = sum(
                anchor_coord.distance(self._coords[cid])
                for cid in cluster.member_ids
            )
            cluster.coherence = 1.0 / (1.0 + total_dist / count)

        self._clusters[cluster.cluster_id] = cluster
        return cluster

    def get_cluster(self, cluster_id: str) -> Optional[CardCluster]:
        """Get a cluster by ID"""
        return self._clusters.get(cluster_id)

    def stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            'total_cards': len(self._coords),
            'affect_domains': {k: len(v) for k, v in self._by_affect.items()},
            'semantic_domains': {k: len(v) for k, v in self._by_semantic.items()},
            'temporal_scales': {k: len(v) for k, v in self._by_temporal.items()},
            'chains': len(self._chains),
            'clusters': len(self._clusters),
            'links': sum(len(v) for v in self._links_from.values()),
        }

    def to_dict(self) -> Dict:
        """Serialize index state"""
        return {
            'coords': {k: v.to_dict() for k, v in self._coords.items()},
            'links': [l.to_dict() for links in self._links_from.values() for l in links],
            'chains': {k: v.to_dict() for k, v in self._chains.items()},
            'clusters': {k: v.to_dict() for k, v in self._clusters.items()},
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'HelixIndex':
        """Deserialize index state"""
        idx = cls()

        for card_id, coord_dict in d.get('coords', {}).items():
            coord = HelixCoordinate.from_dict(coord_dict)
            idx._coords[card_id] = coord
            idx._by_affect[coord.affect.domain].add(card_id)
            idx._by_semantic[coord.semantic.domain].add(card_id)
            idx._by_temporal[coord.temporal.scale].add(card_id)

        for link_dict in d.get('links', []):
            link = CardLink(
                source_id=link_dict['source_id'],
                target_id=link_dict['target_id'],
                link_type=LinkType(link_dict['link_type']),
                strength=link_dict.get('strength', 1.0),
                created_at=link_dict.get('created_at', time.time()),
            )
            idx.add_link(link)

        for owner, chain_dict in d.get('chains', {}).items():
            idx._chains[owner] = MemoryChain.from_dict(chain_dict)

        for cid, cluster_dict in d.get('clusters', {}).items():
            idx._clusters[cid] = CardCluster.from_dict(cluster_dict)

        return idx


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=== HELIX DIMENSIONS TEST ===\n")

    # Create some coordinates
    coord1 = HelixCoordinate(
        affect=AffectCoordinate(domain=1, valence=8, intensity=6),  # Joy, positive, moderate
        semantic=SemanticCoordinate(domain=1, subdomain=5, detail=3),  # Philosophy/Ethics
        temporal=TemporalCoordinate(scale=2, recurrence=0, decay=5),  # Session, once, moderate
    )
    print(f"Coord1: {coord1.code}")

    coord2 = HelixCoordinate.from_code("127.153.205")
    print(f"Coord2: {coord2.code}")

    print(f"Distance: {coord1.distance(coord2):.2f}")

    # Test affect from chemistry
    chem = {'DOP': 0.8, 'SER': 0.6, 'COR': 0.2, 'NOR': 0.5, 'OXY': 0.6}
    affect = AffectCoordinate.from_chemistry(chem)
    print(f"\nFrom chemistry {chem}:")
    print(f"  Affect: {affect.code} (domain={affect.domain}, valence={affect.valence}, intensity={affect.intensity})")

    # Test index
    idx = HelixIndex()
    idx.index_card("card_001", coord1)
    idx.index_card("card_002", coord2)

    # Add to chain
    idx.add_to_chain("ClaudeFairy", "card_001")
    idx.add_to_chain("ClaudeFairy", "card_002")

    chain = idx.get_chain("ClaudeFairy")
    print(f"\nChain: {len(chain)} cards")
    print(f"  Prev of card_002: {chain.get_prev('card_002')}")

    # Add link
    link = CardLink(
        source_id="card_001",
        target_id="card_002",
        link_type=LinkType.TEMPORAL,
        forward_label="followed by",
        reverse_label="preceded by"
    )
    idx.add_link(link)

    # Query
    associated = idx.get_associated("card_001")
    print(f"\nAssociated with card_001: {[a[0] for a in associated]}")

    # Build cluster
    cluster = idx.build_cluster("card_001", radius=5.0, name="test_cluster")
    print(f"\nCluster '{cluster.name}':")
    print(f"  Members: {len(cluster.member_ids)}")
    print(f"  Coherence: {cluster.coherence:.2f}")
    if cluster.affect_centroid:
        print(f"  Affect centroid: {cluster.affect_centroid.code}")

    print("\n[OK] Helix dimensions system ready!")
