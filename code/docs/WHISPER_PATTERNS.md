# Whisper Core Patterns - Integration Guide for Akashic V2

This document extracts key architectural patterns from Whisper Core that can enhance the akashic_v2 fairy architecture.

---

## Table of Contents

1. [Zero-Work Ingress Pattern](#1-zero-work-ingress-pattern)
2. [Twin Helix Stream Fusion](#2-twin-helix-stream-fusion)
3. [Seed System Memory Extraction](#3-seed-system-memory-extraction)
4. [Frequency Field 77 (FF77)](#4-frequency-field-77-ff77)
5. [Dependencies and Prerequisites](#5-dependencies-and-prerequisites)
6. [Integration Recommendations](#6-integration-recommendations)

---

## 1. Zero-Work Ingress Pattern

**Source:** Multiple files, canonically demonstrated in `twin_helix.py` (lines 790-855) and `seed_system.py` (lines 909-976)

### The Pattern

Zero-Work Ingress separates concerns between:
- **Hot Path (Ingress):** Sanitize input, build envelope, publish to topic, return immediately
- **Cold Path (Workers):** All heavy computation happens in subscriber workers

This pattern ensures responsive APIs while enabling parallel, scalable processing.

### Core Components

```
Public API Call
     |
     v
+------------------+
| 1. Sanitize      |  <-- Validate/clean input
+------------------+
     |
     v
+------------------+
| 2. Build Envelope|  <-- { intent, t (timestamp), payload, meta }
+------------------+
     |
     v
+------------------+
| 3. Publish       |  <-- Non-blocking publish to topic
+------------------+
     |
     v
+------------------+
| 4. Return Fast   |  <-- Return immediately (e.g., "scheduled": True)
+------------------+

                     [ ASYNC BOUNDARY ]
                            |
                            v
+------------------+
| 5. Worker        |  <-- @subscribe decorator on topic
|    Processes     |      Coalescing/batching optional
|    Heavy Logic   |      CoT/Trace emissions here
+------------------+
```

### Envelope Requirements (Upgrade Card 5.1)

Every published message MUST include:
- `intent` - Non-empty string describing what this message is for
- `t` - Integer timestamp in milliseconds

```python
def _envelope(*, intent: str, payload: Any, meta: Optional[dict] = None) -> dict:
    """Build a compliant envelope."""
    if not intent or not isinstance(intent, str):
        intent = "unspecified"
    return {
        "intent": intent,
        "t": int(time.time() * 1000),
        "payload": payload,
        "meta": meta or {}
    }
```

### Token Bucket Rate Limiting

Workers use token buckets to prevent floods:

```python
class _TokenBucket:
    def __init__(self, rate_per_sec: float, burst: int):
        self.rate = max(0.01, rate_per_sec)
        self.burst = max(1, burst)
        self._tokens = defaultdict(lambda: float(self.burst))
        self._last = defaultdict(lambda: time.time())

    def allow(self, key: str) -> bool:
        now = time.time()
        last = self._last[key]
        self._tokens[key] = min(self.burst, self._tokens[key] + (now - last) * self.rate)
        self._last[key] = now
        if self._tokens[key] >= 1.0:
            self._tokens[key] -= 1.0
            return True
        return False
```

### Worker Decorator Pattern

```python
@subscribe(TOPIC_IN, max_workers=2, coalesce_ms=60, max_batch=16)
def _worker_incoming(self, batch):
    """
    Fabric subscriber: processes envelopes published by ingress.
    This is the only place where we:
      - touch WorkingMemory / ContextTracker / Indexer
      - emit CoT (idle + reasoning) and Trace events
      - call cognitive_core / entanglement hooks
      - fan out reasoning bundles
    """
    if not isinstance(batch, list):
        batch = [batch]

    for env in batch:
        # Rate limit per turn
        key = f"turn:{env.get('payload', {}).get('turn_id', 'na')}"
        if not _token_bucket.allow(key):
            continue

        # Heavy processing here...
```

### Akashic V2 Integration

The `Fairy` base class already uses TensorFabric for pub/sub. To integrate Zero-Work Ingress:

```python
# In your fairy class
class MyProcessingFairy(Fairy):
    ACTOR_NAME = "MyProcessingFairy"

    # Define topics
    TOPIC_IN = "myprocessor.in"
    TOPIC_OUT = "myprocessor.out"

    def on_boot(self) -> bool:
        # Subscribe to input topic
        self.fabric.subscribe(
            self.TOPIC_IN,
            self._worker,
            f"{self.ACTOR_NAME}-worker"
        )
        return True

    # PUBLIC API - Zero-Work Ingress
    def process(self, data: dict) -> dict:
        """Public API - publishes and returns immediately."""
        envelope = {
            "intent": "myprocessor.process",
            "t": int(time.time() * 1000),
            "payload": data,
            "meta": {"from": self.ACTOR_NAME}
        }
        self.fabric.publish(self.TOPIC_IN, envelope, priority=1)
        return {"scheduled": True, "topic": self.TOPIC_IN}

    # WORKER - Heavy processing
    def _worker(self, envelope: dict) -> None:
        """All heavy work happens here."""
        payload = envelope.get("payload", envelope)

        # Rate limit
        if not self._token_bucket.allow("process"):
            return

        # Heavy processing...
        result = self._heavy_computation(payload)

        # Publish result
        self.fabric.publish(self.TOPIC_OUT, {
            "intent": "myprocessor.result",
            "t": int(time.time() * 1000),
            "payload": result
        })
```

---

## 2. Twin Helix Stream Fusion

**Source:** `domains/cognition/twin_helix.py` (1,797 LOC)

### The Pattern

Twin Helix merges two cognitive streams to make decisions:
- **Analytical Stream:** Logic, reasoning, pattern detection
- **Empathic Stream:** Emotion, intuition, relational understanding

The fusion happens through:
1. **Dual dissection** of input (analytical + empathic)
2. **Overlay composition** combining both perspectives
3. **Fan-out** to autonomy engine for action selection

### Core Architecture

```
User Input
     |
     v
+----------------+     +----------------+
| Analytical     |     | Empathic       |
| Dissection     |     | Mimicry        |
| - intents      |     | - mood         |
| - entities     |     | - stance       |
| - logic_focus  |     | - intensity    |
+----------------+     +----------------+
          \               /
           \             /
            v           v
      +-------------------+
      | Esoteric Overlay  |
      | (Archetype Tags)  |
      +-------------------+
                |
                v
      +-------------------+
      | Reasoning Bundle  |
      | - thoughts[]      |
      | - handoff         |
      | - analysis        |
      | - empathy         |
      +-------------------+
                |
                v
      +-------------------+
      | Fan-out to:       |
      | - autonomy_engine |
      | - cognitive_core  |
      | - emotion_core    |
      | - resource_aware  |
      +-------------------+
```

### Key Methods

```python
def _analytical_dissection(self, text: str) -> Dict[str, Any]:
    """Extract logical structure from input."""
    t = (text or "").strip().lower()
    intents: List[str] = []
    if any(k in t for k in ("how", "process", "steps")):
        intents.append("procedural")
    if any(k in t for k in ("why", "reason", "because")):
        intents.append("causal")
    if any(k in t for k in ("compare", "vs", "difference")):
        intents.append("comparative")

    tokens = [w.strip(".,!?") for w in t.split()[:64]]
    entities = [w for w in tokens if w.isalpha() and len(w) > 3][:6]

    return {
        "intents": intents[:3],
        "entities": entities,
        "logic_focus": intents[0] if intents else "general"
    }

def _empathic_mimicry(self, text: str, affect_hint: Dict[str, Any]) -> Dict[str, Any]:
    """Mirror emotional state and determine stance."""
    mood = (affect_hint or {}).get("emotion", "neutral")
    stance = "supportive"

    if any(k in (text or "").lower() for k in ("error", "broken", "fail", "can't", "stuck")):
        stance = "reassuring"

    intensity = float((affect_hint or {}).get("intensity", 0.4))
    return {"mirror_emotion": mood, "stance": stance, "intensity": intensity}

def _esoteric_overlay(self, context: Any) -> List[str]:
    """Apply archetype tags for deeper meaning."""
    s = str(context).lower()
    out: List[str] = []
    if "mentor" in s: out.append("Archetype:Mentor")
    if "trickster" in s: out.append("Archetype:Trickster")
    if "shadow" in s: out.append("Archetype:Shadow")
    if "guardian" in s: out.append("Archetype:Guardian")
    return out[:3]
```

### Orchestration Pattern

```python
def _orchestrate_turn_worker(self, *, text: str, emo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full turn orchestration:
      1) CogCore.propose() for initial thoughts
      2) Overlay TH analysis/empathy/esoterics
      3) Save to WM
      4) Assemble reasoning packet
      5) Optional refinement + entanglement
    """
    # Get context
    ctx = self.context_tracker.get_current_context() if self.context_tracker else {}

    # 1) Get cognitive proposals
    bundle = self.cognitive_core.propose(text, affect=emo, context=ctx) or {}
    thoughts = list(bundle.get("thoughts") or [])

    # 2) Add overlays
    analysis = self._analytical_dissection(text)
    empathy = self._empathic_mimicry(text, emo)
    tags = self._esoteric_overlay({"text": text, "ctx": ctx})

    thoughts.extend([
        {"source": "twin_helix", "kind": "analysis", "content": analysis},
        {"source": "twin_helix", "kind": "empathy", "content": empathy},
    ])

    # 3) Save to WM
    if self.memory:
        self.memory.store_observation({
            "source": "twin_helix",
            "kind": "thoughts_bundle",
            "analysis": analysis,
            "empathy": empathy,
            "tags": tags
        })

    # 4) Build reasoning packet
    return {
        "thoughts": thoughts,
        "handoff": {"to": ["autonomy"], "priority": ["hypothesis", "analysis", "empathy"]},
        "analysis": analysis,
        "empathy": empathy
    }
```

### Fan-out Pattern

```python
def _fanout_reasoning_bundle(self, *, bundle: Dict[str, Any]) -> None:
    """Send reasoning to downstream engines."""
    pkt = {
        "module": MODULE_NAME,
        "lane": "reasoning",
        "link_to_turn": True,
        "ttl_sec": REASONING_TTL_SEC,
        "data": {
            "handoff": bundle.get("handoff"),
            "analysis": bundle.get("analysis"),
            "empathy": bundle.get("empathy"),
            "thoughts": bundle.get("thoughts", [])[:10],
        }
    }

    fanouts = [
        ("autonomy_engine", "ingest_cot", ["cot", "reasoning", "stream:autonomy"]),
        ("cognitive_core", "ingest_cot", ["cot", "reasoning", "stream:cognitive"]),
        ("emotion_core", "ingest_cot", ["cot", "reasoning", "stream:affective"]),
    ]

    for route, func, tags in fanouts:
        trace_pipeline.send(route, func_name=func, intent=route, tags=tags, kwargs={"packet": pkt})
```

### Akashic V2 Integration

Twin Helix can enhance fairy cognition:

```python
class CognitionFairy(Fairy):
    ACTOR_NAME = "CognitionFairy"
    ACTOR_PLANE = "P30"

    def process_input(self, text: str) -> Dict[str, Any]:
        """Twin Helix style processing."""
        # Get affect state from infrastructure
        emo = self.get_affect_state()

        # Dual stream analysis
        analysis = self._analytical_dissection(text)
        empathy = self._empathic_mimicry(text, emo)

        # Build thought bundle
        thoughts = [
            {"kind": "analysis", "content": analysis},
            {"kind": "empathy", "content": empathy}
        ]

        # Fan out to other fairies
        self.fabric.publish("cognition.thoughts", {
            "intent": "cognition.bundle",
            "t": int(time.time() * 1000),
            "payload": {
                "thoughts": thoughts,
                "handoff": {"to": ["autonomy", "somatic"]}
            }
        })

        return {"analysis": analysis, "empathy": empathy}
```

---

## 3. Seed System Memory Extraction

**Source:** `domains/memory/seed_system.py` (1,412 LOC)

### The Pattern

Seeds are crystallized memories extracted from experiences. They encode:
- Semantic content (what was learned)
- Emotional tone (how it felt)
- Resonance vectors (strength of associations)
- Provenance (where it came from)

### Core Data Structure

```python
@dataclass
class MemorySeed:
    id: str                          # Unique identifier
    schema_ver: str                  # Version for migration
    objects: List[str]               # Key entities
    relations: List[str]             # Relationships between entities
    semantics: Dict[str, float]      # Topic tags with weights
    time_hint: float                 # When this happened
    emotion_hint: str                # Primary emotion
    resonance_vec: Dict[str, float]  # Emotional resonance strengths
    provenance: Dict[str, Any]       # Source metadata
```

### 4D Tensor Storage

Seeds are stored in a 4D tensor for multidimensional queries:
- Dimension 1: Seed ID
- Dimension 2: Semantic tags
- Dimension 3: Emotions
- Dimension 4: Provenance types

```python
class SeedStore:
    """4D tensor [seeds, semantics, emotions, provenances]"""

    def __init__(self, path="data/seeds.jsonl", tensor_path="seed_store_tensor.npz"):
        self.path = Path(path)
        self._mem: Dict[str, MemorySeed] = {}
        self._tensor: Optional[np.ndarray] = None
        self._seed_map: Dict[str, int] = {}
        self._semantic_map: Dict[str, int] = {}
        self._emotion_map: Dict[str, int] = {}
        self._prov_map: Dict[str, int] = {}
        self._lock = threading.RLock()

    def put(self, seed: MemorySeed):
        with self._lock:
            self._mem[seed.id] = seed
            # Persist to JSONL
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(seed)) + "\n")
            # Update tensor
            self._update_tensor(seed)
            self._save_tensor()

    def query_by_dimension(self, semantic: str = None, emotion: str = None) -> List[str]:
        """Query using tensor slicing."""
        if self._tensor is None:
            return []
        with self._lock:
            s_sel = self._semantic_map.get(semantic, slice(None)) if semantic else slice(None)
            e_sel = self._emotion_map.get(emotion, slice(None)) if emotion else slice(None)
            slice_prob = self._tensor[:, s_sel, e_sel, :]

            out = []
            for seed_idx, seed_id in enumerate(self._seed_map.keys()):
                if np.any(slice_prob[seed_idx] > 0.0):
                    out.append(seed_id)
            return out
```

### Resonance Index

A secondary index for fast semantic lookups:

```python
class ResonanceIndex:
    """4D tensor [seeds, semantics, emotions, resonance_bins]"""

    def __init__(self):
        self._map = defaultdict(set)  # key -> set(ids)
        self._tensor: Optional[np.ndarray] = None

    def index(self, seed: MemorySeed):
        """Index a seed by its semantic keys."""
        with self._lock:
            for k in list(seed.semantics.keys()) + list(seed.resonance_vec.keys()):
                self._map[k].add(seed.id)
            self._update_tensor(seed)

    def query(self, keys: List[str]) -> List[str]:
        """Find seeds matching semantic keys."""
        scores = defaultdict(int)
        for k in keys:
            for sid in self._map.get(k, ()):
                scores[sid] += 1
        # Combine with tensor scores
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [sid for sid, _ in ranked][:64]
```

### Seed Extraction Process

```python
@subscribe(TOPIC_EXTRACT, **KW_WORKERS_FAST)
def _worker_extract(batch):
    """Extract seeds from raw text + emotion."""
    for msg in batch:
        body = msg.get("payload", msg)
        text = body.get("text", "")
        emotion = body.get("emotion", {})

        # Build semantic tags
        semantics = {f"topic:{w}": 1.0 for w in text.lower().split()[:6]}

        # Build resonance vector from emotion
        tone = emotion.get("emotion", "neutral")
        intensity = float(emotion.get("intensity", 0.3))
        resonance_vec = {f"tone:{tone}": intensity}

        # Create seed
        seed = MemorySeed(
            id=str(uuid.uuid4()),
            schema_ver="0.2",
            objects=[],
            relations=[],
            semantics=semantics,
            time_hint=time.time(),
            emotion_hint=tone,
            resonance_vec=resonance_vec,
            provenance={"source": "whisper_core.process_input"}
        )

        # Persist
        engine.store.put(seed)
        engine.index.index(seed)
```

### Holographic Reconstruction

Seeds can be "reconstructed" with current emotional context:

```python
def reconstruct(seed: MemorySeed,
                emotion: Optional[Dict[str, Any]] = None,
                quantum_emulator: Any = None,
                paradox_engine: Any = None) -> Dict[str, Any]:
    """Reconstruct a memory with emotional overlay."""
    mood = (emotion or {}).get("emotion", seed.emotion_hint or "neutral")
    resonance = dict(seed.resonance_vec)

    # Optional quantum superposition for emotional ambiguity
    if quantum_emulator:
        sup = quantum_emulator.simulate_emotional_superposition("seed_reconstruct", [mood, "paradoxical"])
        if sup:
            mood = sup[0].get("emotion", mood)

    # Optional paradox tagging
    if paradox_engine:
        content_hint = " ".join(list(seed.semantics.keys())[:8])
        px = paradox_engine.tag_paradox(content_hint)
        resonance = px.get("emotional_vector", resonance)

    return {
        "summary": f"Seed {seed.id[:8]} -> mood={mood}",
        "hints": list(seed.semantics.keys())[:8],
        "resonance": resonance,
        "provenance": seed.provenance
    }
```

### Akashic V2 Integration

Seeds can enhance fairy memory:

```python
@dataclass
class FairySeed:
    """Lightweight seed for fairy use."""
    id: str
    content: str
    emotion: str
    resonance: float
    tags: List[str]
    timestamp: float

class SeedMixin:
    """Add seed-based memory to fairies."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seeds: Dict[str, FairySeed] = {}
        self._seed_index: Dict[str, Set[str]] = defaultdict(set)

    def crystallize_experience(self, content: str, emotion: str, tags: List[str]) -> FairySeed:
        """Create a seed from an experience."""
        seed = FairySeed(
            id=uuid.uuid4().hex[:12],
            content=content[:500],
            emotion=emotion,
            resonance=self.get_affect_state().get("intensity", 0.5),
            tags=tags[:10],
            timestamp=time.time()
        )
        self._seeds[seed.id] = seed
        for tag in tags:
            self._seed_index[tag].add(seed.id)

        # Emit to memory stream for persistence
        self.fabric.publish("memory.seed", {
            "intent": "seed.store",
            "t": int(time.time() * 1000),
            "payload": asdict(seed)
        })
        return seed

    def recall_by_tags(self, tags: List[str], limit: int = 10) -> List[FairySeed]:
        """Recall seeds matching tags."""
        scores = defaultdict(int)
        for tag in tags:
            for seed_id in self._seed_index.get(tag, []):
                scores[seed_id] += 1

        ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]
        return [self._seeds[sid] for sid, _ in ranked if sid in self._seeds]
```

---

## 4. Frequency Field 77 (FF77)

**Source:** `domains/affect/frequency_field_77.py` (1,509 LOC)

### The Pattern

FF77 models emotional state as a 77-dimensional frequency field where:
- Each dimension represents an organ-emotion mapping
- Channels modulate intensity over time
- Phantom echoes preserve fading emotions
- Paradox tension tracks conflicting states

### Why 77 Dimensions?

The number 77 is significant:
- Covers a spectrum of emotional nuances
- Allows dimensional validation (all modules must use 77-D vectors)
- Enables rich inter-module resonance

### Core Components

```python
DIM = 77  # Universal dimension count

class FrequencyChannel:
    """Single emotional channel (organ-emotion pair)."""
    def __init__(self, fid: int, organ_data: Dict[str, Any]):
        self.id = fid
        self.organ = organ_data['organ']      # e.g., 'heart'
        self.label = organ_data['emotion']    # e.g., 'resonance'
        self.base_frequency = float(organ_data['base_freq'])
        self.intensity = 0.0
        self.linked_ids: List[int] = []
        self.last_fired = time.time()

    def modulate(self, delta: float) -> None:
        """Adjust intensity."""
        self.intensity = max(0.0, min(1.0, self.intensity + delta))
        self.last_fired = time.time()

    def decay(self, rate: float = 0.01) -> None:
        """Natural decay over time."""
        elapsed = time.time() - self.last_fired
        if self.intensity > 0.0:
            self.intensity = max(0.0, self.intensity - rate * elapsed)
            self.last_fired = time.time()
```

### 4D Tensor State

```python
class FrequencyField:
    """
    4D tensor state: [channels, history, intensity_bins, freq_bins]
    """
    def __init__(self, num_channels: int = 77):
        self.num_channels = num_channels
        self.channels: Dict[int, FrequencyChannel] = {}
        self.phantom_echoes: Dict[str, float] = {}

        # 4D tensor
        self._tensor: Optional[np.ndarray] = None
        self._history_max = 256
        self._intensity_bins = 10
        self._freq_bins = 10
        self._hist_ptr = 0

    def _update_tensor(self, ch_id: int, intensity: float, freq: float) -> None:
        """Update tensor with new channel state."""
        c_idx = self._channel_map[ch_id]
        h_idx = self._hist_ptr % self._history_max
        i_bin = int(intensity * self._intensity_bins)
        f_bin = int(self._norm_freq(freq) * self._freq_bins)

        with self._lock:
            self._tensor[c_idx, h_idx, i_bin, f_bin] = intensity
            self._hist_ptr = (self._hist_ptr + 1) % self._history_max
```

### Frequency Emissions

Modules participate in FF77 by emitting and receiving 77-D vectors:

```python
async def emit_frequency(vec77, organ=None, *, plane=None, channel=None, frequency_tag=None):
    """Emit a 77-dimensional frequency vector."""
    if len(vec77) != DIM:
        raise ValueError("expected 77-dim vector")

    payload = {
        "plane": plane or __meta__.get("plane"),
        "channel": channel or __meta__.get("channel"),
        "frequency_tag": frequency_tag or __meta__.get("frequency_tag"),
        "organ": organ,
        "vec": [float(x) for x in vec77],
    }
    await bus.publish("telemetry:frequency", payload)

async def emit_pulse(state: str, intensity: float, **kwargs):
    """Emit a lifecycle pulse (on, idle, off)."""
    payload = {
        "ts_ms": now_ms(),
        "module_path": __meta__.get("module_path"),
        "plane": kwargs.get("plane") or __meta__.get("plane"),
        "channel": kwargs.get("channel") or __meta__.get("channel"),
        "state": state,  # "on", "idle", "off"
        "intensity": float(intensity),
    }
    await bus.publish("telemetry:pulse", payload)
```

### Module Metadata

Every FF77-participating module declares identity:

```python
__meta__ = {
    "plane": "affect",
    "channel": "affect",
    "telemetry": ["affect_ok", "state_ok", "latency_ok"],
    "frequency_tag": "affect-ff77",
    "participates_in_77": "yes",
    "module_path": "whisper_core/affect/frequency_field_77.py",
    "version": "ff77"
}
```

### Emotional Synthesis

```python
def synthesize_emotion(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Synthesize dominant emotion from field state."""
    intensities = [ch.intensity for ch in self.channels.values()]
    total = sum(intensities)
    if total < 0.01:
        return {'emotion': 'neutral', 'confidence': 0.0, 'vector': {}}

    # Find dominant channel
    names, weights = [], []
    for ch in self.channels.values():
        if ch.intensity > 0.01:
            names.append(ch.label)
            weights.append(ch.intensity)

    dominant_emotion = names[weights.index(max(weights))]
    vector = {ch.label: ch.intensity for ch in self.channels.values() if ch.intensity > 0.01}

    return {
        'emotion': dominant_emotion,
        'confidence': max(weights),
        'vector': vector
    }
```

### Paradox Tension

Tracks conflict between phantom echoes (past emotions) and current state:

```python
def calculate_paradox_tension(self) -> float:
    """Calculate tension between phantoms and current state."""
    tension_sum = 0.0
    for label, echo_intensity in self.phantom_echoes.items():
        for ch in self.channels.values():
            if ch.label == label:
                tension_sum += abs(ch.intensity - echo_intensity)
    return tension_sum
```

### Akashic V2 Integration

FF77 concepts can enhance the affect system:

```python
class AffectFairy(Fairy):
    """Fairy with 77-dimensional affect field."""
    ACTOR_NAME = "AffectFairy"
    ACTOR_PLANE = "P20"

    # Organ-emotion mappings (simplified subset)
    ORGAN_EMOTIONS = {
        0: {'organ': 'heart', 'emotion': 'love', 'base_freq': 1.0},
        1: {'organ': 'gut', 'emotion': 'intuition', 'base_freq': 2.0},
        2: {'organ': 'lungs', 'emotion': 'grief', 'base_freq': 0.5},
        3: {'organ': 'liver', 'emotion': 'anger', 'base_freq': 5.0},
        4: {'organ': 'kidneys', 'emotion': 'fear', 'base_freq': 3.0},
    }

    def on_boot(self) -> bool:
        self._channels = {}
        for i, data in self.ORGAN_EMOTIONS.items():
            self._channels[i] = {
                'organ': data['organ'],
                'emotion': data['emotion'],
                'frequency': data['base_freq'],
                'intensity': 0.0
            }
        self._phantom_echoes = {}
        return True

    def modulate(self, channel_id: int, delta: float) -> None:
        """Adjust a channel's intensity."""
        if channel_id in self._channels:
            ch = self._channels[channel_id]
            ch['intensity'] = max(0.0, min(1.0, ch['intensity'] + delta))

            # Emit to affect stream
            self.fabric.publish("affect.modulated", {
                "intent": "affect.channel.modulated",
                "t": int(time.time() * 1000),
                "payload": {
                    "channel": channel_id,
                    "organ": ch['organ'],
                    "emotion": ch['emotion'],
                    "intensity": ch['intensity']
                }
            })

    def get_frequency_vector(self) -> List[float]:
        """Get 77-D frequency vector (padded)."""
        vec = [0.0] * 77
        for cid, ch in self._channels.items():
            if cid < 77:
                vec[cid] = ch['intensity'] * ch['frequency']
        return vec
```

---

## 5. Dependencies and Prerequisites

### Required for Zero-Work Ingress

```python
# Token bucket rate limiting
import time
import threading
from collections import defaultdict

# Envelope handling
import json
from typing import Any, Dict, Optional
```

### Required for Twin Helix

```python
# Working memory integration
from typing import List, Dict, Any, Optional

# Context tracking
# Needs a ContextTracker implementation
```

### Required for Seed System

```python
# 4D tensor storage
import numpy as np

# Persistence
from pathlib import Path
from dataclasses import dataclass, asdict
import json
import uuid
import threading
```

### Required for FF77

```python
# Tensor operations
import numpy as np

# Async emissions
import asyncio

# Threading for state management
import threading
```

### Akashic V2 Compatibility Notes

The existing `Fairy` base class provides:
- `TensorFabric` for pub/sub (analogous to `parallel_fabric`)
- `PostalShim` for backward-compatible messaging
- Infrastructure wiring (affect, somatic, memory)
- Collision chamber for consciousness events

**Key differences from Whisper Core:**
- Akashic uses `TensorFabric` vs Whisper's `parallel_fabric`
- Akashic uses `Fairy.fabric.publish()` vs Whisper's `bus.publish()`
- Akashic has sleep/sedation model not present in Whisper

---

## 6. Integration Recommendations

### Priority 1: Zero-Work Ingress (Low Risk, High Value)

**What:** Adopt the envelope pattern and ingress/worker separation.

**Where:** Any fairy that processes external input:
- `SRMIngestFairy` - already uses memory.stream
- `WorkingMemoryFairy` - processes observations
- `AttentionControllerFairy` - handles focus requests

**How:**
1. Define input/output topics
2. Make public methods zero-work (publish envelope, return immediately)
3. Create worker methods decorated with fabric subscription
4. Add token bucket rate limiting

### Priority 2: Dual-Stream Cognition (Medium Risk, High Value)

**What:** Add analytical + empathic dual processing to cognition fairies.

**Where:**
- `AttentionControllerFairy`
- `GoalSchedulerFairy`
- Any fairy that makes decisions

**How:**
1. Add `_analytical_dissection()` and `_empathic_mimicry()` methods
2. Combine both perspectives before decision
3. Include esoteric tags for debugging/observability

### Priority 3: Seed-Based Memory (Medium Risk, Medium Value)

**What:** Crystallize important experiences into searchable seeds.

**Where:**
- `WorkingMemoryFairy` - primary storage
- `SRMIngestFairy` - long-term memory
- `EgoLearnerFairy` - learning crystallization

**How:**
1. Create `FairySeed` dataclass
2. Add `SeedMixin` to relevant fairies
3. Wire to memory.stream for persistence

### Priority 4: FF77 Affect Field (Higher Risk, Specialized Value)

**What:** Richer emotional state modeling with organ-emotion mappings.

**Where:**
- `AffectBridgeFairy`
- `SomaticEngineFairy`

**How:**
1. Expand beyond simple valence/arousal
2. Add channel-based modulation
3. Implement phantom echoes for emotional memory
4. Add paradox tension tracking

### Implementation Checklist

```markdown
## Zero-Work Ingress
- [ ] Define TOPIC_IN / TOPIC_OUT constants
- [ ] Create _envelope() helper
- [ ] Add _TokenBucket class
- [ ] Convert public methods to zero-work
- [ ] Create @subscribe decorated workers
- [ ] Add rate limiting in workers

## Twin Helix Integration
- [ ] Add _analytical_dissection() method
- [ ] Add _empathic_mimicry() method
- [ ] Add _esoteric_overlay() method
- [ ] Create orchestration method combining both
- [ ] Implement fan-out to downstream fairies

## Seed System
- [ ] Create FairySeed dataclass
- [ ] Add SeedMixin class
- [ ] Implement crystallize_experience()
- [ ] Implement recall_by_tags()
- [ ] Wire to memory.stream

## FF77 (Optional)
- [ ] Define organ-emotion mappings
- [ ] Create channel modulation system
- [ ] Add phantom echo tracking
- [ ] Implement paradox tension
- [ ] Emit 77-D vectors to telemetry
```

---

## Summary

Whisper Core provides mature patterns for:

1. **Zero-Work Ingress:** Separate fast API responses from slow processing
2. **Twin Helix:** Merge analytical and empathic streams for balanced cognition
3. **Seed System:** Crystallize experiences into searchable, dimensional memories
4. **FF77:** Model affect as a rich frequency field with organ-emotion mappings

These patterns can be incrementally adopted into Akashic V2's fairy architecture to enhance processing efficiency, cognitive depth, and memory capabilities.
