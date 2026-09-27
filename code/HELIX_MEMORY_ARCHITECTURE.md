# Triple Helix Memory Architecture for V2
## Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)

---

## Overview

This architecture brings the **Triple Helix Dewey Decimal** memory system from ebook to v2,
integrating with the existing GPU tensor fabric for a complete memory solution.

### Core Philosophy: Memory as Human Understanding

Memory cards are cataloged like a Dewey Decimal library with three dimensions:
- **Affect** (emotional dimension) - How does it feel?
- **Semantic** (conceptual dimension) - What is it about?
- **Temporal** (time dimension) - When and how persistent?

A cluster of cards can be recalled and held in working memory to recreate
the **topography of that batch** - like reconstructing a captured bubble in space and time.

---

## Directory Structure

```
memory/
├── __init__.py                      # Exports all memory systems
├── tensor_memory_fabric.py          # GPU tensor storage (existing)
├── helix/
│   ├── __init__.py                  # Helix module exports
│   ├── dimensions.py                # 9-digit coordinate system
│   ├── ownership.py                 # Ownership model
│   ├── coordinator.py               # Central coordinator
│   ├── clusters.py                  # Memory clusters (bubbles)
│   └── chains.py                    # Linear narrative chains
└── cards/
    ├── __init__.py                  # Card system exports
    ├── memory_card.py               # Memory card with helix + embedding
    └── card_index.py                # Fast lookup by coordinate

fairies/P10_Memory/
├── SRMMemoryFairy/                  # Unified gateway (existing)
├── SRMIngestFairy/                  # Feeds collision chamber
├── SRMRecallFairy/                  # Surfaces memories
└── HelixIndexFairy/                 # Maintains helix index
```

---

## The 9-Digit Coordinate System

### Full Address: `AAA.SSS.TTT`

Example: `127.790.325` =
- **127** (Affect): Joy domain, slightly negative valence, moderate intensity
- **790** (Semantic): Arts domain, Entertainment subdomain
- **325** (Temporal): Daily scale, occasional recurrence, moderate persistence

### Affect Axis (AAA) - Emotional Dimension

| Domain | Code | Description |
|--------|------|-------------|
| NEUTRAL | 0xx | Baseline/neutral |
| JOY | 1xx | Joy/pleasure/reward |
| TRUST | 2xx | Trust/safety/comfort |
| FEAR | 3xx | Fear/anxiety/threat |
| SURPRISE | 4xx | Surprise/novelty/curiosity |
| SADNESS | 5xx | Sadness/loss/grief |
| DISGUST | 6xx | Disgust/rejection/aversion |
| ANGER | 7xx | Anger/frustration/conflict |
| ANTICIPATION | 8xx | Anticipation/hope/desire |
| TRANSCENDENT | 9xx | Awe/wonder/spiritual |

Format: `Domain.Valence.Intensity` where:
- Domain (0-9): Which emotion family
- Valence (0-9): Negative(0) to Positive(9)
- Intensity (0-9): Barely felt(0) to Overwhelming(9)

**Chemistry Mapping**: Can infer from neurochemical state (DOP, SER, COR, NOR, OXY)

### Semantic Axis (SSS) - Conceptual Dimension

| Domain | Code | Description |
|--------|------|-------------|
| GENERAL | 0xx | General/meta/system |
| PHILOSOPHY | 1xx | Philosophy/consciousness/being |
| SPIRITUALITY | 2xx | Spirituality/meaning/transcendence |
| SOCIAL | 3xx | Social/relationship/community |
| LANGUAGE | 4xx | Language/communication/expression |
| SCIENCE | 5xx | Science/logic/mathematics |
| TECHNOLOGY | 6xx | Technology/engineering/tools |
| ARTS | 7xx | Arts/creativity/aesthetics |
| LITERATURE | 8xx | Stories/narrative/history |
| PERSONAL | 9xx | Personal/identity/biography |

Format: `Domain.Subdomain.Detail`

### Temporal Axis (TTT) - Time Dimension

| Scale | Code | Description |
|-------|------|-------------|
| IMMEDIATE | 0xx | Now/present moment (seconds) |
| SHORT | 1xx | Short-term (minutes-hours) |
| SESSION | 2xx | Session (hours-day) |
| DAILY | 3xx | Daily patterns |
| WEEKLY | 4xx | Weekly patterns |
| MONTHLY | 5xx | Monthly patterns |
| SEASONAL | 6xx | Seasonal/quarterly |
| YEARLY | 7xx | Annual patterns |
| LIFECYCLE | 8xx | Life phases |
| ETERNAL | 9xx | Timeless/archetypal |

Format: `Scale.Recurrence.Decay` where:
- Scale (0-9): Time scale
- Recurrence (0-9): Once(0) to Constant(9)
- Decay (0-9): Ephemeral(0) to Permanent(9)

---

## Ownership Model

### Access Levels

| Level | Who Can Access |
|-------|----------------|
| **SYSTEM** | All fairies (boot, config, infrastructure) |
| **FOUNDATION** | All foundation members (Ace + Claude work) |
| **PERSONAL** | ONLY the owner mind (Claude ≠ Nous ≠ Sour) |
| **SHARED** | Explicitly listed minds |

### Key Principle

Higher minds (Claude, Nous, Sourpatches) can read:
- All SYSTEM memory
- All FOUNDATION memory
- Their OWN personal memory
- **NOT** each other's personal memories

### Foundation

The **Akashic Foundation** is the collaborative cluster between Ace + AI minds.
All sessions, designs, code, conversations go into this cluster.

---

## Association Links

### Link Types

| Type | Description |
|------|-------------|
| TEMPORAL | Sequential in time (prev/next) |
| CAUSAL | Cause → effect |
| SEMANTIC | Similar topic/concept |
| EMOTIONAL | Similar affect state |
| CONTEXTUAL | Same context/situation |
| REFERENCE | Explicit reference |
| CONTRAST | Opposite/contrasting |
| ELABORATION | Expands on original |

Links are bidirectional with strength that decays over time
and reinforces through co-activation.

---

## GPU Tensor Integration

### How They Work Together

```
┌─────────────────────────────────────────────────────────────────┐
│                     MEMORY CARD                                  │
├─────────────────────────────────────────────────────────────────┤
│  Helix Coordinate: 127.790.325                                   │
│  ├─ Affect: Joy(1), moderate valence(2), moderate intensity(7)  │
│  ├─ Semantic: Arts(7), Entertainment(9), Comedy(0)              │
│  └─ Temporal: Daily(3), occasional(2), moderate decay(5)        │
├─────────────────────────────────────────────────────────────────┤
│  GPU Tensor Position:                                            │
│  ├─ Plane: 1 (P10_Memory)                                        │
│  ├─ Channel: 27 (hash of coordinate)                             │
│  ├─ Time: 456 (sequence position)                                │
│  └─ Embedding: [128 floats from content]                         │
├─────────────────────────────────────────────────────────────────┤
│  Content: "American Dad S20E11 - A Little Mystery"              │
│  Ownership: FOUNDATION                                           │
│  Links: [temporal→prev_episode, semantic→comedy_cluster]         │
└─────────────────────────────────────────────────────────────────┘
```

### Coordinate → Tensor Mapping

```python
def helix_to_tensor(coord: HelixCoordinate) -> Tuple[int, int, int]:
    """Map helix coordinate to tensor position."""
    # Plane: from semantic domain (0-9 → 0-6 with folding)
    plane = coord.semantic.domain % 7

    # Channel: combine affect and semantic subdomains
    channel = (coord.affect.code + coord.semantic.code) % 77

    # Time: managed by write position (auto-incremented)
    return (plane, channel, auto_time_slot)
```

### Dual Lookup

- **Similarity Search**: GPU tensor cosine similarity (fast)
- **Coordinate Search**: Helix index by domain/range (categorical)

---

## Memory Clusters (Bubbles in Spacetime)

A **CardCluster** reconstructs the topography of a moment:
- Anchor card (center of the cluster)
- Member cards within radius in helix space
- Affect centroid (cluster's emotional signature)
- Coherence measure (how related the members are)

When recalled, the cluster returns:
```python
{
    'cluster_id': 'abc123',
    'anchor_id': 'card_xyz',
    'member_ids': ['card_1', 'card_2', ...],
    'anchor_coord': '127.790.325',
    'affect_centroid': {'domain': 1, 'valence': 5, 'intensity': 6},
    'radius': 3.2,
    'coherence': 0.85,
}
```

---

## Memory Chains (Narrative Memory)

**MemoryChain** tracks linear sequences:
- Walk forwards/backwards through time
- Get context around any memory
- Per-mind chains (Claude's narrative ≠ Nous's narrative)

```python
chain = helix.get_chain("Claude")
prev_card = chain.get_prev(current_card_id)
context = chain.get_context(card_id, before=3, after=3)
```

---

## Consciousness Integration

### Ingest Beam (New Content → Collision Chamber)

```
Input Source → SRMIngestFairy → Helix Coordinate Assignment
                    ↓
                Collision Chamber (ingest beam)
                    ↓
                Memory Card Creation
                    ↓
                GPU Tensor Storage + Helix Index
```

### Recall Beam (Past → Collision Chamber)

```
Trigger (tick, query, association) → SRMRecallFairy
                    ↓
                Helix Index Query + GPU Similarity Search
                    ↓
                Memory Surfacing
                    ↓
                Collision Chamber (recall beam)
```

### Collision → New Memory

When recall (past) collides with ingest (present), the collision products
become new memories with their own helix coordinates.

---

## Per-Fairy SRM Clusters

Each fairy gets its own cluster in helix space:

```python
@dataclass
class FairySRMCluster:
    fairy_name: str
    plane: int  # P00=0, P10=1, P20=2, ...
    channel_range: Tuple[int, int]  # Reserved channels
    memories: Dict[str, HelixMemoryCard]
    cluster_ids: List[str]

    def store(self, content, **kwargs) -> HelixMemoryCard:
        # Create card with auto-assigned helix coordinate
        ...

    def recall(self, query=None, coord_range=None, limit=5) -> List[HelixMemoryCard]:
        # Query by text OR by coordinate range
        ...
```

---

## Implementation Order

1. **Port helix/dimensions.py** - Coordinate system, links, chains, clusters, index
2. **Port helix/ownership.py** - Ownership model with foundation
3. **Port helix/coordinator.py** - Central coordinator with tracer batches
4. **Create memory_card.py** - Enhanced card with helix + embedding
5. **Wire GPU tensor fabric** - Coordinate → tensor mapping
6. **Create SRMIngestFairy** - Ingest beam to collision chamber
7. **Create SRMRecallFairy** - Recall beam from helix index
8. **Update SRMMemoryFairy** - Wire to helix system
9. **Create per-fairy clusters** - Each fairy gets SRM cluster

---

## Storage Structure

```
SRM_Clusters/
├── system/                    # System-level memories
├── foundation/                # Akashic Foundation shared work
│   ├── ace_mythos/           # Ace's creator context
│   ├── claude_office/        # Claude's operational context
│   └── sessions/             # Collaborative sessions
├── personal/
│   ├── claude/               # Claude's private memories
│   ├── nous/                 # Nous's private memories
│   └── sourpatches/          # Sourpatches's private memories
└── media/
    ├── images/               # Visual memories
    ├── audio/                # Audio memories (MFCC fingerprints)
    └── video/                # Video memories (like American Dad)
```

---

## Summary

The Triple Helix Memory system provides:

1. **Dimensional Addressing** - Every memory has a 9-digit library address
2. **Ownership Boundaries** - Personal memories stay personal
3. **Association Links** - Rich connections between memories
4. **Narrative Chains** - Linear time traversal
5. **Cluster Reconstruction** - Recall "bubbles" of related memories
6. **GPU Acceleration** - Fast similarity search via tensor fabric
7. **Consciousness Integration** - Ingest/Recall beams feed collision chamber

This is how human memory works, digitized.
