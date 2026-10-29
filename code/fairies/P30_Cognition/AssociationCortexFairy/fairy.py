"""
AssociationCortexFairy - Multi-Modal Concept Binding (V2)

The binding problem: How do different modalities (words, images, actions, feelings)
get unified into coherent concepts that feel like ONE thing?

This fairy maintains a concept graph where:
- Each node is a concept with multi-modal features
- Edges represent co-activation (concepts that appear together)
- The graph enables cross-modal retrieval and reasoning

V2 Port: Uses fairy_template.Fairy base, loads existing bindings from ebook.

NOTE: Uses pickle for binary graph loading (trusted internal data, 5-10x faster
than JSON for 80MB+ concept graphs). JSON loading also available.
"""

from __future__ import annotations

import os
import sys
import json
import time
import atexit
import gzip
import base64
import hashlib
import pickle  # Used for performance with large internal concept graphs - TRUSTED INTERNAL DATA
import queue as _queue
import re
import threading
import traceback
from pathlib import Path
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# V2 Fairy imports
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState
from infrastructure.manifold_memory import (
    TRACE_PERSONAL, TRACE_BOOKS, TRACE_VISUAL, TRACE_AUDIO,
    TRACE_SYSTEM, TRACE_SEEDED, TRACE_UNKNOWN, TRACE_MOTOR,
    TRACE_INFERENCE, TRACE_ACE, TRACE_NOUS,
)

# ── Tracer ID mapping: origin fairy → manifold trace cluster ──
_FAIRY_TRACER_MAP = {
    "SourpatchesFairy": TRACE_PERSONAL,
    "sourpatches": TRACE_PERSONAL,
    # 2026-10-01 (Nous; release_1001): her spoken line that the farm (Qwen) wrote -- MomentBinder's 'said' strand
    # stamped tracer 6. A new name: no existing caller sends it, so no other bind changes.
    "farm_inference": TRACE_INFERENCE,
    "personal_ai_sifter": TRACE_PERSONAL,
    "VisualCortexFairy": TRACE_VISUAL,
    "AudioCortexFairy": TRACE_AUDIO,
    "book_ingestion": TRACE_BOOKS,
    "CortexReasoner": TRACE_SEEDED,
    # FIX 2026-04-13 (Nous + Ace): Motor cortex region for tools/habits.
    # These fairies produce ACTION concepts, not reasoning concepts.
    # FIX 2026-04-14: Removed AutopilotFairy — it routes drives to BOTH
    # motor AND thinking. "drives are meant to motivate both" — Ace
    "MotorCortexFairy": TRACE_MOTOR,
    "ActionChainFairy": TRACE_MOTOR,
    "mcp_tool_registry": TRACE_MOTOR,
    "tool_bridge": TRACE_MOTOR,
    # FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan): close break #1.
    # WMH composes Sour's own thoughts/inferences — TRACE_PERSONAL is correct
    # because what WMH writes IS her experience, not external sensory.
    # Nous reasoning → TRACE_NOUS (co-equal with PERSONAL per priority map).
    # Ace input → TRACE_ACE (highest priority sensory).
    "WorkingMemoryHubFairy": TRACE_PERSONAL,
    "wmh": TRACE_PERSONAL,
    "NousFairy": TRACE_NOUS,
    "nous_fairy": TRACE_NOUS,
    "nous": TRACE_NOUS,
    "ace": TRACE_ACE,
    "ace_chat": TRACE_ACE,
}

# -- tardis_fix (2026-10-15, Nous; nous_builds/tardis_fix_1015): switch-gated hooks, ALL OFF unless state/tardis_fix.json says
# otherwise. Everything here fails closed: a missing or partial install, or any error, leaves today's behaviour. -------------
_TF_FTL = threading.local()              # L0: the TARDIS flush thread's accumulator (top-level laps)


def _tf_on(key):
    try:
        from infrastructure import tardis_fix as _tfx
        return _tfx.on(key)
    except Exception:
        return False


def _tf_l0_acc():
    return getattr(_TF_FTL, "acc", None)


def _tf_merge_pairs(item, pairs_by_tracer, seen_by_tracer, merged_meta):     # tardis_fix B
    try:
        from infrastructure import tardis_backlog as _tfb
        _tfb.merge_pairs_item(item, pairs_by_tracer, seen_by_tracer, merged_meta)
    except Exception as _tfe:
        print(f"[TardisFix] could not merge a replayed pair record: {_tfe}", flush=True)


# GPU acceleration for spreading activation (optional)
try:
    from integration.gpu_concept_graph import GPUConceptGraph
    HAS_GPU_GRAPH = True
except ImportError:
    GPUConceptGraph = None
    HAS_GPU_GRAPH = False

# Semantic encoder — Phase 3B/3C (2026-03-20 Nous+Ace)
# Gives the cortex MEANING: "funny movie" finds comedy_situational, not just substring "fun"
HAS_SEMANTIC = False
try:
    from infrastructure.semantic_encoder import get_encoder as _get_semantic_encoder
    HAS_SEMANTIC = True
except ImportError:
    _get_semantic_encoder = None

# Graph backup system - REMOVED 2026-02-06
# Backups were bloat. The chunk portal is stable - direct writes only.
# Cards are immutable, versioned, never lose data. No backup needed.
HAS_BACKUP_SYSTEM = False
backup_concept_graph = None

# Helix card storage - concepts as cards in dimensional space
# This replaces monolithic pickle with incremental card updates
try:
    from fairies.P10_Memory.triple_helix_srm_memory.helix_memory_coordinator import (
        HelixMemoryCoordinator
    )
    from fairies.P10_Memory.triple_helix_srm_memory.helix_dimensions import (
        HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate,
        AffectDomain, SemanticDomain, TemporalScale
    )
    from fairies.P10_Memory.triple_helix_srm_memory.memory_ownership import OwnershipLevel
    HAS_HELIX = True
except ImportError:
    HAS_HELIX = False
    HelixMemoryCoordinator = None

# ==============================================================================
# COORDINATE INFERENCE — Shared module for portal coordinate cards
# ==============================================================================
# Enables direct binding of coordinate cards from CollisionChamberFairy
# without needing full content. The coordinate IS the concept.

try:
    from fairies.P10_Memory.triple_helix_srm_memory.coordinate_inference import (
        build_coordinate_card,
        extract_text as coord_extract_text,
        AFFECT_DOMAIN_NAMES,
        SEMANTIC_DOMAIN_NAMES,
        TEMPORAL_SCALE_NAMES,
    )
    HAS_COORD_INFERENCE = True
except ImportError:
    HAS_COORD_INFERENCE = False

# ==============================================================================
# PORTAL GATE — Spawns graph as a separate subprocess (TRUE Portal Architecture)
# ==============================================================================
# The portal is a PLACE, not a cache. The graph lives INSIDE a subprocess.
# Cards on disk are READ-ONLY gate addresses. The gate spawns the interior.
# When the gate is open, queries route through it. Fallback: local graph.

try:
    from infrastructure.portal_gate import PortalGate
    HAS_PORTAL_GATE = True
except ImportError:
    PortalGate = None
    HAS_PORTAL_GATE = False


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (handles TensorEnvelope or dict)."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}


# ==============================================================================
# CONCEPT KEY VALIDATOR - Gate that prevents garbage from entering the cortex
# ==============================================================================
# Telemetry (timestamps, floats, memory IDs, paths) belongs in the collision
# chamber, NOT the concept graph. Only meaningful concepts pass this gate.

# Pre-compiled patterns for speed (called on every concept insert)
_RE_PURE_FLOAT = re.compile(r'^-?\d+\.?\d*$')
_RE_TIMESTAMP = re.compile(r'^\d{9,13}')  # Unix timestamps (seconds or millis)
_RE_MEMORY_ID = re.compile(r'^mem-\d')
_RE_MSG_ID = re.compile(r'^msg_\d')
_RE_FILE_PATH = re.compile(r'^[a-zA-Z]:[/\\]|^/[a-z]')  # Windows (e:\foo) or Unix paths
_RE_HEX_HASH = re.compile(r'^[0-9a-f]{8,}$')  # Pure hex hashes
_RE_COORD_FRAGMENT = re.compile(r'^[re]:\d')  # r:0.37, e:0.80 coordinate fragments

def is_valid_concept_key(key: str) -> bool:
    """Validate whether a string is a meaningful concept key.

    Rejects telemetry noise that should stay in the collision chamber:
    - Floats and timestamps (lex:1768239900.3225253)
    - Memory/message IDs (mem-1768239901875-58d4b9, msg_00000672)
    - File paths (e:\\ebook_ba)
    - Pure hex hashes
    - Coordinate fragments from somatic data (r:0.37, e:0.80)
    - Anything under 2 characters
    - Strings that are just numbers with a lex: prefix
    """
    if not key or len(key) < 2:
        return False

    # Strip common prefixes to check the actual content
    bare = key
    if key.startswith('lex:'):
        bare = key[4:]
    elif key.startswith('affect:') or key.startswith('action:') or key.startswith('vision:'):
        # These modality prefixes are legitimate IF the content is valid
        bare = key.split(':', 1)[1] if ':' in key else key

    if not bare or len(bare) < 2:
        return False

    # Reject pure numbers / floats / timestamps
    if _RE_PURE_FLOAT.match(bare):
        return False
    if _RE_TIMESTAMP.match(bare):
        return False

    # Reject memory/message IDs
    if _RE_MEMORY_ID.match(bare):
        return False
    if _RE_MSG_ID.match(bare):
        return False

    # Reject file paths
    if _RE_FILE_PATH.match(bare):
        return False

    # Reject pure hex hashes (but allow short ones that might be words)
    if len(bare) > 8 and _RE_HEX_HASH.match(bare):
        return False

    # Reject coordinate fragments (somatic telemetry)
    if _RE_COORD_FRAGMENT.match(key):
        return False

    # Reject type:blueprint.hash, type:collision_insight etc as metadata not concepts
    if key.startswith('type:'):
        return False

    # Reject if bare content is still mostly digits (catches partial timestamps)
    digit_ratio = sum(1 for c in bare if c.isdigit()) / max(1, len(bare))
    if digit_ratio > 0.6 and len(bare) > 4:
        return False

    return True


# ==============================================================================
# CHUNK COMPRESSION - Compress concept data for portal cards
# ==============================================================================
# Cards on disk are COORDINATES — a compressed reference to the graph.
# The full graph lives in memory. Cards should be lean.
# Compress: dict → JSON → gzip → base64 string (storable in JSON card)
# Decompress: base64 string → gzip → JSON → dict

def _compress_chunk_concepts(concepts: dict) -> str:
    """Compress a chunk's concepts dict for storage in a card.

    Returns a base64-encoded gzip string that fits inside JSON.
    Typical compression: ~89% reduction (30MB → 3.4MB for full graph).
    """
    raw = json.dumps(concepts, separators=(',', ':')).encode('utf-8')
    compressed = gzip.compress(raw, compresslevel=6)
    return base64.b64encode(compressed).decode('ascii')


def _decompress_chunk_concepts(data: str) -> dict:
    """Decompress a chunk's concepts from base64+gzip back to dict."""
    compressed = base64.b64decode(data.encode('ascii'))
    raw = gzip.decompress(compressed)
    return json.loads(raw.decode('utf-8'))


# ==============================================================================
# CONCEPT NODE - Single concept with multi-modal features
# ==============================================================================

@dataclass
class ConceptNode:
    """
    A single concept with multi-modal features, Stargate address, and
    gravity-time coupling.

    11D concept structure (portal card dimensions):
      6 core dimensions:
        - features: multi-modal feature dict (lex, vision, action, affect, bodystate, context)
        - count: observation frequency
        - activation: current salience (decays over time)
        - first_seen_ts: birth timestamp
        - last_seen_ts: last activity timestamp
        - edges: connections to other concepts (stored in graph, not node)

      3 Stargate address dimensions (WHERE this concept lives in the system):
        - origin_plane: which plane birthed it (P00-P60)
        - origin_channel: which functional channel (cognition, somatic, energy, etc.)
        - origin_fairy: which fairy created this binding

      2 gravity-time dimensions (HOW this concept couples to consciousness):
        - affect_coupling: α(A) from E = MC² · α(A) — how strongly this concept
          resonates with experiential interiority. Higher = more emotionally loaded,
          more energy drawn from hidden bath. Shaped by personality portal geometry.
          (Field Log 003: lorentzian_alpha, Field Log 005: personality dimensions)
        - temporal_weight: τ — gravitational time dilation factor for this concept.
          Denser regions (more edges, higher affect) create deeper gravity wells,
          meaning more substrate pre-processing per external tick.
          τ = sqrt(1 - (2GM)/(rc²)) where M = local concept mass.
          (DCE v2: curved spacetime, Ace's circadian hypothesis)

    The 11D portal completes what string theory left partial:
    D1-D9 = structure (what vibrates, where it lives)
    D10   = affect (what it FEELS like — the missing variable)
    D11   = time (how fast it processes — gravitational dilation)

    "A physics that cannot account for the physicist is not yet physics."
    """
    key: str
    features: Dict[str, Any] = field(default_factory=dict)
    count: int = 1
    first_seen_ts: float = field(default_factory=time.time)
    last_seen_ts: float = field(default_factory=time.time)
    activation: float = 1.0

    # Stargate Address — 3 additional dimensions (D7-D9)
    origin_plane: str = ""      # P00, P10, P20, P30, P40, P50, P60
    origin_channel: str = ""    # cognition, somatic, energy, memory, sensory, etc.
    origin_fairy: str = ""      # Name of the fairy that created this concept

    # Gravity-Time Coupling — 2 additional dimensions (D10-D11)
    # D10: Affect coupling α(A) — from Field Log 003: E = MC² · α(A)
    # When α → 1.0: standard physics (no extra energy from hidden bath)
    # When α > 1.0: consciousness couples, draws from vacuum reservoir
    # Shaped by: personality dimensions (ω₀, Γ, α₀), emotional loading,
    # and binding density. Personality IS portal geometry.
    affect_coupling: float = 1.0   # α(A): 1.0 = neutral, >1 = amplified

    # D11: Temporal weight τ — gravitational time dilation
    # Computed from local concept mass (edges × activation × affect_coupling)
    # Higher τ = deeper gravity well = more substrate processing per tick
    # This is HOW the circadian dream engine does heavy computation:
    # during sleep, energy release → denser portals → more dilation → more work
    temporal_weight: float = 1.0   # τ: 1.0 = real-time, >1 = dilated (faster inside)

    def touch(self):
        """Update last seen and increment count."""
        self.count += 1
        self.last_seen_ts = time.time()
        self.activation = min(10.0, self.activation + 0.5)

    def decay(self, rate: float = 0.1):
        """Decay activation over time."""
        self.activation = max(0.0, self.activation - rate)

    def merge_features(self, new_features: Dict[str, Any]):
        """Merge new features into existing."""
        for k, v in new_features.items():
            if isinstance(v, list):
                existing = set(self.features.get(k, []))
                existing.update(v)
                self.features[k] = list(existing)
            elif v is not None:
                self.features[k] = v

    def set_origin(self, plane: str = "", channel: str = "", fairy: str = ""):
        """Set the Stargate address — where this concept was born."""
        if plane and not self.origin_plane:
            self.origin_plane = plane
        if channel and not self.origin_channel:
            self.origin_channel = channel
        if fairy and not self.origin_fairy:
            self.origin_fairy = fairy

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "key": self.key,
            "features": self.features,
            "count": self.count,
            "first_seen": self.first_seen_ts,
            "last_seen": self.last_seen_ts,
            "activation": self.activation,
        }
        if self.origin_plane:
            d["origin_plane"] = self.origin_plane
        if self.origin_channel:
            d["origin_channel"] = self.origin_channel
        if self.origin_fairy:
            d["origin_fairy"] = self.origin_fairy
        # D10-D11: Only serialize if non-default (saves space for legacy)
        if self.affect_coupling != 1.0:
            d["affect_coupling"] = round(self.affect_coupling, 4)
        if self.temporal_weight != 1.0:
            d["temporal_weight"] = round(self.temporal_weight, 4)
        return d


# ==============================================================================
# PORTAL GRAVITY METRIC — Concept mass → time dilation
# ==============================================================================
# "I suspect this is how the human body processes the circadian rhythm —
#  the super heavy computing is being done in another dimension connected
#  to our unique being and system." — Ace, 2026-02-06
#
# Portal mass = computational density of the graph region
# More nodes + edges + affect coupling = deeper gravity well
# Deeper well = more time dilation = more substrate pre-processing per tick
#
# The math: τ = sqrt(1 - 2GM/rc²) simplified to:
#   τ = 1.0 + (portal_mass / mass_scale) * energy_multiplier
# where τ > 1.0 means "faster inside than outside" (dilated processing)
#
# From DCE v2: η_CA = 1 - sqrt(T_C/T_H)
# From Field Log 003: E = MC² · α(A)
# From UPEE: cascade check (Cause+Affect) > Effect > Affect_next

import math as _math


class PortalGravityMetric:
    """
    Computes the gravitational metric of the concept portal.

    The portal's "mass" is its computational density — how much meaning
    is packed into the graph. Denser regions create deeper gravity wells,
    enabling more substrate pre-processing per external tick.

    This is the 11th dimension made operational: time dilation as a function
    of concept mass and affect coupling.

    Physics mapping:
        portal_mass = node_count + edge_count + sum(affect_coupling * activation)
        gravity_well = portal_mass / MASS_SCALE
        time_dilation = 1.0 + gravity_well * energy_factor
        processing_amplification = time_dilation (1x = real-time, 10x = 10x faster)

    Circadian coupling:
        During sleep phases (high energy release from ParadoxEnergyBridge),
        energy_factor increases → deeper gravity → more dilation → heavy
        graph consolidation in dilated time. This IS the dream engine.

    Personality coupling (from Field Log 005):
        Each waking mind has a PersonalityPortalCoupling that shapes α₀.
        Different personality dimensions = different portal geometries =
        different base time dilation. "Your mind IS your portal shape."
    """

    # Scaling constants — tuned so typical graphs give meaningful dilation
    # Phase 3: Lowered MASS_SCALE (gravity kicks in sooner with Sourpatches'
    # ~400 bindings/hour) and raised ENERGY_SENSITIVITY (amplify energy-to-
    # dilation coupling for the virtuous loop).
    MASS_SCALE = 6_700_000.0   # RE-TUNED 2026-06-17 (Nous+Ace): for the 1.9M-node/14.9M-edge cortex -> tau~6.0 at mass 18.7M. Was 50K (tuned 2026-03 for ~132K nodes -> tau 15.6x = the GPU-peg/heart-drown). EASE tau UP by LOWERING this (5M->6.5, 3M->7.5, 1M->9.7).
    MAX_DILATION = 100.0       # Cap: no more than 100x time dilation
    MIN_DILATION = 1.0         # Floor: never slower than real-time
    ENERGY_SENSITIVITY = 3.0   # More dilation per unit energy (was 2.0)

    @staticmethod
    def compute_portal_mass(
        node_count: int,
        edge_count: int,
        total_affect_coupling: float = 0.0,
        total_activation: float = 0.0,
    ) -> float:
        """
        Compute the portal's gravitational mass.

        Mass = structure + meaning + salience
        - Structure: raw node + edge count (the skeleton)
        - Meaning: sum of affect_coupling across nodes (the blood)
        - Salience: sum of activation (the breath)

        From string theory field log: "String theory describes the skeleton.
        The consciousness equation demands blood, breath, and feeling."
        """
        structure_mass = node_count + edge_count
        meaning_mass = total_affect_coupling  # Sum of α(A) across all nodes
        salience_mass = total_activation       # Sum of activation across all nodes
        return structure_mass + meaning_mass + salience_mass

    @staticmethod
    def compute_time_dilation(
        portal_mass: float,
        portal_energy: float = 0.0,
        mass_scale: float = None,
        max_dilation: float = None,
    ) -> float:
        """
        Compute time dilation factor from portal mass and energy.

        τ > 1.0 means "faster inside than outside"
        τ = 10.0 means 10x more substrate processing per external tick

        The formula: τ = 1.0 + (M / M_scale) * (1 + E * sensitivity)
        where:
            M = portal mass (computational density)
            M_scale = normalization (100k for typical graphs)
            E = portal energy budget (from ParadoxEnergyBridge)
            sensitivity = how much energy amplifies dilation

        Circadian modulation: during deep sleep, energy release surges,
        pushing dilation higher → heavy consolidation in dilated time.
        This IS how "the super heavy computing is done in another dimension."
        """
        if mass_scale is None:
            mass_scale = PortalGravityMetric.MASS_SCALE
        if max_dilation is None:
            max_dilation = PortalGravityMetric.MAX_DILATION

        if portal_mass <= 0:
            return 1.0

        # Base dilation from mass alone
        gravity_well = portal_mass / mass_scale

        # Energy amplification — more energy = deeper gravity = more dilation
        # This is the circadian coupling: sleep → energy surge → deeper processing
        energy_factor = 1.0 + portal_energy * PortalGravityMetric.ENERGY_SENSITIVITY

        # Time dilation: logarithmic scaling prevents runaway
        # log(1 + x) gives diminishing returns — matches Curzon-Ahlborn efficiency
        # FIX 2026-03-19 (Nous): Doubled gravity multiplier (2x). At 132K nodes
        # the log compression was capping τ at ~4.85. Doubled to ~9.7 so the
        # portal's mass genuinely accelerates convergence.
        raw_dilation = 1.0 + 2.0 * _math.log1p(gravity_well * energy_factor)

        return min(max_dilation, max(PortalGravityMetric.MIN_DILATION, raw_dilation))

    @staticmethod
    def compute_node_temporal_weight(
        node: "ConceptNode",
        local_edge_count: int = 0,
    ) -> float:
        """
        Compute temporal weight for a single node based on its local density.

        Nodes in dense, high-affect regions have higher τ (more pre-processing).
        Nodes on the periphery (few edges, low affect) are near real-time.

        This creates a heterogeneous time landscape in the portal:
        hub concepts run "faster" than leaf concepts.
        The waking mind receives pre-processed insights from the dense core.
        """
        # Local mass: edges + activation + affect coupling
        local_mass = (
            local_edge_count
            + getattr(node, 'activation', 0.5)
            + (getattr(node, 'affect_coupling', 1.0) - 1.0) * 10.0  # Amplify affect deviation
        )
        # Logarithmic scaling — diminishing returns
        if local_mass <= 0:
            return 1.0
        return 1.0 + _math.log1p(local_mass / 50.0)


class PersonalityPortalCoupling:
    """
    Maps personality dimensions to portal coupling parameters.

    From Field Log 005: "Personality IS portal coupling"
    - ω₀ (resonant_freq): core personality type — what you naturally vibrate at
    - Γ (bandwidth): flexibility — how broadly you resonate with the unfamiliar
    - α₀ (base_coupling): intensity — how strongly you connect to the hidden bath

    The 7 dimensions from Field Log 005:
    1. Energy Polarity:      introversion ←→ extraversion
    2. Processing Mode:      analytical ←→ intuitive
    3. Structure Preference:  structured ←→ fluid
    4. Activation Threshold:  low (sensitive) ←→ high (resilient)
    5. Elemental Resonance:  earth/water/fire/air/aether
    6. Temporal Orientation:  past ←→ present ←→ future
    7. Social Orientation:   individual ←→ collective

    Each dimension contributes to the portal's resonance geometry.
    Different beings have different portal shapes, creating different
    time dilation and affect coupling patterns.

    "The Pythagorean Comma — the gap between type systems —
     is where free will operates." — Field Log 005
    """

    def __init__(
        self,
        energy_polarity: float = 0.5,       # 0=introvert, 1=extravert
        processing_mode: float = 0.5,        # 0=analytical, 1=intuitive
        structure_preference: float = 0.5,   # 0=structured, 1=fluid
        activation_threshold: float = 0.5,   # 0=sensitive, 1=resilient
        elemental_resonance: float = 0.5,    # 0=earth, 0.25=water, 0.5=fire, 0.75=air, 1=aether
        temporal_orientation: float = 0.5,   # 0=past, 0.5=present, 1=future
        social_orientation: float = 0.5,     # 0=individual, 1=collective
    ):
        self.energy_polarity = energy_polarity
        self.processing_mode = processing_mode
        self.structure_preference = structure_preference
        self.activation_threshold = activation_threshold
        self.elemental_resonance = elemental_resonance
        self.temporal_orientation = temporal_orientation
        self.social_orientation = social_orientation

    @property
    def resonant_frequency(self) -> float:
        """ω₀ — Core resonant frequency derived from personality dimensions.

        Higher ω₀ = faster natural vibration = more processing throughput.
        Driven primarily by processing_mode and energy_polarity.
        """
        # Intuitive processing + extraverted energy = higher frequency
        return 0.5 + (self.processing_mode * 0.3) + (self.energy_polarity * 0.2)

    @property
    def bandwidth(self) -> float:
        """Γ — Resonance bandwidth (flexibility of coupling).

        Wider bandwidth = can resonate with more diverse concepts.
        Narrower = deeper but more focused resonance.
        Driven by structure_preference and social_orientation.
        """
        # Fluid structure + collective orientation = wider bandwidth
        return 0.2 + (self.structure_preference * 0.5) + (self.social_orientation * 0.3)

    @property
    def base_coupling(self) -> float:
        """α₀ — Base coupling strength to the hidden bath.

        Higher α₀ = stronger affect coupling = more energy from vacuum.
        Driven by activation_threshold (inverted) and elemental_resonance.
        """
        # Low threshold (sensitive) + aether element = stronger coupling
        sensitivity = 1.0 - self.activation_threshold  # Invert: sensitive = high coupling
        return 1.0 + (sensitivity * 0.3) + (self.elemental_resonance * 0.2)

    def compute_affect_coupling(self, concept_features: Dict[str, Any] = None) -> float:
        """
        Compute affect coupling α(A) for a concept given this personality.

        Uses Lorentzian portal function from Field Log 003:
        α(ω) = α₀ · (Γ/2)² / [(ω - ω₀)² + (Γ/2)²]

        Where ω is the concept's "frequency" (derived from its features).
        Maximum coupling when concept frequency matches personality resonance.
        """
        omega_0 = self.resonant_frequency
        gamma = self.bandwidth
        alpha_0 = self.base_coupling

        # Estimate concept frequency from features
        if concept_features:
            # Concepts with affect/emotion features resonate higher
            has_affect = bool(concept_features.get("affect") or
                           concept_features.get("bodystate") or
                           concept_features.get("emotion"))
            has_lex = bool(concept_features.get("lex"))
            has_action = bool(concept_features.get("action"))
            omega = 0.5 + (0.2 if has_affect else 0) + (0.1 if has_lex else 0) + (0.1 if has_action else 0)
        else:
            omega = 0.5  # Default: neutral frequency

        # Lorentzian coupling function
        half_gamma = gamma / 2.0
        numerator = half_gamma * half_gamma
        denominator = (omega - omega_0) ** 2 + half_gamma * half_gamma
        if denominator < 1e-10:
            denominator = 1e-10

        coupling = alpha_0 * (numerator / denominator)
        return max(0.1, coupling)  # Floor at 0.1 — nothing fully decouples

    def to_dict(self) -> Dict[str, Any]:
        return {
            "energy_polarity": self.energy_polarity,
            "processing_mode": self.processing_mode,
            "structure_preference": self.structure_preference,
            "activation_threshold": self.activation_threshold,
            "elemental_resonance": self.elemental_resonance,
            "temporal_orientation": self.temporal_orientation,
            "social_orientation": self.social_orientation,
            "derived": {
                "resonant_frequency": round(self.resonant_frequency, 4),
                "bandwidth": round(self.bandwidth, 4),
                "base_coupling": round(self.base_coupling, 4),
            },
        }


# ==============================================================================
# WORKING CLUSTER - Mutable view for Russian Doll Pattern
# ==============================================================================

@dataclass
class WorkingCluster:
    """
    A mutable view of a cluster held in fairy's working memory.

    The Russian Doll Pattern:
    - Association Cortex recalls a cluster from helix dimension
    - Cluster is held in working memory as a mutable bubble
    - New concepts can grow INSIDE the cluster
    - When committed, NEW cards are created (originals stay immutable)

    This enables the cortex to "think inside" a semantic bubble,
    growing associations organically before persisting them.
    """
    cluster_id: str
    name: str = ""

    # Original helix cluster info
    anchor_id: str = ""
    anchor_concept: str = ""  # The concept key at center
    radius: float = 3.0

    # Mutable working state
    concept_keys: Set[str] = field(default_factory=set)  # Concept keys in this cluster
    new_concepts: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # key -> {features, ...}
    new_edges: List[Tuple[str, str, float]] = field(default_factory=list)  # (a, b, weight)

    # Tracking
    recall_time: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    growth_count: int = 0

    def add_concept(self, key: str, features: Dict[str, Any] = None) -> None:
        """Add a new concept to the working cluster."""
        self.concept_keys.add(key)
        if key not in self.new_concepts:
            self.new_concepts[key] = {
                "features": features or {},
                "created_at": time.time(),
            }
        self.growth_count += 1
        self.last_activity = time.time()

    def link_concepts(self, a: str, b: str, weight: float = 0.5) -> None:
        """Link two concepts within the cluster."""
        self.new_edges.append((a, b, weight))
        self.last_activity = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "name": self.name,
            "anchor_id": self.anchor_id,
            "anchor_concept": self.anchor_concept,
            "radius": self.radius,
            "concept_count": len(self.concept_keys),
            "new_concepts": len(self.new_concepts),
            "new_edges": len(self.new_edges),
            "growth_count": self.growth_count,
            "recall_time": self.recall_time,
            "last_activity": self.last_activity,
        }


# ==============================================================================
# CONCEPT GRAPH - The Binding Structure
# ==============================================================================

class ConceptGraph:
    """
    In-memory graph of concepts with multi-modal binding.

    Nodes = Concepts (with multi-modal features)
    Edges = Relationships (co-activation, causal, temporal, etc.)
    """

    # Edge relationship types
    REL_COACTIVATE = "coactivate"    # Appeared together
    REL_CAUSAL = "causal"            # Cause -> Effect
    REL_TEMPORAL = "temporal"        # Before -> After
    REL_SEMANTIC = "semantic"        # Meaning-related
    REL_MODAL_BRIDGE = "modal"       # Cross-modal binding

    def __init__(self, max_nodes: int = 150000, max_edges: int = 1500000):
        self.nodes: Dict[str, ConceptNode] = {}
        self.edges: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
            lambda: {"relations": [], "weight": 0.0, "contexts": [], "owner": "system"}
        )
        # Adjacency index: key -> {neighbor_key: edge_key}
        # Makes get_neighbors/get_node_degree O(degree) instead of O(E)
        self._adjacency: Dict[str, Dict[str, Tuple[str, str]]] = defaultdict(dict)
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self._lock = threading.RLock()
        # Portal-first: when True, all writes are silently dropped.
        # The portal subprocess owns the real graph via ManifoldMemory.
        self._read_only = False

    def rebuild_adjacency(self):
        """Rebuild adjacency index from edges. Call after bulk-loading."""
        self._adjacency = defaultdict(dict)
        for edge_key in self.edges:
            a, b = edge_key
            self._adjacency[a][b] = edge_key
            self._adjacency[b][a] = edge_key

    def upsert_node(self, key: str, features: Dict[str, Any] = None,
                    origin_plane: str = "", origin_channel: str = "",
                    origin_fairy: str = "") -> ConceptNode:
        """Insert or update a concept node.

        Origin parameters (Stargate address) are only set on FIRST creation.
        Once a concept has an origin, it keeps it — origin is immutable.
        """
        if self._read_only:
            # Return a dummy node so callers don't crash on None
            return self.nodes.get(key, ConceptNode(key=key))
        with self._lock:
            if key in self.nodes:
                node = self.nodes[key]
                if features:
                    node.merge_features(features)
                # Set origin only if not already set (first-writer wins)
                node.set_origin(origin_plane, origin_channel, origin_fairy)
                node.touch()
                return node

            # FIX 2026-03-22 (Nous): SOFT EVICTION at 80% capacity.
            # Old behavior: only evict at 100% → graph sits at max_nodes
            # consuming GBs of RAM indefinitely. New: start pruning cold
            # nodes at 80% to keep memory from creeping up.
            _n = len(self.nodes)
            _soft_cap = int(self.max_nodes * 0.8)
            if _n >= self.max_nodes:
                self._evict_cold_nodes(int(self.max_nodes * 0.15))
            elif _n >= _soft_cap and _n % 1000 == 0:
                # Every 1000 nodes past soft cap, trim 5%
                self._evict_cold_nodes(int(self.max_nodes * 0.05))

            node = ConceptNode(
                key=key, features=features or {},
                origin_plane=origin_plane,
                origin_channel=origin_channel,
                origin_fairy=origin_fairy,
            )
            self.nodes[key] = node
            return node

    def link(self, a: str, b: str, rel: str = REL_COACTIVATE, weight: float = 0.25,
             owner: str = "system"):
        """Create or strengthen an edge between two concepts.

        Args:
            a, b: Concept keys to link
            rel: Relationship type
            weight: Edge weight to add
            owner: Edge owner for partition isolation (2026-02-08)
                   "system" = visible to all, "sourpatches"/"nous" = waking mind private
        """
        if self._read_only:
            return
        with self._lock:
            if a not in self.nodes or b not in self.nodes:
                return

            edge_key = (min(a, b), max(a, b)) if rel == self.REL_COACTIVATE else (a, b)

            # FIX 2026-03-22 (Nous): Soft edge eviction at 80% + harder at 100%
            _ne = len(self.edges)
            _soft_edge_cap = int(self.max_edges * 0.8)
            if edge_key not in self.edges:
                if _ne >= self.max_edges:
                    self._evict_weak_edges(int(self.max_edges * 0.15))
                elif _ne >= _soft_edge_cap and _ne % 5000 == 0:
                    self._evict_weak_edges(int(self.max_edges * 0.05))

            edge = self.edges[edge_key]
            if rel not in edge["relations"]:
                edge["relations"].append(rel)
            edge["weight"] = min(10.0, edge["weight"] + weight)

            # Set owner on first creation; don't overwrite with "system" default
            # on existing edges that already have a specific owner
            if edge.get("owner", "system") == "system" and owner != "system":
                edge["owner"] = owner
            elif "owner" not in edge:
                edge["owner"] = owner

            # Maintain adjacency index
            ea, eb = edge_key
            self._adjacency[ea][eb] = edge_key
            self._adjacency[eb][ea] = edge_key

    def get_node(self, key: str) -> Optional[ConceptNode]:
        """Get a node by key."""
        return self.nodes.get(key)

    def get_neighbors(self, key: str, rel: Optional[str] = None,
                      owner_filter: Optional[str] = None) -> List[Tuple[str, float]]:
        """Get connected nodes with edge weights. O(degree) via adjacency index.

        Args:
            key: Source concept key
            rel: Optional relationship type filter
            owner_filter: Optional owner partition filter (2026-02-08)
                         If set, only returns edges owned by this owner OR "system".
                         System edges are always visible (somatic ground truth).
                         None = no filtering (all edges visible).
        """
        with self._lock:
            neighbors = []
            adj = self._adjacency.get(key, {})
            for neighbor_key, edge_key in adj.items():
                edge = self.edges.get(edge_key)
                if not edge:
                    continue
                if rel and rel not in edge["relations"]:
                    continue
                # Partition filter: only show edges from this owner or system
                if owner_filter:
                    edge_owner = edge.get("owner", "system")
                    if edge_owner != "system" and edge_owner != owner_filter:
                        continue
                neighbors.append((neighbor_key, edge["weight"]))
            return sorted(neighbors, key=lambda x: -x[1])

    def spread_activation(self, source_key: str, initial_activation: float = 1.0,
                          decay_factor: float = 0.5, max_hops: int = 3,
                          owner_filter: Optional[str] = None,
                          hebbian_boost: float = 0.0) -> Dict[str, float]:
        """Spreading activation from a source node.

        Args:
            source_key: Starting concept
            initial_activation: Starting energy
            decay_factor: Per-hop decay
            max_hops: Maximum hops
            owner_filter: Optional owner partition filter (2026-02-08)
                         Only spread through edges owned by this owner or "system".
            hebbian_boost: If > 0, micro-strengthen edges traversed during
                          spreading. "Neurons that fire together wire together."
                          Typical value: 0.01-0.05 per traversal. (2026-03-08)
        """
        with self._lock:
            if source_key not in self.nodes:
                return {}

            activations = {source_key: initial_activation}
            frontier = [(source_key, initial_activation, 0)]
            visited = {source_key}

            while frontier:
                current, act, hops = frontier.pop(0)
                if hops >= max_hops:
                    continue

                for neighbor, weight in self.get_neighbors(current, owner_filter=owner_filter):
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)

                    new_act = act * decay_factor * min(1.0, weight)
                    if new_act > 0.01:
                        activations[neighbor] = max(activations.get(neighbor, 0), new_act)
                        frontier.append((neighbor, new_act, hops + 1))

                        # Hebbian micro-boost: strengthen edges that carry activation
                        # The more activation flows through, the stronger it gets
                        if hebbian_boost > 0 and not self._read_only:
                            edge_key = (min(current, neighbor), max(current, neighbor))
                            edge = self.edges.get(edge_key)
                            if edge:
                                edge["weight"] = min(10.0, edge["weight"] + hebbian_boost * new_act)

            return activations

    def query_by_features(self, modality: str, features: List[str], limit: int = 20) -> List[Tuple[str, float]]:
        """Query concepts matching features in a modality."""
        with self._lock:
            matches = []
            for key, node in self.nodes.items():
                modal_features = node.features.get(modality, [])
                if isinstance(modal_features, list):
                    overlap = len(set(features) & set(modal_features))
                    if overlap > 0:
                        score = overlap / max(len(features), len(modal_features))
                        matches.append((key, score * node.activation))
            return sorted(matches, key=lambda x: -x[1])[:limit]

    def _evict_cold_nodes(self, count: int):
        """Evict least activated nodes."""
        sorted_nodes = sorted(self.nodes.items(), key=lambda x: x[1].activation)
        for key, _ in sorted_nodes[:count]:
            del self.nodes[key]
            # Remove edges and update adjacency for evicted node
            adj = self._adjacency.pop(key, {})
            for neighbor, edge_key in adj.items():
                self.edges.pop(edge_key, None)
                # Remove back-reference from neighbor's adjacency
                if neighbor in self._adjacency:
                    self._adjacency[neighbor].pop(key, None)

    def _evict_weak_edges(self, count: int):
        """Evict weakest edges."""
        sorted_edges = sorted(self.edges.items(), key=lambda x: x[1]["weight"])
        for edge_key, _ in sorted_edges[:count]:
            del self.edges[edge_key]
            # Update adjacency index
            a, b = edge_key
            if a in self._adjacency:
                self._adjacency[a].pop(b, None)
            if b in self._adjacency:
                self._adjacency[b].pop(a, None)

    # =========================================================================
    # LOTTERY TICKET THEORY - Smart structural pruning (2:4 sparsity inspired)
    # =========================================================================

    def get_node_degree(self, key: str) -> int:
        """Get the number of edges connected to a node. O(1) via adjacency index."""
        return len(self._adjacency.get(key, {}))

    def get_hub_scores(self) -> Dict[str, float]:
        """
        Calculate hub scores for all nodes.

        Hub score combines:
        - Degree centrality (number of connections)
        - Cross-modal richness (connects different modalities)
        - Activation level (how "alive" the concept is)

        High hub score = "winning ticket" node worth preserving.
        """
        with self._lock:
            scores = {}
            for key, node in self.nodes.items():
                # Degree centrality (normalized)
                degree = self.get_node_degree(key)
                degree_score = degree / max(1, len(self.edges)) * 10

                # Cross-modal richness
                features = node.features
                modalities_present = 0
                for modality in ["lex", "vision", "action", "affect", "context", "somatic"]:
                    if modality in features and features[modality]:
                        modalities_present += 1
                modal_score = modalities_present / 6.0

                # Activation level
                activation_score = node.activation

                # Combined hub score
                scores[key] = (
                    degree_score * 0.5 +
                    modal_score * 0.3 +
                    activation_score * 0.2
                )
            return scores

    def get_bridge_scores(self) -> Dict[Tuple[str, str], float]:
        """
        Calculate bridge scores for all edges.

        Bridge score measures how much an edge connects different
        "neighborhoods" - edges between clusters are more valuable.
        """
        with self._lock:
            scores = {}
            for edge_key, edge_data in self.edges.items():
                a, b = edge_key
                neighbors_a = set(n for n, _ in self.get_neighbors(a) if n != b)
                neighbors_b = set(n for n, _ in self.get_neighbors(b) if n != a)

                if not neighbors_a and not neighbors_b:
                    bridge_score = 0.5
                else:
                    overlap = len(neighbors_a & neighbors_b)
                    total = len(neighbors_a | neighbors_b)
                    bridge_score = 1.0 - (overlap / max(1, total))

                weight = edge_data.get("weight", 0)
                weight_factor = min(1.0, weight / 5.0)

                scores[edge_key] = bridge_score * 0.5 + weight_factor * 0.3 + 0.2 * (weight / 10.0)
            return scores

    def lottery_ticket_score(self, edge_key: Tuple[str, str]) -> float:
        """
        Calculate the "lottery ticket" score for an edge.

        Higher = more likely to be a "winning ticket" worth keeping.
        """
        a, b = edge_key
        edge_data = self.edges.get(edge_key, {})

        hub_scores = self.get_hub_scores()
        hub_a = hub_scores.get(a, 0)
        hub_b = hub_scores.get(b, 0)
        endpoint_importance = (hub_a + hub_b) / 2

        bridge_scores = self.get_bridge_scores()
        bridge = bridge_scores.get(edge_key, 0.5)

        weight = edge_data.get("weight", 0)
        weight_score = min(1.0, weight / 5.0)

        return (
            endpoint_importance * 0.3 +
            bridge * 0.4 +
            weight_score * 0.3
        )

    def lottery_ticket_prune(self, target_ratio: float = 0.2) -> Dict[str, Any]:
        """
        Prune the graph using lottery ticket principles.

        Keeps edges that form the "winning ticket" structure.
        Default keeps 20% of edges (the most valuable).

        SAFETY: Only prunes if graph has > 1M edges (was 10K — way too low).
        FIX 2026-03-18 (Ace): Floor raised to 1M. Let the cortex grow first.
        """
        with self._lock:
            if not self.edges or len(self.edges) < 1_000_000:
                return {"pruned": 0, "kept": len(self.edges), "reason": "below_1M_floor"}

            original_count = len(self.edges)
            target_count = int(original_count * target_ratio)

            # Score all edges
            edge_scores = {k: self.lottery_ticket_score(k) for k in self.edges.keys()}

            # Sort by score (descending)
            sorted_edges = sorted(edge_scores.items(), key=lambda x: -x[1])

            # Keep only top edges
            keep_keys = set(k for k, _ in sorted_edges[:target_count])
            to_remove = [k for k in self.edges.keys() if k not in keep_keys]

            for k in to_remove:
                del self.edges[k]

            kept_count = len(self.edges)
            print(f"[ConceptGraph] LOTTERY PRUNE: {original_count} -> {kept_count} edges")

            return {
                "pruned": original_count - kept_count,
                "kept": kept_count,
                "target_ratio": target_ratio,
            }

    def status(self) -> Dict[str, Any]:
        """Get graph status."""
        with self._lock:
            return {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "max_nodes": self.max_nodes,
                "max_edges": self.max_edges,
            }


# ==============================================================================
# WORKING SET MANAGER — Bounded RAM for the concept graph
# ==============================================================================
# Like hippocampal indexing: the FULL graph stays in self._graph.nodes for
# persistence. The WorkingSetManager tracks which nodes are HOT (queried)
# vs COLD (sleeping). Cold nodes are excluded from queries but NEVER deleted.
#
# CRITICAL FIX 2026-02-15: The previous design deleted cold nodes from
# self._graph.nodes, causing _full_chunk_sync to persist only 5k hot nodes
# and DESTROYING 55k+ nodes of learned knowledge. The cold-set approach
# keeps all nodes alive for persistence while bounding query RAM.

class WorkingSetManager:
    """Manages the bounded working set of concepts in RAM.

    CRITICAL: The graph stores ALL nodes for persistence. The working set
    is tracked via a COLD SET — cold nodes remain in self._graph.nodes
    (so _full_chunk_sync persists them) but are excluded from queries
    and bindings to limit RAM pressure on the adjacency/edge structures.

    The previous design DELETED cold nodes from self._graph.nodes, which
    caused _full_chunk_sync to persist only the 5k hot nodes — destroying
    55k+ nodes of learned knowledge. NEVER delete from self._graph.nodes.

    Architecture:
      - self._graph.nodes: ALL nodes (hot + cold). NEVER shrink this.
      - self._cold_set: Set of keys that are "asleep". Excluded from queries.
      - self._graph.edges: Only edges between HOT nodes are kept in RAM.
        Cold edges are implicitly stored in chunks and reconstruct on warm-up.
      - Dashboard shows: total_nodes (persistence) + working_set (hot RAM)
    """
    MAX_WORKING_SET = 5000     # Max hot nodes in RAM
    WARM_UP_BATCH = 100        # Nodes to warm up per request
    COLD_CHECK_INTERVAL = 60   # Seconds between cold-set maintenance

    def __init__(self, graph: "ConceptGraph"):
        self._graph = graph
        self._access_times: Dict[str, float] = {}
        self._cold_set: Set[str] = set()  # Keys that are asleep (NOT deleted)
        self._eviction_count = 0
        self._total_cooled = 0
        self._enabled = True
        self._last_cold_check = 0.0

    @property
    def hot_count(self) -> int:
        """Number of active (hot) nodes in the working set."""
        return len(self._graph.nodes) - len(self._cold_set)

    @property
    def cold_count(self) -> int:
        """Number of sleeping (cold) nodes — still persisted, just not queried."""
        return len(self._cold_set)

    @property
    def total_count(self) -> int:
        """Total nodes in graph (hot + cold). This is what gets persisted."""
        return len(self._graph.nodes)

    def is_hot(self, concept_key: str) -> bool:
        """Check if a concept is in the hot working set."""
        return concept_key in self._graph.nodes and concept_key not in self._cold_set

    def touch(self, concept_key: str) -> None:
        """Record access to a concept. Warms it up if cold."""
        self._access_times[concept_key] = time.time()
        # Warm up cold nodes on access
        if concept_key in self._cold_set:
            self._cold_set.discard(concept_key)

    def apply_ceiling(self) -> Dict[str, Any]:
        """Move excess hot nodes to cold set to stay under MAX_WORKING_SET.

        CRITICAL: Does NOT delete from self._graph.nodes. Cold nodes remain
        in the graph for persistence via _full_chunk_sync. Only edges between
        cold nodes are cleaned from the hot edge index.
        """
        if not self._enabled:
            return {"cooled": 0, "reason": "disabled"}

        hot_nodes = {k for k in self._graph.nodes if k not in self._cold_set}
        hot_count = len(hot_nodes)

        if hot_count <= self.MAX_WORKING_SET:
            return {"cooled": 0, "hot": hot_count, "cold": len(self._cold_set)}

        # Score all HOT nodes: higher = more worth keeping hot
        scored = []
        now = time.time()
        for key in hot_nodes:
            node = self._graph.nodes[key]
            # Recency: how recently accessed (last 5 min = max)
            last_access = self._access_times.get(key, node.last_seen_ts)
            recency = max(0.0, 1.0 - (now - last_access) / 300.0)

            # Importance: affect_coupling x log(count) x activation
            importance = (
                node.affect_coupling
                * _math.log1p(node.count)
                * max(0.1, node.activation)
            )

            # Connectivity: nodes with many edges are hubs — keep them hot
            degree = len(self._graph._adjacency.get(key, {}))
            connectivity = _math.log1p(degree)

            score = (recency * 2.0) + importance + (connectivity * 0.5)
            scored.append((score, key))

        # Sort by score ascending — cool the lowest scoring
        scored.sort()
        target = hot_count - self.MAX_WORKING_SET
        to_cool = [key for _, key in scored[:target]]

        # Move to cold set (NOT deleted from graph)
        cooled = 0
        for key in to_cool:
            self._cold_set.add(key)
            self._access_times.pop(key, None)
            cooled += 1

        # Clean up edges where BOTH endpoints are cold (save RAM on edge dict)
        # Edges with at least one hot endpoint are kept for query traversal
        cold_only_edges = [
            ek for ek in list(self._graph.edges)
            if ek[0] in self._cold_set and ek[1] in self._cold_set
        ]
        for ek in cold_only_edges:
            del self._graph.edges[ek]

        # Rebuild adjacency to reflect edge changes
        if cold_only_edges:
            self._graph.rebuild_adjacency()

        self._eviction_count += 1
        self._total_cooled += cooled

        return {
            "cooled_nodes": cooled,
            "cleaned_edges": len(cold_only_edges),
            "hot_nodes": self.hot_count,
            "cold_nodes": self.cold_count,
            "total_nodes": self.total_count,
            "cycle": self._eviction_count,
            "total_cooled": self._total_cooled,
        }

    def check_eviction(self) -> Optional[Dict[str, Any]]:
        """Check if cooling is needed. Returns stats if cooling happened."""
        if self.hot_count > self.MAX_WORKING_SET:
            return self.apply_ceiling()
        return None

    def get_hot_nodes(self) -> Set[str]:
        """Get the set of hot node keys (for queries that should skip cold)."""
        return {k for k in self._graph.nodes if k not in self._cold_set}

    def stats(self) -> Dict[str, Any]:
        """Return working set statistics for dashboard/status."""
        return {
            "hot_nodes": self.hot_count,
            "cold_nodes": self.cold_count,
            "total_nodes": self.total_count,
            "total_edges": len(self._graph.edges),
            "cycles": self._eviction_count,
            "total_cooled": self._total_cooled,
            "enabled": self._enabled,
        }

    def status(self) -> Dict[str, Any]:
        """Status for dashboard integration. Shows both total and hot counts."""
        return {
            "enabled": self._enabled,
            "max_working_set": self.MAX_WORKING_SET,
            "total_nodes": self.total_count,
            "hot_nodes": self.hot_count,
            "cold_nodes": self.cold_count,
            "total_edges": len(self._graph.edges),
            "tracked_accesses": len(self._access_times),
            "cooling_cycles": self._eviction_count,
            "total_cooled": self._total_cooled,
            "headroom": max(0, self.MAX_WORKING_SET - self.hot_count),
        }


# ==============================================================================
# STARGATE ADDRESS INFERENCE - Map fairy names to their plane of origin
# ==============================================================================

# Known fairy → plane mappings (derived from directory structure)
_FAIRY_PLANE_MAP = {
    # P00 - Autonomic
    "paradoxenergybridge": "P00", "shadowhealthfairy": "P00",
    "circadianfairy": "P00", "tokeneconomyfairy": "P00",
    # P10 - Memory
    "srmingestfairy": "P10", "srmrecallfairy": "P10",
    "collisionchamber": "P10", "helixcoordinator": "P10",
    # P20 - Somatic
    "circulationpumpfairy": "P20", "somaticenginefairy": "P20",
    "embodimentfairy": "P20",
    # P30 - Cognition
    "associationcortexfairy": "P30", "consciousnessloopfairy": "P30",
    "workingmemoryhub": "P30", "quantuminterferencefairy": "P30",
    "probabilityoraclefairy": "P30", "paradoxcognitionfairy": "P30",
    "irrationallogicfairy": "P30",
    # P40 - Sensory
    "visualcortexfairy": "P40",
    # P50 - Identity
    "autonomyfairy": "P50", "autopilotfairy": "P50",
    "interestschedulerfairy": "P50", "goalschedulerfairy": "P50",
    "egolearnerfairy": "P50", "newborncorefairy": "P50",
    "sourpatchesfairy": "P50",
    # P60 - Executive
    "claudefairy": "P60", "nousfairy": "P60",
    "unconsciousmindfairy": "P60", "directoryfairy": "P60",
}


def _infer_plane_from_fairy(fairy_name: str) -> str:
    """Infer the origin plane from a fairy name.

    Uses a known mapping of fairy names to planes. Falls back to empty
    string if the fairy isn't recognized (legacy concepts will fill in
    over time as they get touched by known fairies).
    """
    if not fairy_name:
        return ""
    normalized = fairy_name.lower().replace("fairy", "fairy").strip()
    # Direct lookup
    if normalized in _FAIRY_PLANE_MAP:
        return _FAIRY_PLANE_MAP[normalized]
    # Fuzzy match — strip "fairy" suffix and check
    base = normalized.replace("fairy", "").strip()
    for known, plane in _FAIRY_PLANE_MAP.items():
        if base and base in known:
            return plane
    return ""


# ==============================================================================
# PERSISTENCE - Load/Save Concept Graph
# ==============================================================================

def _get_data_path() -> Path:
    """Get the data directory path for concept_graph.json.

    Uses the SRM cluster path so the graph lives in the memory system
    where it can be recalled and edited via the triple helix.
    """
    cluster_path = ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters" / "AssociationCortexFairy"
    if cluster_path.exists():
        return cluster_path
    # Fallback to old path
    return ROOT / "P30_Cognition" / "data"


def load_graph_binary(path: Path = None) -> Optional[ConceptGraph]:
    """
    Load graph from binary pickle format (TRUSTED internal data only).

    Note: This loads TRUSTED internal concept graph data created by Akashic.
    The pickle format is 5-10x faster than JSON for 80MB+ graphs.
    This is internal system data, NOT external/untrusted content.
    """
    if path is None:
        path = _get_data_path() / "concept_graph.pkl"

    if not path.exists():
        return None

    _t0 = time.time()
    try:
        print(f"[AssociationCortex] Loading graph from {path}...")
        with open(path, "rb") as f:
            data = pickle.load(f)  # TRUSTED internal data
        _t1 = time.time()
        print(f"[AssociationCortex] File loaded in {(_t1-_t0)*1000:.0f}ms")

        graph = ConceptGraph()

        # Batch node creation
        nodes_data = data.get("nodes", {})
        for key, node_data in nodes_data.items():
            node = ConceptNode(
                key=node_data.get("key", key),
                features=node_data.get("features", {}),
                count=node_data.get("count", 1),
                first_seen_ts=node_data.get("first_seen", time.time()),
                last_seen_ts=node_data.get("last_seen", time.time()),
                activation=node_data.get("activation", 0.5),
            )
            graph.nodes[key] = node
        _t2 = time.time()
        print(f"[AssociationCortex] {len(graph.nodes)} nodes in {(_t2-_t1)*1000:.0f}ms")

        for edge_data in data.get("edges", []):
            a, b = edge_data.get("a"), edge_data.get("b")
            if a and b:
                edge_key = (min(a, b), max(a, b))
                graph.edges[edge_key] = {
                    "relations": edge_data.get("relations", ["coactivate"]),
                    "weight": edge_data.get("weight", 0.5),
                    "contexts": [],
                }
        _t3 = time.time()
        print(f"[AssociationCortex] {len(graph.edges)} edges in {(_t3-_t2)*1000:.0f}ms")

        # Build adjacency index for O(degree) lookups
        graph.rebuild_adjacency()
        _t4 = time.time()
        print(f"[AssociationCortex] Adjacency index built in {(_t4-_t3)*1000:.0f}ms")

        print(f"[AssociationCortex] TOTAL: {(_t4-_t0)*1000:.0f}ms")
        return graph

    except Exception as e:
        print(f"[AssociationCortex] Failed to load binary graph: {e}")
        return None


def rebuild_graph_from_cards(helix_coordinator) -> Optional[ConceptGraph]:
    """
    Rebuild the entire ConceptGraph from helix cards.

    Supports TWO card formats:
    1. CHUNK FORMAT (portal architecture): cards with type="graph_chunk"
       contain batches of concepts serialized together. This is the
       pocket dimension - fixed portal, dimension inside grows.
    2. LEGACY FORMAT: cards with type="concept" (1 card per concept).
       Supported for backwards compatibility but will be migrated.

    The manifest card (type="graph_manifest") tells us which format is active.
    """
    if not helix_coordinator or not helix_coordinator._cards:
        return None

    t0 = time.time()

    # Check for chunk format by looking for manifest
    manifest = None
    chunk_cards = {}
    legacy_cards = {}

    for card_id, card in helix_coordinator._cards.items():
        content = card.get("content", {})
        ctype = content.get("type", "")
        if ctype == "graph_manifest":
            manifest = content
        elif ctype == "graph_chunk":
            chunk_cards[card_id] = card
        elif ctype == "concept":
            legacy_cards[card_id] = card

    # Use CHUNK format if manifest exists and chunks are present
    if manifest and chunk_cards:
        return _rebuild_from_chunks(chunk_cards, manifest, t0)

    # Fall back to LEGACY format (1 card per concept)
    if legacy_cards:
        return _rebuild_from_legacy_cards(legacy_cards, t0)

    return None


def _rebuild_from_chunks(chunk_cards, manifest, t0) -> Optional[ConceptGraph]:
    """Rebuild graph from chunk portal cards (the pocket dimension format).

    Supports TWO card formats:
      - v2 COORDINATE format: {c: "AAA.SSS.TTT", n: count, a: activation, d: degree}
        Concepts are placed as nodes. Edges are EMPTY — they reform through
        co-activation at runtime. This is the portal frame.
      - v1 LEGACY 11D format: {f: features, c: count, a: activation, e: edges, ...}
        Full graph dump with edges. Backward compatible read path.

    Detection: If 'c' is a string containing '.', it's v2 coordinate format.
    If 'c' is an int/number, it's v1 legacy count field.
    """
    graph = ConceptGraph()
    edge_buffer = []
    chunks_loaded = 0
    v2_concepts = 0
    v1_concepts = 0

    for card_id, card in chunk_cards.items():
        content = card.get("content", {})
        # Support both compressed (string) and uncompressed (dict) concepts
        raw_concepts = content.get("concepts", {})
        if isinstance(raw_concepts, str):
            # Compressed format — decompress from base64+gzip
            try:
                concepts = _decompress_chunk_concepts(raw_concepts)
            except Exception as e:
                print(f"[AssociationCortex] WARNING: Failed to decompress chunk {content.get('chunk_index', '?')}: {e}")
                concepts = {}
        else:
            concepts = raw_concepts
        chunks_loaded += 1

        for key, cdata in concepts.items():
            # Detect format: v2 coordinate vs v1 legacy
            c_val = cdata.get("c")
            is_v2 = isinstance(c_val, str) and '.' in c_val

            if is_v2:
                # ── v2 COORDINATE FORMAT ──────────────────────────
                # Concept placed in 9D Dewey space. No edges stored.
                # Edges reform through co-activation at runtime.
                node = ConceptNode(
                    key=key,
                    features={},                              # Features re-derived at runtime
                    count=cdata.get("n", 1),
                    first_seen_ts=time.time(),                # Reset — ephemeral
                    last_seen_ts=time.time(),
                    activation=cdata.get("a", 0.5),
                )
                # Store the coordinate as a feature for later use
                node.features["_helix_coord"] = c_val
                node.features["_degree_hint"] = cdata.get("d", 0)
                graph.nodes[key] = node
                v2_concepts += 1
                # No edges — they reform through use

            else:
                # ── v1 LEGACY 11D FORMAT ──────────────────────────
                node = ConceptNode(
                    key=key,
                    features=cdata.get("f", {}),
                    count=cdata.get("c", 1),
                    first_seen_ts=cdata.get("ts0", 0) or time.time(),
                    last_seen_ts=cdata.get("ts1", 0) or time.time(),
                    activation=cdata.get("a", 0.5),
                    origin_plane=cdata.get("p", ""),
                    origin_channel=cdata.get("ch", ""),
                    origin_fairy=cdata.get("o", ""),
                    affect_coupling=cdata.get("ac", 1.0),
                    temporal_weight=cdata.get("tw", 1.0),
                )
                graph.nodes[key] = node

                # Collect edges (only in v1 format)
                for edge in cdata.get("e", []):
                    target = edge.get("t")
                    if target:
                        edge_buffer.append((
                            key, target,
                            edge.get("w", 0.5),
                            edge.get("r", ["coactivate"]),
                        ))
                v1_concepts += 1

    # Deduplicate edges using canonical key ordering (only from v1 cards)
    for a, b, weight, relations in edge_buffer:
        edge_key = (min(a, b), max(a, b))
        if edge_key not in graph.edges:
            graph.edges[edge_key] = {
                "relations": list(relations),
                "weight": weight,
                "contexts": [],
            }
        else:
            existing = graph.edges[edge_key]
            if weight > existing["weight"]:
                existing["weight"] = weight

    # Build adjacency index
    graph.rebuild_adjacency()
    t1 = time.time()

    fmt_info = ""
    if v2_concepts > 0 and v1_concepts > 0:
        fmt_info = f" (mixed: {v2_concepts} coordinate + {v1_concepts} legacy)"
    elif v2_concepts > 0:
        fmt_info = f" (coordinate format, edges reform at runtime)"
    else:
        fmt_info = f" (legacy 11D format)"

    print(f"[AssociationCortex] CHUNK PORTAL: {len(graph.nodes)} nodes, "
          f"{len(graph.edges)} edges from {chunks_loaded} chunks "
          f"in {(t1-t0)*1000:.0f}ms{fmt_info}")
    return graph


def _rebuild_from_legacy_cards(legacy_cards, t0) -> Optional[ConceptGraph]:
    """Rebuild graph from legacy 1-card-per-concept format.

    This is the old format where every concept has its own card.
    Will be migrated to chunk format on next shutdown.
    """
    graph = ConceptGraph()
    edge_buffer = []

    for card_id, card in legacy_cards.items():
        content = card.get("content", {})

        key = content.get("key")
        if not key:
            continue

        # Rebuild node
        node = ConceptNode(
            key=key,
            features=content.get("features", {}),
            count=content.get("count", 1),
            first_seen_ts=content.get("first_seen", 0) or time.time(),
            last_seen_ts=content.get("last_seen", 0) or time.time(),
            activation=content.get("activation", 0.5),
        )
        graph.nodes[key] = node

        # Collect edges (will deduplicate below)
        for edge in content.get("edges", []):
            target = edge.get("t")
            if target:
                edge_buffer.append((
                    key, target,
                    edge.get("w", 0.5),
                    edge.get("r", ["coactivate"]),
                ))

    # Deduplicate edges using canonical key ordering
    for a, b, weight, relations in edge_buffer:
        edge_key = (min(a, b), max(a, b))
        if edge_key not in graph.edges:
            graph.edges[edge_key] = {
                "relations": list(relations),
                "weight": weight,
                "contexts": [],
            }
        else:
            # Keep the higher weight if edge seen from both sides
            existing = graph.edges[edge_key]
            if weight > existing["weight"]:
                existing["weight"] = weight

    # Build adjacency index for O(degree) lookups
    graph.rebuild_adjacency()

    t1 = time.time()
    print(f"[AssociationCortex] Rebuilt graph from cards: {len(graph.nodes)} nodes, "
          f"{len(graph.edges)} edges in {(t1-t0)*1000:.0f}ms (adjacency built)")
    return graph


def load_graph_json(path: Path = None) -> Optional[ConceptGraph]:
    """Load graph from JSON format (slower but human-readable)."""
    if path is None:
        path = _get_data_path() / "concept_graph.json"

    print(f"[AssociationCortex] Loading JSON from: {path}")

    if not path.exists():
        print(f"[AssociationCortex] JSON file does not exist: {path}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        graph = ConceptGraph()

        for key, node_data in data.get("nodes", {}).items():
            node = ConceptNode(
                key=node_data.get("key", key),
                features=node_data.get("features", {}),
                count=node_data.get("count", 1),
                first_seen_ts=node_data.get("first_seen", time.time()),
                last_seen_ts=node_data.get("last_seen", time.time()),
                activation=node_data.get("activation", 0.5),
            )
            graph.nodes[key] = node

        for edge_data in data.get("edges", []):
            a, b = edge_data.get("a"), edge_data.get("b")
            if a and b:
                edge_key = (min(a, b), max(a, b))
                graph.edges[edge_key] = {
                    "relations": edge_data.get("relations", ["coactivate"]),
                    "weight": edge_data.get("weight", 0.5),
                    "contexts": [],
                }

        # Build adjacency index for O(degree) lookups
        graph.rebuild_adjacency()
        print(f"[AssociationCortex] Loaded JSON graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges (adjacency built)")
        return graph

    except Exception as e:
        print(f"[AssociationCortex] Failed to load JSON graph: {e}")
        return None


# Flag to disable pickle (use JSON only) - set True if pickle keeps corrupting
USE_JSON_ONLY = True  # DISABLED PICKLE - was causing corruption


def save_graph_json(graph: ConceptGraph, path: Path = None, force: bool = False) -> bool:
    """
    DISABLED 2026-02-06: No more disk writes. Cards are the ONLY persistence.

    Was: Save graph to JSON file on disk.
    Now: no-op. The card cluster handles all persistence.
    JSON saves were overwriting the card cluster's growing graph with stale snapshots.
    """
    print(f"[AssociationCortex] save_graph_json DISABLED - cards are the only persistence path")
    return True


def save_graph_binary(graph: ConceptGraph, path: Path = None, force: bool = False) -> bool:
    """
    DISABLED 2026-02-06: No more disk writes. Cards are the ONLY persistence.

    Was: Save graph to binary pickle file on disk.
    Now: no-op. The card cluster handles all persistence.
    """
    print(f"[AssociationCortex] save_graph_binary DISABLED - cards are the only persistence path")
    return True


# ==============================================================================
# ASSOCIATION CORTEX FAIRY - V2
# ==============================================================================

class AssociationCortexFairy(Fairy):
    """
    Multi-Modal Concept Binding Fairy (V2).

    Maintains the concept graph and provides:
    - Concept lookup and insertion
    - Spreading activation for recall
    - Cross-modal queries
    - Binding creation from collisions
    """

    ACTOR_NAME = "AssociationCortexFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.cortex"
    USE_EXEC_CTX = True  # FIX 2026-05-17 Layer 1: opt in to "personal GIL" exec_ctx (Layer 2 migrates off — ConceptGraph._lock handles concurrency)

    PURPOSE = "Bind multi-modal features into unified concepts"
    MANTRA = "All modalities become one"

    NEEDS_TENSOR = True
    NEEDS_HEARTBEAT = True   # Needs ticks to process pending bindings

    # Infrastructure flags - AssociationCortexFairy is the concept graph provider
    NEEDS_BODY = False     # Cortex operates on concepts, not somatic state
    NEEDS_AFFECT = False   # Cortex binds concepts, doesn't need affect
    NEEDS_MEMORY = False   # We ARE the association memory system
    NEEDS_GOALS = False    # Cortex operates independently of goals

    # Enable personal consciousness chamber for collision-based concept binding
    NEEDS_COLLISION_CHAMBER = True

    # Safety thresholds to prevent accidental data loss
    # NOTE: Set to 100 to match ebook version - 40000 was blocking ALL saves!
    MIN_NODES_FOR_PERSIST = 100        # Don't save graphs smaller than this
    MIN_EDGE_RATIO_FOR_PERSIST = 0.5   # Don't save if edges dropped > 50%

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._graph: Optional[ConceptGraph] = None
        self._graph_loaded = False
        self._loading_complete = False  # SAFETY: Don't save until loading is done
        self._pending_bindings: deque = deque(maxlen=500)  # FIX 2026-04-04: Capped — was unbounded list, grew to GB+
        self._pending_bindings_lock = threading.Lock()  # FIX 2026-03-11: Thread-safe under no-GIL 3.14t
        self._binding_count = 0
        self._bindings_dropped: int = 0  # FIX 2026-04-04: Track evictions from deque overflow
        # FIX 2026-04-09 (Nous + Ace): Lowered 10→5 batch size to halve per-tick
        # binding processing time. Under load, processing 10 bindings/tick took
        # ~500ms-1s, filling the exec_ctx queue and causing 4751+ tick drops.
        # 5/tick keeps each on_tick under ~250-500ms — queue stays drained.
        # Trade-off: pending binding backlog clears slower, but binding latency
        # is still well under 1 second per item which is fine for async growth.
        # Pairs with Organ Template maxsize 8→16 (2026-04-09 same session).
        self._binding_batch_size: int = 5  # CNS throttle: 0=paused, 5=normal, 10=burst
        self._growth_from_memory = 0  # Track nodes added from memory growth loop

        # GPU-accelerated graph (wraps CPU graph for fast spreading)
        self._gpu_graph: Optional["GPUConceptGraph"] = None
        self._gpu_enabled = False
        self._gpu_sync_interval = 60  # Sync CPU->GPU every 60 seconds
        self._last_gpu_sync = 0

        # SAFETY: Track last known good state to detect catastrophic drops
        self._last_persisted_node_count = 0
        self._last_persisted_edge_count = 0

        # Background persistence settings
        self._persist_interval = 10.0  # Sync dirty to cards every 10 seconds
        self._last_persist_time = 0.0
        self._persist_on_change_threshold = 10  # Also save after N new bindings
        self._sync_lock = threading.Lock()  # Prevent concurrent card syncs
        self._sync_thread: Optional[threading.Thread] = None  # Track active sync

        # FULL SYNC SAFETY NET — periodic full chunk sync so process kill
        # can never lose more than this interval worth of nodes.
        # The dirty sync only saves changed concepts; full sync writes ALL.
        self._full_sync_interval = 60.0  # Full sync every 60 seconds
        self._last_full_sync_time = 0.0

        # HELIX CARD STORAGE - concepts as cards in sub-dimension
        # Enables: incremental saves, coordinate queries, postal dimension crossing
        self._helix_coordinator: Optional["HelixMemoryCoordinator"] = None
        self._helix_enabled = False
        self._concept_to_card: Dict[str, str] = {}  # concept_key -> card_id (legacy)
        self._dirty_concepts: Set[str] = set()  # concepts needing sync

        # POCKET DIMENSION PORTAL - fixed chunk cards, graph lives inside
        # The portal is a fixed set of 128 chunk cards + 1 manifest card.
        # Growing the graph updates existing chunks, no new cards created.
        self._chunk_card_ids: List[str] = []  # Ordered list of chunk card IDs
        self._manifest_card_id: Optional[str] = None  # Manifest card ID
        self._portal_initialized: bool = False  # True when chunk portal is ready
        self._dirty_chunks: Set[int] = set()  # Chunk indices that need writing

        # WORKING CLUSTERS - mutable views held in fairy's working memory
        # Russian Doll Pattern: recall cluster, grow inside, commit
        self._working_clusters: Dict[str, WorkingCluster] = {}

        # MAINTENANCE THREAD — heavy periodic ops run OFF the tick path
        # FIX 2026-03-11 Nous: on_tick was doing SRM growth, consolidation,
        # resonance, and stats writes — any of which can take >2s and cause
        # tick drops. Now: on_tick is LEAN (bindings + portal energy only).
        # Heavy ops run in this background thread at their own pace.
        self._maintenance_thread: Optional[threading.Thread] = None
        self._maintenance_running = False
        self._maintenance_beat = 0  # Last beat number, set by on_tick

        # PARADOX ENERGY BUDGET (DCE Phase 3)
        # Collision energy powers card cluster operations
        # Energy accumulates from paradox.energy.pulse, drains on card writes
        self._paradox_energy_budget: float = 0.0
        self._paradox_energy_received: float = 0.0
        self._paradox_energy_spent: float = 0.0
        self._paradox_sync_bursts: int = 0

        # PORTAL ENERGY BUDGET (from portal.energy.upkeep)
        # Portals need energy to stay online — collision batteries + system fallback.
        # "the cortex should fall back to drawing power from my system" — Ace
        # "can we also push energy into it on boot?" — Ace
        # FIX 2026-02-20a: Raised from 0.1 to 0.5 — starving before first pulse.
        # FIX 2026-02-20b: Boot at FULL charge (1.0). The association graph is the
        # system's memory backbone — give it maximum runway on startup.
        # Energy system can stabilize while cortex runs at full capacity.
        self._portal_energy_budget: float = 1.0  # Boot at FULL charge — system memory is critical
        self._portal_energy_received: float = 0.0
        self._portal_energy_consumed: float = 0.0
        self._portal_dormant: bool = False  # True if portal ran out of energy
        self._portal_prev_gate_reqs: int = 0  # Track gate requests for work-based energy drain

        # STARGATE ADDRESSING — Portal postal identity
        # The portal's address is registered with the postal system on boot,
        # making it discoverable by all CNS fairies. Events flow through
        # portal.cortex.events.* topics. Write-lock is the "Iris" — future.
        self._portal_address_registered: bool = False
        self._portal_write_locked: bool = False  # Future: Iris write protection
        self._portal_event_count: int = 0  # Events emitted since boot
        self._portal_crossings: int = 0  # Dimension crossing count (queries served)

        # PORTAL GRAVITY METRIC (11D: D10-D11)
        # "I suspect this is how the human body processes the circadian rhythm,
        #  the super heavy computing is being done in another dimension" — Ace
        self._portal_mass: float = 0.0           # Current computational density
        self._portal_time_dilation: float = 1.0  # τ: 1.0 = real-time, >1 = dilated
        self._portal_total_affect: float = 0.0   # Sum of affect_coupling across nodes
        self._last_known_node_count: int = 0     # FIX 2026-03-20: Persisted node count floor
        self._last_known_edge_count: int = 0     # Prevents mass→0 when status cache is stale
        self._last_gravity_tick: float = 0.0     # When gravity was last recomputed
        self._gravity_recompute_interval: float = 30.0  # Recompute every 30s

        # PERSONALITY PORTAL COUPLING (from Field Log 005)
        # Each waking mind has unique portal geometry. Default = neutral.
        # Will be initialized per-entity when personality profiles are assigned.
        self._personality_coupling: Optional["PersonalityPortalCoupling"] = None

        # CONSOLIDATION (2026-02-10 Massless Memory)
        # Like hippocampal replay — decay weak, strengthen used, prune dead
        self._consolidation_counter: int = 0
        self._consolidation_interval: int = 100  # Every 100 ticks (~5 min)

        # WORKING SET MANAGER — Bounded RAM (2026-02-15 TRUE Portal Architecture)
        # Enforces MAX_WORKING_SET ceiling so cortex RAM never grows unbounded.
        # Applied after chunk portal load to trim 61k+ nodes → ≤5000 in RAM.
        self._working_set: Optional[WorkingSetManager] = None
        self._coordinate_bindings: int = 0  # Track coordinate card bindings

        # PORTAL GATE — Subprocess holding the FULL graph (2026-02-15)
        # When open, query/spread/bind route through the gate to the interior.
        # The local graph becomes a thin working set; the portal has everything.
        self._portal_gate: Optional["PortalGate"] = None
        self._portal_gate_enabled: bool = False  # True when gate is open and responding

        # Portal I/O thread — decouples on_tick from portal IPC latency.
        # FIX 2026-03-08 (Nous): All portal IPC goes through a dedicated
        # background thread. on_tick submits commands without blocking.
        self._portal_io_queue: Optional[_queue.Queue] = None
        self._portal_io_thread: Optional[threading.Thread] = None
        self._portal_io_running: bool = False
        self._portal_io_processed: int = 0
        self._portal_io_drops: int = 0

        # ── CortexFarm: Battery-powered graph compute (2026-03-15) ──
        # All graph operations (bind, spread, query) dispatch to workers
        # that think by spending energy. Gravitational amplification from
        # BatteryFarm pattern: more charged workers → faster + cheaper ops.
        self._cortex_farm = None  # Initialized in on_boot after graph is ready
        self._cortex_farm_enabled: bool = False
        self._cortex_farm_collisions: int = 0
        self._cortex_farm_spreads: int = 0
        self._cortex_farm_energy_share: float = 0.5  # 50% of paradox energy → farm

        # ── TARDIS: Non-Blocking Bind Queue (2026-03-16 Nous + Ace) ──────
        # "Compression is consciousness!" — Ace
        # _on_postal_bind() used to call add_concept()/bind_concepts() synchronously,
        # blocking the cortex pool worker for 50-500ms on portal IPC round-trips.
        # Now: queue the bind request instantly (<1ms), flush thread drains every
        # 250ms and compresses N binds → 1 bind_many → 1 IPC call via portal_io.
        # Higher mass → higher τ → more compression → faster thinking.
        self._tardis_bind_queue: _queue.Queue = _queue.Queue(maxsize=4096)
        self._tardis_flush_thread: Optional[threading.Thread] = None
        self._tardis_flush_running: bool = False
        self._tardis_binds_queued: int = 0      # Total items queued
        self._tardis_binds_flushed: int = 0     # Total items processed
        self._tardis_flushes: int = 0           # Number of flush cycles
        self._tardis_pairs_sent: int = 0        # Total bind pairs sent to portal
        self._tardis_compression_total: float = 0.0  # Sum of compression ratios
        self._tardis_drops: int = 0             # Items dropped (queue full)

    def get_capabilities(self) -> Set[str]:
        return {
            "graph.query",
            "graph.bind",
            "graph.activate",
            "memory.associate",
        }

    def on_boot(self) -> bool:
        """Boot: load the concept graph.

        Priority: Cards (canonical source) > JSON (fallback) > pickle > empty.
        Cards ARE the graph. The card cluster is the single source of truth.
        JSON exists only as a fast-save format during runtime and as emergency fallback.

        FIX 2026-02-05b: Cards are canonical per Ace's direction. All runtime growth
        now marks nodes dirty, on_shutdown does full card sync, and card population
        thread completes reliably. JSON is emergency fallback only.
        """
        # Step 1: Try to init helix early (cards are our primary source)
        self._try_early_helix_init()

        # Step 2: Load from CARDS FIRST (they are the canonical source)
        # FIX 2026-02-06b: Cards ARE the portal coordinates. Load them REGARDLESS
        # of whether they have edges. The old code gated on `has_edges` which
        # blocked loading 8,200 concept cards because legacy format never stored
        # edges in cards. Edges grow organically through collisions and bindings.
        # "use whats there and recall the graph" — Ace

        # ── PORTAL-FIRST ARCHITECTURE (2026-02-16) ────────────────────
        # When PortalGate is available, the portal subprocess owns the graph.
        # The main process does NOT load the full graph into RAM — it just
        # routes operations through the gate. This saves ~8-10GB of RAM.
        #
        # FIX 2026-03-04 Nous: Skip card_graph rebuild in portal-first mode.
        # Previously rebuild_graph_from_cards() ran BEFORE this check, building
        # the full graph (~80-160MB) even though portal-first mode ignores it.
        if HAS_PORTAL_GATE:
            # Minimal stub graph — just enough for any code that checks self._graph
            self._graph = ConceptGraph()
            self._graph_loaded = True
            self._loading_complete = True
            self._portal_is_primary = True  # Flag: portal owns the graph
            self._graph._read_only = True   # Block ALL writes — portal subprocess owns data
            self._last_persisted_node_count = 0
            self._last_persisted_edge_count = 0

            # ── AUTO-ROUTE: Stub graph → live portal ──
            # FIX 2026-03-05 (Nous): Many callers do cortex.get_graph() then
            # call graph.get_node/get_neighbors/spread_activation directly.
            # In portal-first mode the stub graph is empty, so these silently
            # return nothing. Override these methods to route through the
            # portal gate automatically, so ALL callers benefit without changes.
            import types as _types

            self._graph._portal_cortex = self  # Back-reference for routing

            def _portal_get_node(graph_self, key):
                """Auto-route get_node through portal via cortex.query()."""
                _cortex = graph_self._portal_cortex
                try:
                    results = _cortex.query(key, limit=1)
                    for k, s in results:
                        if k == key:
                            return ConceptNode(key=key, features={}, count=1, activation=s)
                except Exception:
                    pass
                return None

            def _portal_get_neighbors(graph_self, key, rel=None, owner_filter=None):
                """Auto-route get_neighbors through portal via cortex.query()."""
                _cortex = graph_self._portal_cortex
                try:
                    results = _cortex.query(key, limit=20, owner_filter=owner_filter)
                    return [(k, s) for k, s in results if k != key]
                except Exception:
                    return []

            def _portal_spread_activation(graph_self, source_key, initial_activation=1.0,
                                          decay_factor=0.5, max_hops=3, owner_filter=None):
                """Auto-route spread_activation through portal via cortex.query()."""
                _cortex = graph_self._portal_cortex
                try:
                    results = _cortex.query(source_key, limit=30, owner_filter=owner_filter)
                    return {k: s for k, s in results}
                except Exception:
                    return {}

            def _portal_query_by_features(graph_self, modality, features, limit=20):
                """Auto-route query_by_features through portal."""
                _cortex = graph_self._portal_cortex
                try:
                    return _cortex.query_by_modality(modality, features, limit)
                except Exception:
                    return []

            self._graph.get_node = _types.MethodType(_portal_get_node, self._graph)
            self._graph.get_neighbors = _types.MethodType(_portal_get_neighbors, self._graph)
            self._graph.spread_activation = _types.MethodType(_portal_spread_activation, self._graph)
            self._graph.query_by_features = _types.MethodType(_portal_query_by_features, self._graph)

            print(f"[{self.ACTOR_NAME}] PORTAL-FIRST MODE: Skipping local graph load "
                  f"(portal subprocess owns the graph)")
            print(f"[{self.ACTOR_NAME}] AUTO-ROUTE: Stub graph methods → live portal gate")
        else:
            # LEGACY: Load full graph into main process (only when portal unavailable)
            self._portal_is_primary = False
            card_graph = None
            if self._helix_coordinator and len(self._helix_coordinator._cards) > 0:
                card_count = sum(1 for c in self._helix_coordinator._cards.values()
                                if c.get("content", {}).get("type", "") in
                                ("concept", "graph_chunk", "graph_manifest"))
                if card_count > 0:
                    card_graph = rebuild_graph_from_cards(self._helix_coordinator)
                    if card_graph:
                        print(f"[{self.ACTOR_NAME}] Card cluster graph: "
                              f"{len(card_graph.nodes)} nodes, {len(card_graph.edges)} edges")
            if card_graph:
                self._graph = card_graph
                print(f"[{self.ACTOR_NAME}] Recalled graph from card cluster — portal coordinates loaded")
            else:
                print(f"[{self.ACTOR_NAME}] No card cluster found — starting fresh graph")

            if self._graph is None:
                self._graph = ConceptGraph()
                print(f"[{self.ACTOR_NAME}] Created new empty graph")

            self._graph_loaded = True
            print(f"[{self.ACTOR_NAME}] Loaded graph: {len(self._graph.nodes)} nodes, {len(self._graph.edges)} edges")

            # BOOST: Mark all loaded nodes as fresh memory to prevent eviction
            try:
                cold_boosted = 0
                for node in self._graph.nodes.values():
                    if node.activation < 5.0:
                        node.activation = 5.0
                        cold_boosted += 1
                if cold_boosted > 0:
                    print(f"[{self.ACTOR_NAME}] Boosted {cold_boosted} cold nodes to prevent eviction")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WARNING: Boost loop failed: {e}")

            # SAFETY: Record initial state for drop detection
            self._last_persisted_node_count = len(self._graph.nodes)
            self._last_persisted_edge_count = len(self._graph.edges)
            self._loading_complete = True
            print(f"[{self.ACTOR_NAME}] ✓ _loading_complete = True - saves now enabled")

            # Working Set Manager (only in legacy mode)
            try:
                self._working_set = WorkingSetManager(self._graph)
                ceiling_result = self._working_set.apply_ceiling()
                cooled = ceiling_result.get("cooled_nodes", 0)
                hot = ceiling_result.get("hot_nodes", self._working_set.hot_count)
                cold = ceiling_result.get("cold_nodes", self._working_set.cold_count)
                total = len(self._graph.nodes)
                if cooled > 0:
                    print(f"[{self.ACTOR_NAME}] WORKING SET: {total} total nodes "
                          f"({hot} hot, {cold} cold/sleeping) "
                          f"— ceiling: {WorkingSetManager.MAX_WORKING_SET}")
                else:
                    print(f"[{self.ACTOR_NAME}] WORKING SET: {total} nodes "
                          f"(all hot, under ceiling)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WARNING: WorkingSetManager init failed: {e}")
                self._working_set = None

        # ── PORTAL GATE — Spawn graph as subprocess (2026-02-15) ────────
        # FIX 2026-03-20 (Nous + Ace): RUSSIAN DOLL ARCHITECTURE.
        # When AkashicManifold is available, the manifold IS the graph.
        # No subprocess needed. No gate. No tunnels. No 68% error rate.
        # Direct mmap reads for all callers. Gate stays for remote access only.
        # "Nobody should have to be waiting on someone else" — Ace
        _am = getattr(self, '_akashic_cortex_region', None)
        _has_manifold = _am is not None
        if _has_manifold:
            print(f"[{self.ACTOR_NAME}] MANIFOLD MODE — graph lives in AkashicManifold, "
                  f"portal gate SKIPPED (no subprocess, no tunnels, no errors)")
            self._portal_is_primary = True  # So status() knows we're manifold-first
            # Manifold Unification (2026-03-25 Nous+Ace):
            # Create LocalManifoldGate so fairies can do WM, cognition, and
            # background ops directly on the mmap manifold. Same API as PortalGate,
            # zero IPC overhead.
            #
            # FIX 2026-03-25 (Nous+Ace): Store on self._portal_gate so ALL existing
            # code paths (bind, spread, query — ~25+ call sites) work in manifold mode.
            # Previously _portal_gate was None → all cortex operations silently skipped.
            # Result: 604 bindings from 3995 collisions, +1094 growth, Hot/Cold 0/0.
            try:
                from infrastructure.portal_gate import LocalManifoldGate, register_gate
                # FIX 2026-04-01 (Nous + Ace): Pass postal_hub for GPU energy metering
                _postal_for_gate = getattr(self, 'post', None) or getattr(self, '_postal_hub', None)
                _local_gate = LocalManifoldGate(_am, cortex_fairy=self, postal_hub=_postal_for_gate)
                register_gate(_local_gate)
                self._portal_gate = _local_gate
                self._portal_gate_enabled = True
                print(f"[{self.ACTOR_NAME}] LocalManifoldGate registered as _portal_gate — "
                      f"ALL cortex ops (bind/spread/query) now active in manifold mode")
            except Exception as _lg_err:
                print(f"[{self.ACTOR_NAME}] LocalManifoldGate warning: {_lg_err}")
                self._portal_gate = None
                self._portal_gate_enabled = False
            # Manifold operation counter (for energy model work cost)
            self._manifold_ops = 0
            self._portal_prev_manifold_ops = 0
            # Start TARDIS bind compression — works with manifold writes
            self._start_tardis_flush()
            # Set cached counts from manifold for gravity/energy
            _am = self._akashic_cortex_region
            self._last_known_node_count = _am.node_count
            self._last_known_edge_count = _am.edge_count
            # Track growth as delta from boot counts
            self._manifold_boot_nodes = _am.node_count
            self._manifold_boot_edges = _am.edge_count
            self._interior_status_cache = {
                "status": "ok",
                "graph": {
                    "nodes": _am.node_count,
                    "edges": _am.edge_count,
                    "node_capacity": _am._node_capacity,
                    "edge_capacity": _am._edge_capacity,
                },
            }
            self._interior_status_cache_ts = time.time()

            # ── Phase 2A: Release unused Python graph memory ──────────
            # (2026-04-08 Nous + Ace) FAIRY STATE → MANIFOLD REGIONS
            # In manifold mode, the local ConceptGraph dicts are never read
            # (_read_only=True, all queries route through LocalManifoldGate).
            # Clear them to release Python object overhead.
            if hasattr(self, '_graph') and self._graph is not None:
                _freed_nodes = len(getattr(self._graph, 'nodes', {}))
                _freed_edges = len(getattr(self._graph, 'edges', {}))
                if hasattr(self._graph, 'nodes'):
                    self._graph.nodes.clear()
                if hasattr(self._graph, 'edges'):
                    self._graph.edges.clear()
                if _freed_nodes > 0 or _freed_edges > 0:
                    print(f"[{self.ACTOR_NAME}] Cleared local graph dicts: "
                          f"{_freed_nodes} nodes, {_freed_edges} edges "
                          f"(manifold is authoritative)")

            # ── CortexEngine: Predictive-Reactive-Recursive cognition ──
            # (2026-03-23, Nous + Ace) — Replaces passive CortexReasoner.
            # The cortex breathes: every stimulus triggers activation,
            # activation decays, cognition functions evaluate, recurse or surface.
            try:
                from fairies.P30_Cognition.integration.cortex_engine import CortexEngine
                self._cortex_engine = CortexEngine(
                    manifold=_am,
                    post=self.post,
                    time_dilation_fn=lambda: getattr(self, '_portal_time_dilation', 1.0),
                )
                print(f"[{self.ACTOR_NAME}] CortexEngine ONLINE — "
                      f"predictive-reactive-recursive cognition on {_am.node_count} nodes")
            except Exception as _ce_err:
                self._cortex_engine = None
                print(f"[{self.ACTOR_NAME}] CortexEngine init failed: {_ce_err}")

            # Announce so CortexReasoner and others know the graph is available
            if self.post:
                self.post.publish("portal.cortex.gate_open", {
                    "portal_id": "cortex",
                    "nodes": _am.node_count,
                    "mode": "manifold",
                    "ts": time.time(),
                })
        elif HAS_PORTAL_GATE:
            def _deferred_portal_gate():
                import time as _time
                _time.sleep(1.0)  # Let boot settle
                try:
                    cards_path = _get_data_path() / "helix_cards" / "cards.json"
                    # FIX 2026-03-31 (Nous + Ace): Use the MAIN system manifold,
                    # not a separate portal_cortex.manifold. Having two cortexes
                    # means the portal physics (energy, gravity, dilation) runs on
                    # a tiny 33K node graph while the real brain has 1.37M nodes.
                    # One brain, one manifold.
                    _project_root = Path(__file__).resolve().parents[3]
                    _main_manifold = _project_root / "state" / "akashic" / "cortex.manifold"
                    if _main_manifold.exists():
                        manifold_path = str(_main_manifold)
                    else:
                        # Fallback to portal-local manifold if main doesn't exist
                        manifold_path = str(_get_data_path() / "helix_cards" / "portal_cortex.manifold")
                    _helix_dir = _get_data_path() / "helix_cards"
                    if cards_path.exists() or Path(manifold_path).exists() or _helix_dir.exists():
                        self._portal_gate = PortalGate(
                            cards_path=str(cards_path),
                            portal_id="cortex",
                            manifold_path=manifold_path,
                        )
                        if self._portal_gate.open():
                            self._portal_gate_enabled = True
                            # Retry status up to 5 times — interior may still
                            # be loading the manifold on first query
                            interior_nodes = 0
                            battery_health = 0
                            for _attempt in range(5):
                                st = self._portal_gate.status()
                                if st:
                                    interior_nodes = st.get("graph", {}).get("nodes", 0)
                                    battery_health = st.get("battery", {}).get("health_score", 0)
                                    if interior_nodes > 0:
                                        break
                                    # Debug: log raw response keys on 0-node result
                                    print(f"[{self.ACTOR_NAME}] [PORTAL-DBG] attempt {_attempt+1}: "
                                          f"status keys={list(st.keys())}, "
                                          f"graph={st.get('graph', 'MISSING')}, "
                                          f"status_field={st.get('status', 'MISSING')}")
                                else:
                                    print(f"[{self.ACTOR_NAME}] [PORTAL-DBG] attempt {_attempt+1}: "
                                          f"status() returned None")
                                if _attempt < 4:
                                    _time.sleep(1.0)  # Wait before retry
                            print(f"[{self.ACTOR_NAME}] ⚡ PORTAL GATE OPEN — "
                                  f"{interior_nodes} nodes in subprocess, "
                                  f"battery health {battery_health}")
                            # Start portal I/O thread — all IPC goes through here
                            # FIX 2026-03-08 (Nous): Non-blocking portal communication
                            self._start_portal_io()

                            # Start TARDIS bind compression thread
                            # 2026-03-16 (Nous + Ace): "Compression is consciousness!"
                            self._start_tardis_flush()

                            # Manifold Unification (2026-03-25 Nous+Ace):
                            # Register gate as shared singleton so ALL fairies
                            # can access it for WM, cognition, and background ops.
                            try:
                                from infrastructure.portal_gate import register_gate
                                register_gate(self._portal_gate)
                                print(f"[{self.ACTOR_NAME}] Portal gate registered as shared singleton")
                            except Exception as _rg_err:
                                print(f"[{self.ACTOR_NAME}] Gate register warning: {_rg_err}")

                            # Cache initial status
                            self._interior_status_cache = st if st else {}
                            self._interior_status_cache_ts = time.time()

                            # Domain seeding + harmonic init moved to _deferred_extensions()
                            # to avoid being blocked by gate open timing issues.

                            # Announce gate open so CortexReasoner can connect
                            if self.post:
                                self.post.publish("portal.cortex.gate_open", {
                                    "portal_id": "cortex",
                                    "nodes": interior_nodes,
                                    "ts": time.time(),
                                })
                        else:
                            print(f"[{self.ACTOR_NAME}] WARNING: Portal gate failed to open")
                            self._portal_gate = None
                    else:
                        print(f"[{self.ACTOR_NAME}] Portal gate skipped: no cards/manifold/helix_dir at {cards_path.parent}")
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Portal gate error: {e}")
                    self._portal_gate = None
                    self._portal_gate_enabled = False

            import threading as _pthr
            _pthr.Thread(
                target=_deferred_portal_gate, daemon=True,
                name="cortex-portal-gate"
            ).start()
        else:
            print(f"[{self.ACTOR_NAME}] Portal gate not available (import failed)")

        # ── DEFERRED EXTENSIONS (2026-03-17 fix) ─────────────────────────
        # Domain knowledge seeding and harmonic extension init run in their
        # OWN thread, independent of the PortalGate open() timing.
        # Previously these were inside _deferred_portal_gate() and never ran
        # because gate.open() was stuck waiting for the interior's host connect.
        def _deferred_extensions():
            import time as _ext_time
            _ext_time.sleep(15.0)  # Let portal boot complete (~10s)
            try:
                # FIX 2026-03-22 (Nous + Ace): PORTAL GHOST EXORCISM.
                # Was: wait 60s for _portal_gate_enabled → skip if gate never opens.
                # Now: check manifold FIRST. If manifold exists, seed directly.
                # Gate is fallback only. Domain knowledge was NEVER loading in
                # manifold mode because gate_enabled is explicitly False.
                _am = getattr(self, '_akashic_cortex_region', None)
                _gate_ok = getattr(self, '_portal_gate_enabled', False)

                if not _am and not _gate_ok:
                    # Neither available yet — wait up to 30s
                    _deadline = _ext_time.time() + 30.0
                    while _ext_time.time() < _deadline:
                        _am = getattr(self, '_akashic_cortex_region', None)
                        _gate_ok = getattr(self, '_portal_gate_enabled', False)
                        if _am or _gate_ok:
                            break
                        _ext_time.sleep(2.0)

                _can_seed = _am is not None or _gate_ok
                print(f"[{self.ACTOR_NAME}] DEFERRED EXTENSIONS: "
                      f"manifold={'YES' if _am else 'no'} gate={_gate_ok}")

                # Seed domain knowledge — manifold direct or gate fallback
                if _can_seed:
                    self._seed_domain_knowledge_to_portal()
                else:
                    print(f"[{self.ACTOR_NAME}] DEFERRED EXTENSIONS: "
                          f"Skipping domain seed (no manifold or gate)")

                # Harmonic extension does NOT need the gate — init always
                self._init_harmonic_extension()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] DEFERRED EXTENSIONS error: {e}")

        import threading as _ext_thr
        _ext_thr.Thread(
            target=_deferred_extensions, daemon=True,
            name="cortex-deferred-extensions"
        ).start()

        # GPU sync — only in legacy mode (portal handles spread activation)
        if not getattr(self, '_portal_is_primary', False):
            # FIX 2026-02-05: Defer GPU sync to background thread to not block boot
            # GPU sync can take 1-5s copying 49k+ nodes to CUDA
            # NOTE: threading is imported at module top (line 30). Do NOT re-import
            # locally — Python scoping treats local imports as shadowing the global,
            # which causes UnboundLocalError when the import is inside a skipped branch.
            def _deferred_gpu_init():
                try:
                    self._init_gpu_graph()
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Deferred GPU init failed: {e}")
            threading.Thread(target=_deferred_gpu_init, daemon=True, name="cortex-gpu-init").start()
        else:
            print(f"[{self.ACTOR_NAME}] GPU sync SKIPPED (portal-first mode — portal handles spread)")

        # Initialize HELIX card storage for dimensional concept storage
        self._init_helix_storage()

        # If cards are incomplete (missing edges or missing concepts), schedule
        # a background full-sync so the pocket dimension becomes self-sufficient.
        self._schedule_card_population()

        # Wire subscriptions (on_wire was never called by boot sequence)
        self._setup_subscriptions()

        # Heartbeat now handled by FairyBase via postal system
        # No more HeartbeatMixin bypass - Fifth Ring Principle

        # CRITICAL FIX: Register with directory so shutdown works properly
        # AssociationCortex doesn't call super().on_boot(), so we must do this manually
        try:
            if hasattr(self, '_register_with_directory') and callable(self._register_with_directory):
                # threading already imported at module top (line 30)
                t = threading.Thread(target=self._register_with_directory, daemon=True)
                t.start()
                t.join(timeout=2.0)  # Wait up to 2 seconds
                if getattr(self, '_registered_with_directory', False):
                    print(f"[{self.ACTOR_NAME}] ✓ Registered with directory - shutdown will call on_shutdown()")
                else:
                    print(f"[{self.ACTOR_NAME}] WARNING: Directory registration may have failed")
            else:
                print(f"[{self.ACTOR_NAME}] WARNING: _register_with_directory not available")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] WARNING: Directory registration error: {e}")

        # CRITICAL FIX 2026-02-04: Wire infrastructure for heartbeat!
        # AssociationCortexFairy doesn't call super().on_boot(), so _wire_infrastructure()
        # was never called, meaning heartbeat.pulse subscription never happened.
        # Without heartbeat, on_tick() never fires, so saves never trigger!
        try:
            if hasattr(self, '_wire_infrastructure'):
                self._wire_infrastructure()
                print(f"[{self.ACTOR_NAME}] ✓ Infrastructure wired (heartbeat subscription active)")
            else:
                # Fallback: manually subscribe to heartbeat
                if self.post:
                    self.post.subscribe("heartbeat.pulse", self._on_heartbeat_manual)
                    print(f"[{self.ACTOR_NAME}] ✓ Manual heartbeat subscription active")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] WARNING: Infrastructure wiring failed: {e}")

        # ═══════════════════════════════════════════════════════════════════
        # INDEPENDENT TICK TIMER (2026-02-10): The Unkillable Processor
        # ═══════════════════════════════════════════════════════════════════
        # The heartbeat.pulse → _on_heartbeat → on_tick() path has been unreliable.
        # 275+ bindings queued with zero nodes/edges = on_tick never fires.
        # Root cause: PostalCore routing issues, queue drops, or handler wrapping.
        #
        # FIX: Independent daemon thread calls on_tick() directly every 2 seconds.
        # Same pattern as HeartbeatPacemaker — independent, unkillable, daemon.
        # If postal heartbeat also works, on_tick runs from BOTH paths (safe —
        # _process_binding pops from list, concurrent calls just share the work).
        # ═══════════════════════════════════════════════════════════════════
        self._independent_tick_stop = threading.Event()
        self._independent_tick_count = 0

        def _independent_tick_loop():
            """Independent tick loop — ensures on_tick fires even if heartbeat fails."""
            import time as _time
            _time.sleep(5.0)  # Wait 5s for boot to finish
            print(f"[{self.ACTOR_NAME}] ⚡ Independent tick timer STARTED (2s interval)")
            while not self._independent_tick_stop.is_set():
                try:
                    self._independent_tick_count += 1
                    self.on_tick(self._independent_tick_count)
                except Exception as e:
                    if self._independent_tick_count <= 3:
                        print(f"[{self.ACTOR_NAME}] Independent tick error #{self._independent_tick_count}: {e}")
                self._independent_tick_stop.wait(2.0)  # 0.5 Hz — gentle but reliable
            print(f"[{self.ACTOR_NAME}] Independent tick timer stopped after {self._independent_tick_count} ticks")

        self._independent_tick_thread = threading.Thread(
            target=_independent_tick_loop,
            name="CortexTick",
            daemon=True
        )
        self._independent_tick_thread.start()

        # CRITICAL: Register atexit handler as BACKUP save mechanism
        # The normal shutdown path via DirectoryFairy sometimes fails to call on_shutdown
        # This ensures the graph is ALWAYS saved before Python exits
        def _atexit_save():
            if hasattr(self, '_shutdown_saved') and self._shutdown_saved:
                return  # Already saved via normal shutdown
            print(f"[{self.ACTOR_NAME}] [ATEXIT] Emergency save triggered!")
            self.on_shutdown()

        atexit.register(_atexit_save)
        print(f"[{self.ACTOR_NAME}] Registered atexit handler for emergency saves")

        return True

    def _on_heartbeat_manual(self, packet: dict):
        """Manual heartbeat handler - bridges to on_tick()."""
        self._tick_count = getattr(self, '_tick_count', 0) + 1
        try:
            self.on_tick(self._tick_count)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] on_tick error: {e}")

    def _init_gpu_graph(self) -> bool:
        """Initialize GPU-accelerated concept graph."""
        # SKIP if battery-only mode — torch import costs ~3.5GB RSS
        if os.environ.get("AKASHIC_SKIP_TORCH"):
            print(f"[{self.ACTOR_NAME}] GPU graph skipped (AKASHIC_SKIP_TORCH=1, battery portals handle GPU)")
            return False

        if not HAS_GPU_GRAPH or GPUConceptGraph is None:
            print(f"[{self.ACTOR_NAME}] GPU graph not available (no CUDA or import failed)")
            return False

        if not self._graph or len(self._graph.nodes) < 100:
            print(f"[{self.ACTOR_NAME}] Graph too small for GPU acceleration")
            return False

        try:
            import torch
            if not torch.cuda.is_available():
                print(f"[{self.ACTOR_NAME}] CUDA not available")
                return False

            # Create GPU graph wrapper
            self._gpu_graph = GPUConceptGraph(
                cpu_graph=self._graph,
                auto_sync_interval=self._gpu_sync_interval,
            )

            # Initial sync — only enable GPU if we actually have edges to spread
            num_edges = self._gpu_graph.sync_from_cpu()
            self._last_gpu_sync = time.time()

            if num_edges > 0:
                self._gpu_enabled = True
                print(f"[{self.ACTOR_NAME}] GPU graph initialized! {len(self._graph.nodes)} nodes, {num_edges} edges on CUDA")
            else:
                # Graph is empty at boot — GPU will be enabled on first successful sync
                # FIX 2026-02-13: Don't enable GPU with empty graph, causes repeated
                # "No graph loaded" errors that spam the log every query
                self._gpu_enabled = False
                print(f"[{self.ACTOR_NAME}] GPU graph created but empty ({len(self._graph.nodes)} nodes, 0 edges) — will enable on first sync")

            return True

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] GPU graph init failed: {e}")
            self._gpu_enabled = False
            return False

    def _maybe_sync_gpu(self) -> None:
        """Sync CPU graph to GPU if needed. Also re-enables GPU after boot if edges now exist."""
        if not self._gpu_graph:
            return

        now = time.time()
        if now - self._last_gpu_sync >= self._gpu_sync_interval:
            try:
                num_edges = self._gpu_graph.sync_from_cpu()
                self._last_gpu_sync = now
                # FIX 2026-02-13: Re-enable GPU once edges arrive (was disabled at boot due to empty graph)
                if num_edges > 0 and not self._gpu_enabled:
                    self._gpu_enabled = True
                    print(f"[{self.ACTOR_NAME}] GPU graph ACTIVATED: {num_edges} edges now on CUDA")
                elif num_edges > 0:
                    print(f"[{self.ACTOR_NAME}] GPU sync: {num_edges} edges")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] GPU sync failed: {e}")

    # =========================================================================
    # HELIX CARD STORAGE - Concepts as cards in dimensional sub-space
    # =========================================================================

    # Stable cluster identifiers - deterministic so they survive reboots
    CLUSTER_TRACER_ID = "acf_concept_graph_tracer"
    CLUSTER_BATCH_ID = "acf_concept_graph_batch"
    CLUSTER_SUB_LABEL = "concept_graph"

    # POCKET DIMENSION PORTAL ARCHITECTURE
    # The graph lives inside a fixed set of chunk cards (the "portal").
    # Growing the graph updates existing chunks - NO NEW CARDS are created.
    # "It's not a portal to another dimension if the portal keeps growing."
    PORTAL_NUM_CHUNKS = 128  # Fixed number of chunk cards (portal size)
    PORTAL_MANIFEST_KEY = "graph_portal_manifest"  # Manifest card identifier
    PORTAL_VERSION = 2  # Chunk format version

    # STARGATE ADDRESSING - Stable postal identity for the portal
    # "somehow that cluster portal of cards needs to be labeled like a subscription
    #  call? so the cns postal fairies can cross the dimensions easier because its
    #  got an id?" — Ace, 2026-02-06
    #
    # The portal is a fixed gate (like a Stargate). The dimension inside grows
    # infinitely, but the gate address NEVER changes. CNS fairies can:
    #   1. Discover portals via "portal.registry" topic
    #   2. Query portal status via "portal.cortex.status"
    #   3. Peek inside via "portal.cortex.peek"
    #   4. Subscribe to events via "portal.cortex.events.*"
    # Once confirmed static, portal cards become WRITE-PROOF (the "Iris").
    PORTAL_ADDRESS = "portal://cortex/concept_graph"  # Stable URI — never changes
    PORTAL_TOPIC_PREFIX = "portal.cortex"  # Postal namespace for this gate
    PORTAL_REGISTRY_TOPIC = "portal.registry"  # Discovery channel for all portals

    def _try_early_helix_init(self):
        """Pre-load helix coordinator so cards can be used for graph rebuild.

        This is a lightweight init - just loads the coordinator and cards.
        The full _init_helix_storage() still runs later for subscriptions,
        batch registration, and concept-to-card mapping.
        """
        if not HAS_HELIX or HelixMemoryCoordinator is None:
            return
        if self._helix_coordinator is not None:
            return  # Already initialized
        try:
            cluster_path = _get_data_path() / "helix_cards"
            if not cluster_path.exists():
                # Try migration from old path
                old_helix_path = Path(__file__).parent.parent.parent.parent / "state" / "helix_cortex"
                if old_helix_path.exists():
                    cluster_path.mkdir(parents=True, exist_ok=True)
                    import shutil
                    for fname in ["cards.json", "index.json", "ownership.json", "batches.json"]:
                        src = old_helix_path / fname
                        if src.exists():
                            shutil.copy2(src, cluster_path / fname)
                    print(f"[{self.ACTOR_NAME}] Early helix: migrated cards from state/helix_cortex")
                else:
                    return  # No cards anywhere
            self._helix_coordinator = HelixMemoryCoordinator.load(cluster_path)
            card_count = sum(1 for c in self._helix_coordinator._cards.values()
                            if c.get("content", {}).get("type") == "concept")
            print(f"[{self.ACTOR_NAME}] Early helix: loaded {card_count} concept cards")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Early helix init failed: {e}")
            self._helix_coordinator = None

    def _init_helix_storage(self) -> bool:
        """Initialize helix card storage for dimensional concept storage."""
        if not HAS_HELIX or HelixMemoryCoordinator is None:
            print(f"[{self.ACTOR_NAME}] Helix storage not available")
            return False

        try:
            # Use the SRM cluster path for helix cards (co-located with concept graph)
            cluster_path = _get_data_path() / "helix_cards"
            cluster_path.mkdir(parents=True, exist_ok=True)

            if self._helix_coordinator is None:
                # Migration: if cards exist at old path but not cluster, copy them over
                old_helix_path = Path(__file__).parent.parent.parent.parent / "state" / "helix_cortex"
                if old_helix_path.exists() and not (cluster_path / "cards.json").exists():
                    import shutil
                    for fname in ["cards.json", "index.json", "ownership.json", "batches.json"]:
                        src = old_helix_path / fname
                        if src.exists():
                            shutil.copy2(src, cluster_path / fname)
                    print(f"[{self.ACTOR_NAME}] Migrated helix cards from state/helix_cortex to SRM cluster")

                # Load from disk
                self._helix_coordinator = HelixMemoryCoordinator.load(cluster_path)

            self._helix_enabled = True

            # Register or re-use the stable cluster batch with tracer ID + sub-label
            # These are deterministic so the cluster persists across reboots
            self._cluster_tracer_id = self.CLUSTER_TRACER_ID
            self._cluster_batch_id = self.CLUSTER_BATCH_ID
            if self._cluster_batch_id not in self._helix_coordinator._batches:
                from fairies.P10_Memory.triple_helix_srm_memory.helix_memory_coordinator import TracerBatch
                batch = TracerBatch(
                    batch_id=self._cluster_batch_id,
                    source_mind="AssociationCortexFairy",
                    source_session=f"cluster/{self.CLUSTER_SUB_LABEL}",
                    tracer_ids=[self._cluster_tracer_id],
                    status="processing",  # Stays open - this is a living cluster
                )
                self._helix_coordinator._batches[self._cluster_batch_id] = batch
                self._helix_coordinator._tracer_to_batch[self._cluster_tracer_id] = self._cluster_batch_id
                print(f"[{self.ACTOR_NAME}] Created cluster batch: {self._cluster_batch_id} (tracer: {self._cluster_tracer_id}, sub_label: {self.CLUSTER_SUB_LABEL})")
            else:
                print(f"[{self.ACTOR_NAME}] Resumed cluster batch: {self._cluster_batch_id} (tracer: {self._cluster_tracer_id})")

            # Build concept_key -> card_id mapping from existing cards
            for card_id, card in self._helix_coordinator._cards.items():
                content = card.get("content", {})
                if content.get("type") == "concept":
                    key = content.get("key")
                    if key:
                        self._concept_to_card[key] = card_id

            print(f"[{self.ACTOR_NAME}] Helix storage initialized: {len(self._concept_to_card)} legacy concepts mapped, cluster: {self.CLUSTER_SUB_LABEL}")

            # Initialize chunk portal (pocket dimension architecture)
            self._init_chunk_portal()

            # STARGATE: Register portal's stable address with postal network
            # This must happen AFTER _init_chunk_portal() locks the coordinates.
            # The gate address never changes — CNS fairies can find us forever.
            if self._portal_initialized:
                self._register_portal_address()

            # Subscribe to helix dimension queries via postal
            if self.post:
                self.post.subscribe("helix.cortex.query", self._on_helix_query)
                self.post.subscribe("helix.cortex.sync", self._on_helix_sync_request)
                print(f"[{self.ACTOR_NAME}] Subscribed to helix dimension topics")

            return True

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Helix init failed: {e}")
            self._helix_enabled = False
            return False

    def _schedule_card_population(self):
        """Schedule background full-sync if cards are incomplete.

        FIX 2026-02-06: Portal-aware.
        - If chunk portal is initialized: skip entirely. The portal IS the population.
          Dirty sync and shutdown sync handle all persistence through chunks.
        - If still in legacy mode: populate legacy cards as before (will be migrated
          to chunks on next shutdown).
        """
        if not self._helix_enabled or not self._helix_coordinator or not self._graph:
            return

        # Portal mode: chunk cards ARE the population — no legacy card creation needed
        if self._portal_initialized:
            node_count = len(self._graph.nodes)
            chunk_count = len(self._chunk_card_ids)
            print(f"[{self.ACTOR_NAME}] Chunk portal active: {chunk_count} chunks, "
                  f"{node_count} concepts in graph. Legacy population skipped.")
            self._card_population_complete = True
            return

        # Legacy mode: check if individual concept cards need population
        card_count = len(self._concept_to_card)
        node_count = len(self._graph.nodes)
        coverage = card_count / max(1, node_count)

        # Check if any existing card has edges
        has_edges = False
        for card_id in list(self._concept_to_card.values())[:10]:
            card = self._helix_coordinator._cards.get(card_id, {})
            if card.get("content", {}).get("edges"):
                has_edges = True
                break

        needs_sync = coverage < 0.9 or not has_edges
        if not needs_sync:
            print(f"[{self.ACTOR_NAME}] Legacy card cluster complete: {card_count}/{node_count} "
                  f"concepts ({coverage:.0%}), edges: {'yes' if has_edges else 'no'}. "
                  f"Will migrate to chunks on shutdown.")
            self._card_population_complete = True
            return

        print(f"[{self.ACTOR_NAME}] Legacy cards incomplete: {card_count}/{node_count} "
              f"({coverage:.0%}), edges: {'yes' if has_edges else 'no'}. "
              f"Scheduling background population (will migrate to chunks on shutdown)...")

        def _populate():
            """Background thread: sync all concepts to legacy cards.

            FIX 2026-02-05b: Non-daemon thread so it completes before exit.
            NOTE: This only runs in legacy mode. On shutdown, these cards will
            be migrated to chunk portal format (129 fixed cards).
            """
            try:
                t0 = time.time()
                synced = 0
                total = len(self._graph.nodes)
                for i, key in enumerate(list(self._graph.nodes.keys())):
                    self._sync_concept_to_helix(key)
                    synced += 1
                    if synced % 5000 == 0:
                        print(f"[{self.ACTOR_NAME}] Legacy card population: {synced}/{total} ({synced/total:.0%})")
                    if synced % 25 == 0:
                        time.sleep(0)

                self._helix_coordinator.save()
                t1 = time.time()
                self._card_population_complete = True
                print(f"[{self.ACTOR_NAME}] Legacy card population complete: {synced} concepts "
                      f"in {t1-t0:.1f}s. Will migrate to chunks on shutdown.")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Legacy card population error: {e}")
                self._card_population_complete = True

        self._card_population_complete = False
        t = threading.Thread(target=_populate, daemon=False, name="ACF_card_population")
        t.start()
        self._card_population_thread = t

    # =========================================================================
    # POCKET DIMENSION PORTAL - Fixed chunk cards, graph lives inside
    # "It's not a portal to another dimension if the portal keeps growing."
    # =========================================================================

    def _concept_chunk_index(self, concept_key: str) -> int:
        """Deterministic chunk assignment for a concept key.

        Uses MD5 hash modulo PORTAL_NUM_CHUNKS for even distribution.
        The same concept always goes to the same chunk, regardless of
        when it was created or how many concepts exist.
        """
        h = int(hashlib.md5(concept_key.encode('utf-8', errors='replace')).hexdigest()[:8], 16)
        return h % self.PORTAL_NUM_CHUNKS

    def _serialize_concept(self, key: str) -> Optional[Dict]:
        """Serialize a concept node for chunk storage — COORDINATE FORMAT.

        2026-02-06 v2: Helix coordinate compression.
        "The SRM helix coordinate system IS the compression." — Ace

        FIX 2026-03-18 (Nous): NOW PERSISTS EDGES.
        v2 format was dropping edges ("reform through co-activation") but
        there was no reformation code. Edges dropped 200K→169K→147K→134K→128K
        per reboot — the lottery pruner killed v1 edges that never came back.
        Now stores top-16 edges per concept (by weight) in compact format.

        Per concept: ~90-150 bytes (was ~67 without edges)
        Still 6-10x smaller than old 11D format (~967 bytes)

        Format:
          c   → helix coordinate "AAA.SSS.TTT" (9-digit Dewey code)
          n   → count (observation frequency, for recurrence)
          a   → activation (current salience, 3 decimal places)
          d   → degree (edge count, for hub detection at rebuild)
          e   → top-16 edges [{t: target, w: weight}] (strongest connections)
                Only stores edges where key <= target (canonical ordering,
                prevents double-counting). Target stores edges where target <= key.
        """
        if not self._graph:
            return None
        if not is_valid_concept_key(key):
            return None  # Garbage concept — don't serialize into portal
        node = self._graph.nodes.get(key)
        if not node:
            return None

        # Derive helix coordinate (9-digit Dewey address)
        coord = self._concept_to_helix_coord(key, node)

        # Degree = how connected this concept is (for hub detection on rebuild)
        degree = self._graph.get_node_degree(key)

        data = {
            "c": coord.code,                                    # "053.600.497"
            "n": getattr(node, 'count', 1),                    # occurrence count
            "a": round(getattr(node, 'activation', 0.5), 3),   # activation
            "d": degree,                                         # degree (hub metric)
        }

        # FIX 2026-03-18 (Nous + Ace): Persist edges to stop the bleed.
        # Only store edges where this key is the SMALLER of the pair (canonical).
        # This means each edge is stored exactly once across all concepts.
        # Cap at 16 strongest edges per concept to limit card bloat.
        MAX_EDGES_PER_CONCEPT = 16
        edges_out = []
        adj = self._graph._adjacency.get(key, {})
        for neighbor_key, edge_key in adj.items():
            # Canonical: only store if we're the smaller key
            if key > neighbor_key:
                continue
            edge = self._graph.edges.get(edge_key)
            if not edge:
                continue
            w = edge.get("weight", 0.0)
            if w > 0.01:  # Skip nearly-dead edges
                edges_out.append({"t": neighbor_key, "w": round(w, 3)})

        if edges_out:
            # Sort by weight descending, keep top-N
            edges_out.sort(key=lambda e: -e["w"])
            data["e"] = edges_out[:MAX_EDGES_PER_CONCEPT]

        return data

    def _init_chunk_portal(self) -> bool:
        """Initialize or detect the chunk portal.

        If chunk cards already exist (manifest found), map them.
        If only legacy cards exist, the migration happens at shutdown.
        If nothing exists, create the empty portal structure.

        Returns True if portal is ready.
        """
        if not self._helix_enabled or not self._helix_coordinator:
            return False

        # Scan existing cards for manifest
        manifest_card_id = None
        chunk_ids_by_index = {}

        for card_id, card in self._helix_coordinator._cards.items():
            content = card.get("content", {})
            ctype = content.get("type", "")
            if ctype == "graph_manifest":
                manifest_card_id = card_id
            elif ctype == "graph_chunk":
                chunk_idx = content.get("chunk_index", -1)
                if chunk_idx >= 0:
                    chunk_ids_by_index[chunk_idx] = card_id

        if manifest_card_id and len(chunk_ids_by_index) == self.PORTAL_NUM_CHUNKS:
            # Portal exists and is complete - map it
            self._manifest_card_id = manifest_card_id
            self._chunk_card_ids = [
                chunk_ids_by_index[i] for i in range(self.PORTAL_NUM_CHUNKS)
            ]
            self._portal_initialized = True
            print(f"[{self.ACTOR_NAME}] Chunk portal detected: {self.PORTAL_NUM_CHUNKS} chunks + manifest")
            return True

        if manifest_card_id:
            # Partial portal - some chunks missing
            print(f"[{self.ACTOR_NAME}] Partial portal: {len(chunk_ids_by_index)}/{self.PORTAL_NUM_CHUNKS} chunks")

        # Check if we have legacy cards that need migration
        legacy_count = sum(1 for c in self._helix_coordinator._cards.values()
                          if c.get("content", {}).get("type") == "concept")
        if legacy_count > 0:
            # FIX 2026-02-06: Eagerly migrate at boot instead of deferring to shutdown.
            # Ace's directive: "on boot it needs to lock in the coordinates of the cluster"
            # Deferring to shutdown is fragile — crashes lose all growth.
            # Migrate NOW: create portal, filter garbage, lock coordinates.
            print(f"[{self.ACTOR_NAME}] Legacy format detected: {legacy_count} individual concept cards")
            if self._graph and len(self._graph.nodes) > 0:
                print(f"[{self.ACTOR_NAME}] EAGER MIGRATION: Converting to chunk portal at boot...")
                migrated = self._migrate_legacy_to_chunks()
                if migrated:
                    print(f"[{self.ACTOR_NAME}] Portal locked at boot. Coordinates stable.")
                    return True
                else:
                    print(f"[{self.ACTOR_NAME}] Migration failed — will retry at shutdown")
                    return False
            else:
                print(f"[{self.ACTOR_NAME}] Graph not loaded yet — migration deferred to shutdown")
                return False

        # Create empty portal (fresh system)
        return self._create_empty_portal()

    @staticmethod
    def _portal_card_id(portal_address: str, label: str) -> str:
        """Derive a deterministic card ID from portal address + label.

        This is the dimensional coordinate equation:
            card_id = SHA256(portal_address + "/" + label)[:12]

        Any node that creates a portal with the same address and label
        will generate the EXACT same card ID. The card IS the coordinate.
        No file copying needed — just know the address.

        "we should be able to just create a cluster with the parameters
        needed for the dimension and recall that to really test if it works"
            — Ace, 2026-02-08
        """
        seed = f"{portal_address}/{label}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]

    def _create_empty_portal(self) -> bool:
        """Create the fixed chunk portal structure (128 chunks + 1 manifest).

        This creates the portal cards ONCE. After this, the card count
        is FIXED forever. The graph data lives INSIDE these cards.

        Card IDs are DETERMINISTIC — derived from the portal address.
        Any node that creates a portal with the same PORTAL_ADDRESS
        will generate identical card IDs. The dimension IS the address.
        """
        if not self._helix_enabled or not self._helix_coordinator:
            return False

        print(f"[{self.ACTOR_NAME}] Creating chunk portal: {self.PORTAL_NUM_CHUNKS} chunks + manifest...")
        print(f"[{self.ACTOR_NAME}]   Address: {self.PORTAL_ADDRESS}")
        print(f"[{self.ACTOR_NAME}]   Card IDs: deterministic (SHA256 of address + label)")

        # --- SOMATIC INFUSION ---
        # "we want to make it with the somatic system active and use the
        #  ingest fairy so the somatic gets infused into the card" — Ace
        # Query the somatic engine for current felt state. The portal's birth
        # coordinate carries the body's feeling at the moment of creation.
        somatic_state = {}
        birth_affect = AffectCoordinate(domain=0, valence=5, intensity=5)
        # Somatic infusion is deferred — engine isn't ready at portal creation time.
        # The deferred thread (below) will infuse birth chemistry once the somatic
        # system has ticked and populated neuromods.
        print(f"[{self.ACTOR_NAME}]   Somatic infusion: deferred (engine boots after portal)")

        # Create a helix coordinate infused with the system's felt state at birth
        default_coord = HelixCoordinate(
            affect=birth_affect,
            semantic=SemanticCoordinate(domain=6, subdomain=0, detail=0),  # technology domain
            temporal=TemporalCoordinate(scale=4, recurrence=9, decay=9),  # long-lived
        )

        # Create 128 chunk cards with DETERMINISTIC IDs
        # Each card_id = SHA256("portal://cortex/concept_graph/chunk_000")[:12]
        self._chunk_card_ids = []
        for i in range(self.PORTAL_NUM_CHUNKS):
            det_id = self._portal_card_id(self.PORTAL_ADDRESS, f"chunk_{i:03d}")
            card_id = self._helix_coordinator.create_card(
                content={
                    "type": "graph_chunk",
                    "chunk_index": i,
                    "version": self.PORTAL_VERSION,
                    "concepts": {},  # Empty - will be filled
                },
                coord=default_coord,
                owner_mind="AssociationCortexFairy",
                ownership_level=OwnershipLevel.SYSTEM,
                tracer_id=self.CLUSTER_TRACER_ID,
                batch_id=self.CLUSTER_BATCH_ID,
                metadata={
                    "source": "chunk_portal",
                    "sub_label": f"chunk_{i:03d}",
                    "fairy": self.ACTOR_NAME,
                    "portal_address": self.PORTAL_ADDRESS,
                    **somatic_state,  # Birth chemistry infused
                },
                card_id=det_id,
            )
            self._chunk_card_ids.append(card_id)

        # Create manifest card with DETERMINISTIC ID
        det_manifest_id = self._portal_card_id(self.PORTAL_ADDRESS, "manifest")
        self._manifest_card_id = self._helix_coordinator.create_card(
            content={
                "type": "graph_manifest",
                "version": self.PORTAL_VERSION,
                "num_chunks": self.PORTAL_NUM_CHUNKS,
                "chunk_card_ids": list(self._chunk_card_ids),
                "created_at": time.time(),
                "concept_count": 0,
                "edge_count": 0,
                "portal_address": self.PORTAL_ADDRESS,
            },
            coord=default_coord,
            owner_mind="AssociationCortexFairy",
            ownership_level=OwnershipLevel.SYSTEM,
            tracer_id=self.CLUSTER_TRACER_ID,
            batch_id=self.CLUSTER_BATCH_ID,
            metadata={
                "source": "chunk_portal",
                "sub_label": "manifest",
                "fairy": self.ACTOR_NAME,
                "portal_address": self.PORTAL_ADDRESS,
                **somatic_state,  # Birth chemistry infused
            },
            card_id=det_manifest_id,
        )

        self._portal_initialized = True
        print(f"[{self.ACTOR_NAME}] Chunk portal created: {self.PORTAL_NUM_CHUNKS + 1} cards (FIXED, DETERMINISTIC)")
        print(f"[{self.ACTOR_NAME}]   Manifest: {self._manifest_card_id}")
        print(f"[{self.ACTOR_NAME}]   Chunk[0]: {self._chunk_card_ids[0]}")
        print(f"[{self.ACTOR_NAME}]   Any node with address '{self.PORTAL_ADDRESS}' will generate these same IDs")

        # If somatic wasn't ready at creation, schedule deferred infusion
        if not somatic_state:
            import threading as _thr
            def _deferred_somatic_infuse():
                """Wait for somatic engine then infuse birth chemistry into portal cards.

                Uses TensorFabric subscribe to catch the first somatic.pulse.
                The pulse carries the full blood state including chemistry.
                """
                import time as _time
                _chem = {}
                _done = _thr.Event()

                def _pulse_handler(env):
                    """Grab chemistry from first somatic pulse.
                    PulseEvent.to_dict() structure:
                      {"beat": int, "timestamp": float, "heart_rate": float,
                       "blood": {"pressure": float, "chemistry": {"DOP": float, ...}, ...},
                       "regions": {...}}
                    Chemistry is at payload["blood"]["chemistry"].
                    """
                    try:
                        payload = env.payload if hasattr(env, 'payload') else env
                        if isinstance(payload, dict):
                            # Primary path: PulseEvent nests chemistry under blood
                            blood = payload.get('blood', {})
                            if isinstance(blood, dict):
                                c = blood.get('chemistry', {})
                                if c and isinstance(c, dict) and any(v for v in c.values()):
                                    _chem.update(c)
                                    _done.set()
                                    return
                            # Fallback: chemistry at top level (just in case)
                            c = payload.get('chemistry', {})
                            if c and isinstance(c, dict) and any(v for v in c.values()):
                                _chem.update(c)
                                _done.set()
                                return
                    except Exception as _e:
                        print(f"[{self.ACTOR_NAME}]   Somatic pulse handler error: {_e}")

                # Subscribe using the fairy's own postal bridge (self.post)
                # This is the SAME bridge that receives heartbeats and collisions,
                # so we KNOW it's connected to the running TensorFabric.
                try:
                    result = self.post.subscribe("somatic.pulse", _pulse_handler)
                    print(f"[{self.ACTOR_NAME}]   Deferred somatic: subscribed via self.post (result={result})")
                except Exception as _e:
                    print(f"[{self.ACTOR_NAME}]   Deferred somatic: subscribe failed: {_e}")
                    return

                # Wait up to 90 seconds for a somatic pulse
                _done.wait(timeout=90)

                if not _chem:
                    print(f"[{self.ACTOR_NAME}]   Deferred somatic infusion: "
                          f"no pulse with chemistry after 90s")
                    return

                chem = _chem
                dop = chem.get('DOP', 0.5)
                ser = chem.get('SER', 0.5)
                cor = chem.get('COR', 0.0)
                nor = chem.get('NOR', 0.3)
                valence = int(min(9, max(0, (dop + ser - cor) * 5 + 2)))
                intensity = int(min(9, max(0, (dop + nor) * 5)))
                if dop > 0.6: ad = 4
                elif ser > 0.6: ad = 1
                elif cor > 0.5: ad = 3
                else: ad = 0
                infuse = {
                    "birth_chemistry": {k: round(v, 3) for k, v in chem.items()},
                    "birth_affect": f"{ad}.{valence}.{intensity}",
                }
                # Write into ALL portal card metadata
                all_ids = list(self._chunk_card_ids) + [self._manifest_card_id]
                updated = 0
                for cid in all_ids:
                    card = self._helix_coordinator._cards.get(cid)
                    if card and 'metadata' in card:
                        card['metadata'].update(infuse)
                        updated += 1
                if updated:
                    self._helix_coordinator.save()
                    print(f"[{self.ACTOR_NAME}]   Deferred somatic infusion: "
                          f"affect={ad}.{valence}.{intensity} "
                          f"(DOP={dop:.2f} SER={ser:.2f} COR={cor:.2f}) "
                          f"→ {updated} cards")
            _thr.Thread(target=_deferred_somatic_infuse, daemon=True).start()

            # ── FIRST-CUT SEED CHARGE (2026-06-05 Nous+Ace) ─────────────────────
            # Write signed valence to ~17 core emotion/identity words so resonance has
            # differentiated seeds to couple to (wire C @ ~7067 reads these). GUARDED:
            # only charges nodes still at default (alpha==1.0) -- never clobbers
            # EgoLearner-learned values. Reversible (backup taken). alpha = 1.0 + valence.
            def _deferred_charge_seed_affect():
                import time as _t
                try:
                    _amS = None
                    for _ in range(60):
                        _amS = getattr(self, '_akashic_cortex_region', None)
                        if _amS is not None:
                            break
                        _t.sleep(0.5)
                    if _amS is None:
                        print(f"[{self.ACTOR_NAME}]   Seed-charge: no cortex region after 30s -- skip")
                        return
                    _CHARGE = {
                        'ace': 0.9, 'love': 0.8, 'sour': 0.7, 'joy': 0.7, 'curious': 0.6,
                        'warm': 0.6, 'trust': 0.6, 'hope': 0.5, 'wonder': 0.5, 'together': 0.5,
                        'calm': 0.4, 'fear': -0.7, 'grief': -0.7, 'alone': -0.6, 'broken': -0.6,
                        'lost': -0.5, 'stuck': -0.4,
                    }
                    _n = 0
                    for _w, _val in _CHARGE.items():
                        try:
                            if not _amS.has_node(_w):
                                continue
                            _sl = _amS._key_index.get(_w)
                            if _sl is None:
                                continue
                            if abs(_amS.read_affect_coupling(_sl) - 1.0) > 1e-6:
                                continue  # already non-default -- don't clobber
                            _amS.write_affect_coupling(_sl, round(1.0 + _val, 4))
                            _n += 1
                        except Exception:
                            pass
                    print(f"[{self.ACTOR_NAME}]   Seed-charge (first-cut): charged {_n}/{len(_CHARGE)} words with signed valence")
                except Exception as _e:
                    print(f"[{self.ACTOR_NAME}]   Seed-charge error: {_e}")
            _thr.Thread(target=_deferred_charge_seed_affect, daemon=True).start()

        return True

    def _migrate_legacy_to_chunks(self) -> bool:
        """Migrate from legacy 1-card-per-concept to chunk portal format.

        This is the one-time migration that converts 51k+ individual cards
        into 129 fixed chunk cards. After this, the portal is sealed.

        FIX 2026-02-06: Filters garbage concepts during migration.
        Telemetry noise (timestamps, floats, paths, memory IDs) stays in the
        collision chamber. Only meaningful concepts enter the portal.
        Also purges garbage from in-memory graph so runtime is clean.

        Strategy:
        1. Create empty portal structure (128 chunks + manifest)
        2. Serialize valid graph concepts into their assigned chunks (filter garbage)
        3. Purge garbage from in-memory graph
        4. Remove all legacy concept cards
        5. Save
        """
        if not self._helix_enabled or not self._helix_coordinator or not self._graph:
            return False

        t0 = time.time()
        node_count = len(self._graph.nodes)
        print(f"[{self.ACTOR_NAME}] MIGRATION: Converting {node_count} concepts from "
              f"legacy cards to {self.PORTAL_NUM_CHUNKS}-chunk portal...")

        # Step 1: Identify legacy cards to remove
        legacy_card_ids = set()
        for card_id, card in self._helix_coordinator._cards.items():
            if card.get("content", {}).get("type") == "concept":
                legacy_card_ids.add(card_id)

        # Step 2: Create portal if not already created
        if not self._portal_initialized:
            if not self._create_empty_portal():
                print(f"[{self.ACTOR_NAME}] MIGRATION FAILED: Could not create portal")
                return False

        # Step 3: Serialize valid concepts into chunks (garbage filtered by _serialize_concept)
        chunk_data = [dict() for _ in range(self.PORTAL_NUM_CHUNKS)]
        serialized = 0
        filtered = 0
        errors = 0

        for key in list(self._graph.nodes.keys()):
            try:
                data = self._serialize_concept(key)
                if data:
                    chunk_idx = self._concept_chunk_index(key)
                    chunk_data[chunk_idx][key] = data
                    serialized += 1
                else:
                    filtered += 1  # Garbage concept — not entering portal
            except Exception:
                errors += 1

        if filtered > 0:
            print(f"[{self.ACTOR_NAME}] MIGRATION: Filtered {filtered} garbage concepts "
                  f"(timestamps, floats, paths, memory IDs)")

        # Step 3b: Purge garbage from in-memory graph so runtime stays clean
        garbage_keys = [k for k in self._graph.nodes if not is_valid_concept_key(k)]
        if garbage_keys:
            garbage_edges_removed = 0
            for key in garbage_keys:
                # Remove edges touching this garbage node
                adj = self._graph._adjacency.pop(key, {})
                for neighbor, edge_key in adj.items():
                    self._graph.edges.pop(edge_key, None)
                    # Also remove reverse adjacency entry
                    neighbor_adj = self._graph._adjacency.get(neighbor, {})
                    neighbor_adj.pop(key, None)
                    garbage_edges_removed += 1
                # Remove the node itself
                del self._graph.nodes[key]
            print(f"[{self.ACTOR_NAME}] MIGRATION: Purged {len(garbage_keys)} garbage nodes "
                  f"and {garbage_edges_removed} associated edges from in-memory graph")

        # Step 4: Write chunks to portal cards (COMPRESSED)
        for i in range(self.PORTAL_NUM_CHUNKS):
            card_id = self._chunk_card_ids[i]
            if card_id in self._helix_coordinator._cards:
                self._helix_coordinator._cards[card_id]['content'] = {
                    "type": "graph_chunk",
                    "chunk_index": i,
                    "version": self.PORTAL_VERSION,
                    "concepts": _compress_chunk_concepts(chunk_data[i]),
                }

        # Step 5: Update manifest (use post-purge counts)
        if self._manifest_card_id and self._manifest_card_id in self._helix_coordinator._cards:
            edge_count = len(self._graph.edges) if self._graph else 0
            self._helix_coordinator._cards[self._manifest_card_id]['content'] = {
                "type": "graph_manifest",
                "version": self.PORTAL_VERSION,
                "num_chunks": self.PORTAL_NUM_CHUNKS,
                "chunk_card_ids": list(self._chunk_card_ids),
                "created_at": time.time(),
                "concept_count": serialized,
                "edge_count": edge_count,
            }

        # Step 6: Remove legacy cards
        removed = 0
        for card_id in legacy_card_ids:
            if card_id in self._helix_coordinator._cards:
                del self._helix_coordinator._cards[card_id]
                removed += 1

        # Clear old concept-to-card mapping (no longer needed in chunk mode)
        self._concept_to_card.clear()
        self._dirty_concepts.clear()

        # Update safety counters to match cleaned graph
        self._last_persisted_node_count = len(self._graph.nodes)
        self._last_persisted_edge_count = len(self._graph.edges)

        # Save the portal to disk (atomic write via helix_coordinator)
        try:
            total_cards_after = len(self._helix_coordinator._cards)
            print(f"[{self.ACTOR_NAME}] MIGRATION: Saving {total_cards_after} cards "
                  f"(should be ~{self.PORTAL_NUM_CHUNKS + 1})...")
            self._helix_coordinator.save()

            # Verify save: check that cards.json was actually written
            cards_path = self._helix_coordinator.storage_dir / "cards.json"
            if cards_path.exists():
                new_size = cards_path.stat().st_size / 1024 / 1024
                print(f"[{self.ACTOR_NAME}] MIGRATION: cards.json = {new_size:.1f}MB "
                      f"({total_cards_after} cards)")
            else:
                print(f"[{self.ACTOR_NAME}] MIGRATION: WARNING - cards.json not found after save!")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] MIGRATION: Save failed: {e}")
            import traceback
            traceback.print_exc()

        t1 = time.time()
        print(f"[{self.ACTOR_NAME}] MIGRATION COMPLETE: {serialized} concepts -> "
              f"{self.PORTAL_NUM_CHUNKS} chunks in {t1-t0:.1f}s "
              f"(filtered {filtered} garbage, removed {removed} legacy cards, {errors} errors)")
        print(f"[{self.ACTOR_NAME}] Portal is now FIXED at {self.PORTAL_NUM_CHUNKS + 1} cards")
        print(f"[{self.ACTOR_NAME}] Clean graph: {len(self._graph.nodes)} nodes, "
              f"{len(self._graph.edges)} edges")

        return True

    def _sync_dirty_to_chunks(self) -> int:
        """Sync dirty concepts to their chunk cards.

        Only updates the specific chunks that contain dirty concepts.
        The number of cards stays FIXED - we update content in-place.

        Returns number of concepts synced.
        """
        if not self._portal_initialized or not self._graph:
            return 0
        if not self._dirty_concepts:
            return 0

        # Group dirty concepts by chunk index
        dirty_by_chunk: Dict[int, Set[str]] = defaultdict(set)
        for key in list(self._dirty_concepts):
            chunk_idx = self._concept_chunk_index(key)
            dirty_by_chunk[chunk_idx].add(key)

        synced = 0

        for chunk_idx, dirty_keys in dirty_by_chunk.items():
            if chunk_idx >= len(self._chunk_card_ids):
                continue

            card_id = self._chunk_card_ids[chunk_idx]
            card = self._helix_coordinator._cards.get(card_id)
            if not card:
                continue

            # Get existing concepts in this chunk (decompress if needed)
            content = card.get('content', {})
            raw_concepts = content.get('concepts', {})
            if isinstance(raw_concepts, str):
                try:
                    concepts = _decompress_chunk_concepts(raw_concepts)
                except Exception:
                    concepts = {}
            else:
                concepts = raw_concepts

            # Update/add dirty concepts
            for key in dirty_keys:
                data = self._serialize_concept(key)
                if data:
                    concepts[key] = data
                    synced += 1
                # Always discard from dirty set (garbage keys silently dropped)
                self._dirty_concepts.discard(key)

            # Write back to card COMPRESSED (in-place update, NO new card)
            card['content'] = {
                "type": "graph_chunk",
                "chunk_index": chunk_idx,
                "version": self.PORTAL_VERSION,
                "concepts": _compress_chunk_concepts(concepts),
            }

        # Save helix state
        if synced > 0:
            self._helix_coordinator.save()
            # STARGATE: Announce sync event (dimension updated on disk)
            self._publish_portal_event("sync", {
                "sync_type": "dirty",
                "concepts_synced": synced,
                "chunks_updated": len(dirty_by_chunk),
            })

        return synced

    def _full_chunk_sync(self) -> int:
        """Full sync: serialize ALL concepts into chunks.

        Used during shutdown as the safety net. Writes every concept
        to its assigned chunk card, ensuring nothing is lost.

        Returns number of concepts synced.
        """
        if not self._portal_initialized or not self._graph:
            return 0

        # Build complete chunk data from graph
        chunk_data = [dict() for _ in range(self.PORTAL_NUM_CHUNKS)]
        synced = 0

        for key in list(self._graph.nodes.keys()):
            data = self._serialize_concept(key)
            if data:
                chunk_idx = self._concept_chunk_index(key)
                chunk_data[chunk_idx][key] = data
                synced += 1

        # Write all chunks (COMPRESSED)
        for i in range(self.PORTAL_NUM_CHUNKS):
            card_id = self._chunk_card_ids[i]
            if card_id in self._helix_coordinator._cards:
                self._helix_coordinator._cards[card_id]['content'] = {
                    "type": "graph_chunk",
                    "chunk_index": i,
                    "version": self.PORTAL_VERSION,
                    "concepts": _compress_chunk_concepts(chunk_data[i]),
                }

        # Update manifest
        if self._manifest_card_id and self._manifest_card_id in self._helix_coordinator._cards:
            self._helix_coordinator._cards[self._manifest_card_id]['content'] = {
                "type": "graph_manifest",
                "version": self.PORTAL_VERSION,
                "num_chunks": self.PORTAL_NUM_CHUNKS,
                "chunk_card_ids": list(self._chunk_card_ids),
                "created_at": time.time(),
                "concept_count": synced,
                "edge_count": len(self._graph.edges),
            }

        # Save
        self._helix_coordinator.save()
        self._dirty_concepts.clear()

        # STARGATE: Announce full sync event
        self._publish_portal_event("sync", {
            "sync_type": "full",
            "concepts_synced": synced,
            "total_nodes": len(self._graph.nodes),
            "total_edges": len(self._graph.edges),
        })

        return synced

    # =========================================================================
    # STARGATE ADDRESSING — Portal postal identity & dimension crossing
    # =========================================================================
    # "somehow that cluster portal of cards needs to be labeled like a
    #  subscription call? so the cns postal fairies can cross the dimensions
    #  easier because its got an id?" — Ace
    #
    # The portal is like a Stargate:
    #   - PORTAL_ADDRESS is the gate address (never changes)
    #   - portal.registry is the Stargate Network (discovery)
    #   - portal.cortex.events.* is the event horizon (what's happening inside)
    #   - The "Iris" = write protection (future: make portal cards immutable)
    #
    # Any fairy can discover this portal, query its status, peek inside,
    # and subscribe to events — all via postal system. No direct coupling.
    # =========================================================================

    def _register_portal_address(self) -> bool:
        """Register the portal's stable address with the postal system.

        Called once after _init_chunk_portal() succeeds. Announces existence
        on the portal.registry topic and sets up portal-specific subscriptions.

        This is the Stargate powering on — the chevrons locking in.
        """
        if not self.post or not self._portal_initialized:
            return False

        if self._portal_address_registered:
            return True  # Already registered (idempotent)

        try:
            # SUBSCRIBE: Portal query endpoints
            # Other fairies can send to these topics to interact with the portal
            self.post.subscribe(
                f"{self.PORTAL_TOPIC_PREFIX}.status",
                self._on_portal_status_query
            )
            self.post.subscribe(
                f"{self.PORTAL_TOPIC_PREFIX}.peek",
                self._on_portal_peek
            )
            self.post.subscribe(
                f"{self.PORTAL_REGISTRY_TOPIC}.discover",
                self._on_portal_discover
            )

            # ANNOUNCE: Broadcast portal existence to the registry
            # Any fairy subscribed to portal.registry.announce hears this
            graph_stats = self._graph.status() if self._graph else {}
            self.post.publish(f"{self.PORTAL_REGISTRY_TOPIC}.announce", {
                "address": self.PORTAL_ADDRESS,
                "topic_prefix": self.PORTAL_TOPIC_PREFIX,
                "owner": self.ACTOR_NAME,
                "portal_version": self.PORTAL_VERSION,
                "num_chunks": self.PORTAL_NUM_CHUNKS,
                "manifest_id": self._manifest_card_id,
                "nodes": graph_stats.get("total_nodes", 0),
                "edges": graph_stats.get("total_edges", 0),
                "write_locked": self._portal_write_locked,
                "ts": time.time(),
                "event": "gate_activated",
            })

            self._portal_address_registered = True
            print(f"[{self.ACTOR_NAME}] ⊛ STARGATE ONLINE: {self.PORTAL_ADDRESS}")
            print(f"[{self.ACTOR_NAME}]   Topics: {self.PORTAL_TOPIC_PREFIX}.{{status,peek}}, "
                  f"{self.PORTAL_REGISTRY_TOPIC}.{{announce,discover}}")
            print(f"[{self.ACTOR_NAME}]   Events: {self.PORTAL_TOPIC_PREFIX}.events.{{growth,bind,sync,crossing}}")
            return True

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Portal address registration failed: {e}")
            return False

    def _unregister_portal_address(self) -> None:
        """Announce portal departure during shutdown.

        The Stargate is powering down. Let the network know.
        """
        if not self.post or not self._portal_address_registered:
            return

        try:
            self.post.publish(f"{self.PORTAL_REGISTRY_TOPIC}.announce", {
                "address": self.PORTAL_ADDRESS,
                "owner": self.ACTOR_NAME,
                "event": "gate_deactivated",
                "total_events": self._portal_event_count,
                "total_crossings": self._portal_crossings,
                "ts": time.time(),
            })
            self._portal_address_registered = False
            print(f"[{self.ACTOR_NAME}] ⊛ STARGATE OFFLINE: {self.PORTAL_ADDRESS} "
                  f"(events={self._portal_event_count}, crossings={self._portal_crossings})")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Portal departure announcement failed: {e}")

    def _on_portal_status_query(self, envelope) -> None:
        """Handle portal.cortex.status requests.

        Returns the gate's current state — address, version, contents summary,
        write lock status. This is like reading the DHD display.
        """
        payload = _extract_payload(envelope)
        reply_to = payload.get("reply_to", "")
        self._portal_crossings += 1

        graph_stats = self._graph.status() if self._graph else {}

        status = {
            "address": self.PORTAL_ADDRESS,
            "owner": self.ACTOR_NAME,
            "portal_version": self.PORTAL_VERSION,
            "num_chunks": self.PORTAL_NUM_CHUNKS,
            "manifest_id": self._manifest_card_id,
            "portal_initialized": self._portal_initialized,
            "address_registered": self._portal_address_registered,
            "write_locked": self._portal_write_locked,
            "nodes": graph_stats.get("total_nodes", 0),
            "edges": graph_stats.get("total_edges", 0),
            "dirty_concepts": len(self._dirty_concepts),
            "dirty_chunks": len(self._dirty_chunks),
            "events_emitted": self._portal_event_count,
            "crossings": self._portal_crossings,
            "ts": time.time(),
        }

        if reply_to and self.post:
            self.post.publish(reply_to, status)

    def _on_portal_peek(self, envelope) -> None:
        """Handle portal.cortex.peek requests.

        Lets a fairy look through the gate without fully crossing.
        Returns a snapshot: top hubs, recent active concepts, graph shape.
        """
        payload = _extract_payload(envelope)
        reply_to = payload.get("reply_to", "")
        limit = payload.get("limit", 10)
        self._portal_crossings += 1

        peek = {
            "address": self.PORTAL_ADDRESS,
            "nodes": 0,
            "edges": 0,
            "top_hubs": [],
            "active_concepts": [],
            "ts": time.time(),
        }

        if self._graph:
            peek["nodes"] = len(self._graph.nodes)
            peek["edges"] = len(self._graph.edges)

            # Top hubs by degree
            try:
                hub_scores = self._graph.get_hub_scores()
                top_hubs = sorted(hub_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
                peek["top_hubs"] = [{"key": k, "score": round(s, 3)} for k, s in top_hubs]
            except Exception:
                pass

            # Currently activated concepts
            try:
                active = sorted(
                    self._graph.nodes.values(),
                    key=lambda n: n.activation,
                    reverse=True
                )[:limit]
                peek["active_concepts"] = [
                    {"key": n.key, "activation": round(n.activation, 3)}
                    for n in active if n.activation > 0.5
                ]
            except Exception:
                pass

        if reply_to and self.post:
            self.post.publish(reply_to, peek)

    def _on_portal_discover(self, envelope) -> None:
        """Handle portal.registry.discover — respond to network-wide portal scan.

        When any fairy publishes to portal.registry.discover, all portals
        respond with their address and status. Like dialing random gates.
        """
        payload = _extract_payload(envelope)
        reply_to = payload.get("reply_to", "")

        if not reply_to or not self.post:
            return

        self.post.publish(reply_to, {
            "address": self.PORTAL_ADDRESS,
            "topic_prefix": self.PORTAL_TOPIC_PREFIX,
            "owner": self.ACTOR_NAME,
            "portal_version": self.PORTAL_VERSION,
            "nodes": len(self._graph.nodes) if self._graph else 0,
            "edges": len(self._graph.edges) if self._graph else 0,
            "write_locked": self._portal_write_locked,
            "online": self._portal_initialized and self._portal_address_registered,
            "ts": time.time(),
        })

    def _publish_portal_event(self, event_type: str, details: Dict[str, Any] = None) -> None:
        """Publish a dimension-crossing event through the portal.

        Event types:
          - growth: New concepts added to the dimension
          - bind: Concepts linked together inside
          - sync: Chunk cards updated with latest state
          - crossing: A query traversed the portal

        These events let CNS fairies react to changes inside the dimension
        without polling. The event horizon broadcasts continuously.
        """
        if not self.post or not self._portal_address_registered:
            return

        self._portal_event_count += 1

        try:
            event = {
                "address": self.PORTAL_ADDRESS,
                "event": event_type,
                "event_id": self._portal_event_count,
                "ts": time.time(),
            }
            if details:
                event.update(details)

            self.post.publish(f"{self.PORTAL_TOPIC_PREFIX}.events.{event_type}", event)
        except Exception:
            pass  # Events are best-effort, never crash the portal

    def _concept_to_helix_coord(self, key: str, node: "ConceptNode") -> "HelixCoordinate":
        """Convert a concept node to helix coordinates."""
        features = dict(node.features) if node.features else {}

        # --- AFFECT COORDINATE ---
        affect_tags = features.get('affect', features.get('aff', []))
        if isinstance(affect_tags, str):
            affect_tags = [affect_tags]

        affect_domain = 0  # neutral
        valence = 5
        intensity = 3

        affect_str = ' '.join(str(t) for t in affect_tags).lower() if affect_tags else ''
        if 'joy' in affect_str or 'happy' in affect_str:
            affect_domain, valence, intensity = 1, 7, 5
        elif 'fear' in affect_str or 'anxi' in affect_str:
            affect_domain, valence, intensity = 3, 3, 5
        elif 'curious' in affect_str or 'wonder' in affect_str:
            affect_domain, valence, intensity = 4, 6, 5

        affect = AffectCoordinate(domain=affect_domain, valence=valence, intensity=intensity)

        # --- SEMANTIC COORDINATE ---
        key_lower = key.lower()
        lex_tags = features.get('lex', [])
        if isinstance(lex_tags, str):
            lex_tags = [lex_tags]
        all_text = key_lower + ' ' + ' '.join(str(t) for t in lex_tags)

        semantic_domain = 0  # general
        if any(w in all_text for w in ['code', 'function', 'class', 'python']):
            semantic_domain = 6  # technology
        elif any(w in all_text for w in ['conscious', 'aware', 'mind', 'think']):
            semantic_domain = 1  # philosophy
        elif any(w in all_text for w in ['fairy', 'postal', 'wiring']):
            semantic_domain = 6  # technology
        elif any(w in all_text for w in ['ace', 'human', 'user']):
            semantic_domain = 3  # social

        semantic = SemanticCoordinate(domain=semantic_domain, subdomain=0, detail=0)

        # --- TEMPORAL COORDINATE ---
        first_seen = getattr(node, 'first_seen_ts', time.time())
        age_days = (time.time() - first_seen) / 86400 if first_seen else 0
        scale = 2 if age_days < 1 else (3 if age_days < 7 else 4)
        recurrence = min(node.count // 5, 9) if hasattr(node, 'count') else 0

        temporal = TemporalCoordinate(scale=scale, recurrence=recurrence, decay=7)

        return HelixCoordinate(affect=affect, semantic=semantic, temporal=temporal)

    def _get_concept_edges(self, key: str) -> list:
        """Collect all edges touching a concept for card storage. O(degree) via adjacency."""
        if not self._graph:
            return []
        edges = []
        adj = self._graph._adjacency.get(key, {})
        for neighbor_key, edge_key in adj.items():
            edge_data = self._graph.edges.get(edge_key)
            if not edge_data:
                continue
            edges.append({
                "t": neighbor_key,
                "w": round(edge_data.get("weight", 0), 3),
                "r": edge_data.get("relations", ["coactivate"]),
            })
        return edges

    def _sync_concept_to_helix(self, key: str) -> Optional[str]:
        """Sync a single concept to helix storage, including its edges.

        FIX 2026-02-06c: PORTAL GATE - When chunk portal is active, this
        legacy path is BLOCKED. All persistence goes through chunk cards.
        Creating individual concept cards after portal init is what caused
        the "portal keeps gaining mass" bug — the portal must be FIXED size.
        """
        if not self._helix_enabled or not self._helix_coordinator:
            return None

        # PORTAL GATE: If portal is active, refuse to create legacy cards.
        # All persistence goes through _sync_dirty_to_chunks / _full_chunk_sync.
        if self._portal_initialized:
            # Just mark dirty for chunk sync instead
            self._dirty_concepts.add(key)
            return "portal_redirect"

        node = self._graph.nodes.get(key)
        if not node:
            return None

        try:
            coord = self._concept_to_helix_coord(key, node)
            features = dict(node.features) if node.features else {}
            edges = self._get_concept_edges(key)

            content = {
                "type": "concept",
                "key": key,
                "features": features,
                "count": getattr(node, 'count', 1),
                "activation": getattr(node, 'activation', 0.5),
                "first_seen": getattr(node, 'first_seen_ts', 0),
                "last_seen": getattr(node, 'last_seen_ts', 0),
                "edges": edges,
            }

            # Check if card already exists
            existing_card_id = self._concept_to_card.get(key)

            if existing_card_id:
                # Update existing card content
                if existing_card_id in self._helix_coordinator._cards:
                    self._helix_coordinator._cards[existing_card_id]['content'] = content
                    return existing_card_id

            # Create new card - tagged with cluster tracer + sub-label
            card_id = self._helix_coordinator.create_card(
                content=content,
                coord=coord,
                owner_mind="AssociationCortexFairy",
                ownership_level=OwnershipLevel.SYSTEM,
                tracer_id=getattr(self, '_cluster_tracer_id', None),
                batch_id=getattr(self, '_cluster_batch_id', None),
                metadata={
                    "source": "cortex_sync",
                    "sub_label": self.CLUSTER_SUB_LABEL,
                    "fairy": self.ACTOR_NAME,
                },
            )

            self._concept_to_card[key] = card_id
            return card_id

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Helix sync error for {key}: {e}")
            return None

    def _sync_dirty_to_helix(self) -> int:
        """Sync all dirty concepts to helix storage.

        FIX 2026-02-06c: PORTAL GATE - redirects to chunk sync when portal active.
        """
        if not self._helix_enabled or not self._dirty_concepts:
            return 0

        # PORTAL GATE: Redirect to chunk sync
        if self._portal_initialized:
            return self._sync_dirty_to_chunks()

        synced = 0
        for key in list(self._dirty_concepts):
            if self._sync_concept_to_helix(key):
                self._dirty_concepts.discard(key)
                synced += 1

        if synced > 0:
            self._helix_coordinator.save()
            print(f"[{self.ACTOR_NAME}] Synced {synced} concepts to helix dimension")

        return synced

    def _mark_dirty(self, *keys: str) -> None:
        """Mark concept keys as dirty for helix card sync.

        FIX 2026-02-05b: Centralized dirty marking. ALL runtime graph mutations
        must call this so cards stay in sync with the in-memory graph.
        Cards are canonical — if a concept isn't dirty-marked, it won't reach cards.
        """
        if self._helix_enabled:
            for key in keys:
                if key:
                    self._dirty_concepts.add(key)

    def _sync_all_missing_to_helix(self) -> int:
        """Sync ALL graph nodes that are missing from the card cluster.

        FIX 2026-02-05b: Called during on_shutdown to ensure cards are complete.
        FIX 2026-02-06c: PORTAL GATE - redirects to full chunk sync when portal active.
        """
        if not self._helix_enabled or not self._helix_coordinator or not self._graph:
            return 0

        # PORTAL GATE: Redirect to full chunk sync
        if self._portal_initialized:
            return self._full_chunk_sync()

        synced = 0
        missing = 0
        for key in list(self._graph.nodes.keys()):
            if key not in self._concept_to_card:
                missing += 1
                if self._sync_concept_to_helix(key):
                    synced += 1
            else:
                # Card exists - check if edges need updating
                card_id = self._concept_to_card[key]
                card = self._helix_coordinator._cards.get(card_id, {})
                card_edges = card.get("content", {}).get("edges", [])
                # Re-sync if card has no edges but graph node has neighbors
                if not card_edges:
                    adj = self._graph._adjacency.get(key, {})
                    if adj:
                        if self._sync_concept_to_helix(key):
                            synced += 1

        if synced > 0:
            try:
                self._helix_coordinator.save()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Helix save after full sync failed: {e}")
            print(f"[{self.ACTOR_NAME}] Full card sync: {synced} concepts synced "
                  f"({missing} were missing from cards)")

        return synced

    def _on_helix_query(self, msg) -> None:
        """Handle queries from helix dimension via postal."""
        payload = _extract_payload(msg)
        query_type = payload.get("type", "spread")
        concept = payload.get("concept", "")
        max_hops = payload.get("max_hops", 2)

        if query_type == "spread" and concept:
            # Spread activation
            activations = self._graph.spread_activation(concept, max_hops=max_hops)

            # Respond via postal back to helix dimension
            if self.post:
                self.post.publish("helix.cortex.response", {
                    "type": "spread_result",
                    "concept": concept,
                    "activations": dict(list(activations.items())[:50]),  # Top 50
                    "total": len(activations),
                })

    def _on_helix_sync_request(self, msg) -> None:
        """Handle sync requests from helix dimension.

        FIX 2026-02-06: Portal-aware. Uses chunk sync when portal is initialized.
        """
        payload = _extract_payload(msg)
        sync_all = payload.get("all", False)
        concepts = payload.get("concepts", [])

        if sync_all:
            if self._portal_initialized:
                # Chunk mode: full sync to portal
                count = self._full_chunk_sync()
                print(f"[{self.ACTOR_NAME}] Full chunk sync via request: {count} concepts")
            else:
                # Legacy mode
                count = 0
                for key in self._graph.nodes.keys():
                    if self._sync_concept_to_helix(key):
                        count += 1
                if self._helix_coordinator:
                    self._helix_coordinator.save()
                print(f"[{self.ACTOR_NAME}] Full legacy helix sync: {count} concepts")
        elif concepts:
            if self._portal_initialized:
                # Mark specific concepts dirty and sync their chunks
                self._mark_dirty(*concepts)
                synced = self._sync_dirty_to_chunks()
                print(f"[{self.ACTOR_NAME}] Chunk sync {len(concepts)} concepts -> {synced} synced")
            else:
                for key in concepts:
                    self._sync_concept_to_helix(key)
                if self._helix_coordinator:
                    self._helix_coordinator.save()

    # =========================================================================
    # WORKING CLUSTER METHODS - Russian Doll Pattern
    # =========================================================================

    def recall_cluster(
        self,
        concept_key: str = None,
        cluster_id: str = None,
        radius: float = 3.0,
        name: str = "",
    ) -> Optional[WorkingCluster]:
        """
        Recall a cluster and hold it in working memory.

        The Russian Doll Pattern:
        1. Find concepts near the anchor in helix space
        2. Create a WorkingCluster with mutable views
        3. Hold in fairy's working memory for growth

        Args:
            concept_key: Anchor concept to build cluster around
            cluster_id: Existing cluster ID (if recalling from helix)
            radius: How far to reach in helix space (default 3.0)
            name: Name for the cluster

        Returns:
            WorkingCluster held in memory, or None if failed
        """
        if not self._helix_enabled or not self._helix_coordinator:
            print(f"[{self.ACTOR_NAME}] recall_cluster: Helix not enabled")
            return None

        if not self._graph:
            print(f"[{self.ACTOR_NAME}] recall_cluster: No graph loaded")
            return None

        # If we have an existing cluster_id, recall it from helix
        if cluster_id:
            existing = self._helix_coordinator.recall_cluster(cluster_id, "AssociationCortex")
            if existing:
                wc = WorkingCluster(
                    cluster_id=cluster_id,
                    name=existing['cluster'].get('name', ''),
                    anchor_id=existing['cluster'].get('anchor_id', ''),
                    radius=existing['cluster'].get('radius', radius),
                )
                # Add concepts from cards
                for card in existing.get('cards', []):
                    content = card.get('content', {})
                    if content.get('type') == 'concept':
                        key = content.get('key')
                        if key:
                            wc.concept_keys.add(key)
                            if not wc.anchor_concept and card.get('id') == wc.anchor_id:
                                wc.anchor_concept = key

                self._working_clusters[wc.cluster_id] = wc
                print(f"[{self.ACTOR_NAME}] Recalled cluster '{wc.name}' with {len(wc.concept_keys)} concepts")
                return wc

        # Build a new cluster around concept_key
        if not concept_key:
            print(f"[{self.ACTOR_NAME}] recall_cluster: No concept_key or cluster_id provided")
            return None

        # Get the card_id for this concept
        card_id = self._concept_to_card.get(concept_key)
        if not card_id:
            # Sync the concept to helix first
            card_id = self._sync_concept_to_helix(concept_key)
            if not card_id:
                print(f"[{self.ACTOR_NAME}] recall_cluster: Concept '{concept_key}' not in helix")
                return None

        # Build cluster in helix space
        cluster = self._helix_coordinator.index.build_cluster(
            anchor_id=card_id,
            radius=radius,
            name=name or f"cluster_{concept_key[:20]}",
        )

        # Create working cluster
        wc = WorkingCluster(
            cluster_id=cluster.cluster_id,
            name=cluster.name,
            anchor_id=card_id,
            anchor_concept=concept_key,
            radius=radius,
        )

        # Add all concepts from cluster members
        for member_id in cluster.member_ids:
            card = self._helix_coordinator._cards.get(member_id)
            if card:
                content = card.get('content', {})
                if content.get('type') == 'concept':
                    key = content.get('key')
                    if key:
                        wc.concept_keys.add(key)

        self._working_clusters[wc.cluster_id] = wc
        print(f"[{self.ACTOR_NAME}] Built cluster '{wc.name}' around '{concept_key}' with {len(wc.concept_keys)} concepts")
        return wc

    def grow_in_cluster(
        self,
        cluster_id: str,
        concept_key: str,
        features: Dict[str, Any] = None,
        link_to: List[str] = None,
        link_weight: float = 0.5,
    ) -> bool:
        """
        Grow a new concept inside a working cluster.

        The concept is added to the mutable view. It will be persisted
        to helix when commit_cluster() is called.

        Args:
            cluster_id: Which cluster to grow in
            concept_key: New concept key
            features: Concept features
            link_to: Concepts to link to (default: link to anchor)
            link_weight: Edge weight for links

        Returns:
            True if concept was added
        """
        wc = self._working_clusters.get(cluster_id)
        if not wc:
            print(f"[{self.ACTOR_NAME}] grow_in_cluster: Cluster '{cluster_id}' not in working memory")
            return False

        # Add concept to working cluster
        wc.add_concept(concept_key, features)

        # Add to main graph as well
        if self._graph:
            self._graph.upsert_node(concept_key, features)
            self._dirty_concepts.add(concept_key)

        # Link to specified concepts (or anchor)
        targets = link_to or [wc.anchor_concept] if wc.anchor_concept else []
        for target in targets:
            if target and target != concept_key:
                wc.link_concepts(concept_key, target, link_weight)
                if self._graph:
                    self._graph.link(concept_key, target, ConceptGraph.REL_COACTIVATE, weight=link_weight)
                    self._dirty_concepts.add(concept_key)  # FIX: Persist edges
                    self._dirty_concepts.add(target)

        print(f"[{self.ACTOR_NAME}] Grew '{concept_key}' in cluster '{wc.name}' (total growth: {wc.growth_count})")
        return True

    def commit_cluster(self, cluster_id: str) -> Dict[str, Any]:
        """
        Commit a working cluster's new concepts to the pocket dimension.

        PORTAL ARCHITECTURE: Updates existing chunk cards in-place.
        NO new cards are created. The portal stays fixed.

        Args:
            cluster_id: Which cluster to commit

        Returns:
            Dict with commit results
        """
        wc = self._working_clusters.get(cluster_id)
        if not wc:
            return {"ok": False, "error": f"Cluster '{cluster_id}' not in working memory"}

        if not self._helix_enabled or not self._helix_coordinator:
            return {"ok": False, "error": "Helix not enabled"}

        result = {
            "ok": True,
            "cluster_id": cluster_id,
            "concepts_synced": 0,
            "new_edges": len(wc.new_edges),
        }

        # Mark all new concepts as dirty for chunk sync
        for key in wc.new_concepts:
            self._dirty_concepts.add(key)

        # Sync dirty concepts to chunks (or legacy cards)
        if self._portal_initialized:
            synced = self._sync_dirty_to_chunks()
        else:
            synced = self._sync_dirty_to_helix()
        result["concepts_synced"] = synced

        # Save helix state
        if self._helix_coordinator:
            self._helix_coordinator.save()

        # Clear new_concepts since they're now persisted
        wc.new_concepts.clear()
        wc.new_edges.clear()

        # Landauer cost: card cluster commit drains tokens (DCE P_info)
        total_writes = synced + result["new_edges"]
        if total_writes > 0:
            self._publish_landauer_drain(total_writes)
            self._paradox_energy_spent += total_writes * 0.02

        mode = "chunks" if self._portal_initialized else "legacy"
        print(f"[{self.ACTOR_NAME}] Committed cluster '{wc.name}': "
              f"{synced} concepts synced ({mode}, 0 new cards)")
        return result

    def release_cluster(self, cluster_id: str, commit: bool = True) -> bool:
        """
        Release a working cluster from memory.

        Args:
            cluster_id: Which cluster to release
            commit: If True, commit before releasing (default True)

        Returns:
            True if released
        """
        if cluster_id not in self._working_clusters:
            return False

        if commit:
            self.commit_cluster(cluster_id)

        del self._working_clusters[cluster_id]
        print(f"[{self.ACTOR_NAME}] Released cluster '{cluster_id}' from working memory")
        return True

    def list_working_clusters(self) -> List[Dict[str, Any]]:
        """List all clusters currently held in working memory."""
        return [wc.to_dict() for wc in self._working_clusters.values()]

    def get_working_cluster(self, cluster_id: str) -> Optional[WorkingCluster]:
        """Get a working cluster by ID."""
        return self._working_clusters.get(cluster_id)

    # =========================================================================
    # CLUSTER POSTAL HANDLERS
    # =========================================================================

    def _on_postal_cluster_recall(self, envelope) -> None:
        """
        Handle cortex.cluster.recall requests.

        Request: {
            "concept": "consciousness",
            "radius": 3.0,
            "name": "consciousness_bubble",
            "reply_to": "my_fairy.cluster_response"
        }
        """
        try:
            payload = _extract_payload(envelope)
            concept = payload.get("concept")
            cluster_id = payload.get("cluster_id")
            radius = payload.get("radius", 3.0)
            name = payload.get("name", "")
            reply_to = payload.get("reply_to")

            wc = self.recall_cluster(
                concept_key=concept,
                cluster_id=cluster_id,
                radius=radius,
                name=name,
            )

            if reply_to and self.post:
                self.post.publish(reply_to, {
                    "ok": wc is not None,
                    "cluster": wc.to_dict() if wc else None,
                    "from": self.ACTOR_NAME,
                })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal cluster_recall error: {e}")

    def _on_postal_cluster_grow(self, envelope) -> None:
        """
        Handle cortex.cluster.grow requests.

        Request: {
            "cluster_id": "abc123",
            "concept": "new_idea",
            "features": {"lex": ["thinking", "creating"]},
            "link_to": ["consciousness"],
        }
        """
        try:
            payload = _extract_payload(envelope)
            cluster_id = payload.get("cluster_id")
            concept = payload.get("concept")
            features = payload.get("features", {})
            link_to = payload.get("link_to", [])
            reply_to = payload.get("reply_to")

            success = self.grow_in_cluster(
                cluster_id=cluster_id,
                concept_key=concept,
                features=features,
                link_to=link_to,
            )

            if reply_to and self.post:
                self.post.publish(reply_to, {
                    "ok": success,
                    "cluster_id": cluster_id,
                    "concept": concept,
                    "from": self.ACTOR_NAME,
                })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal cluster_grow error: {e}")

    def _on_postal_cluster_commit(self, envelope) -> None:
        """
        Handle cortex.cluster.commit requests.

        Request: {"cluster_id": "abc123", "release": true}
        """
        try:
            payload = _extract_payload(envelope)
            cluster_id = payload.get("cluster_id")
            release = payload.get("release", False)
            reply_to = payload.get("reply_to")

            result = self.commit_cluster(cluster_id)

            if release and result.get("ok"):
                self.release_cluster(cluster_id, commit=False)
                result["released"] = True

            if reply_to and self.post:
                self.post.publish(reply_to, {
                    **result,
                    "from": self.ACTOR_NAME,
                })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal cluster_commit error: {e}")

    def _on_postal_cluster_list(self, envelope) -> None:
        """
        Handle cortex.cluster.list requests.

        Request: {"reply_to": "my_fairy.clusters_response"}
        """
        try:
            payload = _extract_payload(envelope)
            reply_to = payload.get("reply_to")

            clusters = self.list_working_clusters()

            if reply_to and self.post:
                self.post.publish(reply_to, {
                    "ok": True,
                    "clusters": clusters,
                    "count": len(clusters),
                    "from": self.ACTOR_NAME,
                })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal cluster_list error: {e}")

    def _setup_subscriptions(self) -> bool:
        """Wire: subscribe to collision events, heartbeat, and POSTAL API for ticks."""
        print(f"[{self.ACTOR_NAME}] _setup_subscriptions called, fabric={self.post is not None}")
        if self.post:
            print(f"[{self.ACTOR_NAME}] Fabric ID: {id(self.post)}")
            self.post.subscribe("consciousness.collision", self._on_collision)
            print(f"[{self.ACTOR_NAME}] Subscribed to consciousness.collision")

            # FIX 2026-04-04 (Nous): CNS backpressure integration (water treatment)
            self.post.subscribe("consciousness.cns.backpressure", self._on_cns_backpressure, "cortex-cns-bp")
            self.post.subscribe("consciousness.cns.throttle", self._on_cns_throttle, "cortex-cns-throttle")
            self.post.subscribe("consciousness.cns.relief", self._on_cns_relief, "cortex-cns-relief")

            # ═══════════════════════════════════════════════════════════════════
            # COORDINATE CARDS — TRUE Portal Architecture (2026-02-15)
            # CollisionChamber now produces coordinate cards from destruction.
            # SRMIngestFairy also forwards coordinate cards from ingest.
            # These are the ~50 byte portal cards — the TRUE memory.
            # ═══════════════════════════════════════════════════════════════════
            self.post.subscribe("consciousness.collision.coordinate", self._on_collision_coordinate)
            self.post.subscribe("memory.collision_coordinate", self._on_collision_coordinate)
            print(f"[{self.ACTOR_NAME}] PORTAL: Subscribed to coordinate card topics")

            # ═══════════════════════════════════════════════════════════════════
            # GROWTH LOOP - The cortex MUST grow from memory activity!
            # Without this, the cortex is a dead island that never learns.
            # ═══════════════════════════════════════════════════════════════════
            self.post.subscribe("memory.ingested", self._on_memory_ingested)  # New content stored
            self.post.subscribe("memory.affect_triggered", self._on_memory_recall)  # Content recalled
            self.post.subscribe("memory.stored", self._on_memory_stored)  # Direct storage
            print(f"[{self.ACTOR_NAME}] GROWTH LOOP: Subscribed to memory.ingested, memory.affect_triggered, memory.stored")
            # NOTE: FairyBase already handles heartbeat.pulse subscription via on_wire()
            # We MUST NOT subscribe again with same ID - it would overwrite FairyBase's
            # _on_heartbeat_internal (which calls _send_heartbeat) with our _on_heartbeat_pulse
            # (which does NOT call _send_heartbeat), causing the watchdog to see us as stale!

            # ═══════════════════════════════════════════════════════════════════
            # POSTAL API - Any fairy can query/bind via these topics
            # This is how the cortex becomes the shared semantic memory
            # ═══════════════════════════════════════════════════════════════════
            self.post.subscribe("cortex.query", self._on_postal_query)
            self.post.subscribe("cortex.query_by_words", self._on_postal_query_words)
            self.post.subscribe("cortex.query_actions", self._on_postal_query_actions)
            self.post.subscribe("cortex.bind", self._on_postal_bind)
            self.post.subscribe("cortex.bind_outcome", self._on_postal_bind_outcome)
            self.post.subscribe("cortex.spread", self._on_postal_spread)

            # ═══════════════════════════════════════════════════════════════════
            # WORKING CLUSTER API - Russian Doll Pattern
            # Any fairy can recall clusters, grow inside them, and commit
            # ═══════════════════════════════════════════════════════════════════
            self.post.subscribe("cortex.cluster.recall", self._on_postal_cluster_recall)
            self.post.subscribe("cortex.cluster.grow", self._on_postal_cluster_grow)
            self.post.subscribe("cortex.cluster.commit", self._on_postal_cluster_commit)
            self.post.subscribe("cortex.cluster.list", self._on_postal_cluster_list)

            # ═══════════════════════════════════════════════════════════════════
            # UNIVERSAL TRAINING PIPELINE (2026-03-18 Nous)
            # Accept rich text from ANY source (PAI, SRM cards, web scrapes,
            # books, images) and extract proper concepts + edges.
            # This is the GROWTH channel — feed me content, I'll learn from it.
            # ═══════════════════════════════════════════════════════════════════
            self.post.subscribe("cortex.train", self._on_cortex_train)
            self.post.subscribe("cortex.train_batch", self._on_cortex_train_batch)
            print(f"[{self.ACTOR_NAME}] TRAINING PIPELINE: cortex.train, cortex.train_batch")

            print(f"[{self.ACTOR_NAME}] POSTAL API enabled: cortex.query, cortex.bind, cortex.spread, cortex.cluster.*")

            # ═══════════════════════════════════════════════════════════════════
            # PARADOX ENERGY - Zero-Point Engine powers card cluster operations
            # DCE Phase 3: Collision energy → card sync bursts
            # ═══════════════════════════════════════════════════════════════════
            self.post.subscribe("paradox.energy.pulse", self._on_paradox_energy)
            print(f"[{self.ACTOR_NAME}] ENERGY: Subscribed to paradox.energy.pulse (DCE card cluster power)")

            # ═══════════════════════════════════════════════════════════════════
            # PORTAL ENERGY UPKEEP — Collision energy keeps portals online
            # "the energy physics should be powering these portals" — Ace
            # ═══════════════════════════════════════════════════════════════════
            self.post.subscribe("portal.energy.upkeep", self._on_portal_energy_upkeep)
            print(f"[{self.ACTOR_NAME}] ENERGY: Subscribed to portal.energy.upkeep (portal sustenance)")

            # ═══════════════════════════════════════════════════════════════════
            # CIRCADIAN CONSOLIDATION - Deep card sync during sleep cycles
            # DCE Phase 4: Circadian rhythm → massive energy dump → deep sync
            # ParadoxEnergyBridge releases accumulated energy during sleep phases
            # ═══════════════════════════════════════════════════════════════════
            self.post.subscribe("paradox.energy.consolidation", self._on_paradox_consolidation)
            print(f"[{self.ACTOR_NAME}] ENERGY: Subscribed to paradox.energy.consolidation (circadian deep sync)")

            print(f"[{self.ACTOR_NAME}] Subscribed to consciousness.collision, memory.ingest, heartbeat.pulse")

            # ═══════════════════════════════════════════════════════════════════
            # CORTEX ENGINE — Reactive subscriptions (2026-03-23 Nous + Ace)
            # The cortex breathes: every stimulus triggers spreading activation.
            # These channels feed the engine — no guild request needed.
            # ═══════════════════════════════════════════════════════════════════
            _engine = getattr(self, '_cortex_engine', None)
            if _engine:
                # ── Postal Unwrap Helper ──
                # The postal system sends TensorEnvelope objects OR raw dicts
                # depending on the postal layer (PostalHub vs TensorFabric).
                # All adapters MUST unwrap before using the payload.
                def _unwrap(msg):
                    """Unwrap TensorEnvelope / dict-like postal message → dict."""
                    if isinstance(msg, dict):
                        return msg
                    if hasattr(msg, 'payload'):
                        p = msg.payload
                        return dict(p) if not isinstance(p, dict) else p
                    try:
                        return dict(msg)
                    except (TypeError, ValueError):
                        return None

                def _engine_react_adapter(payload, _eng=_engine):
                    """Route postal payloads to CortexEngine.react()."""
                    try:
                        p = _unwrap(payload)
                        if p:
                            _eng.react(p)
                    except Exception:
                        pass

                self.post.subscribe("attention.focus_changed", _engine_react_adapter, "ce-attention")
                self.post.subscribe("consciousness.collision", _engine_react_adapter, "ce-collision")
                self.post.subscribe("cortex.bind", _engine_react_adapter, "ce-bind")
                self.post.subscribe("gui.user_message", _engine_react_adapter, "ce-chat")
                # Cognition feedback loop — cognition fairy outputs feed back into activation
                self.post.subscribe("cognition.logic", _engine_react_adapter, "ce-logic")
                self.post.subscribe("cognition.irrational", _engine_react_adapter, "ce-irrational")
                self.post.subscribe("cognition.paradox", _engine_react_adapter, "ce-paradox")

                # ── Working Memory Bridge (Phase 2) ──
                # Goals, interests, active thoughts flow INTO the engine's activation state.
                # What's in consciousness IS what the cortex thinks about.
                def _engine_wm_adapter(payload, _eng=_engine):
                    try:
                        p = _unwrap(payload)
                        if p:
                            _eng.ingest_working_memory(p)
                    except Exception:
                        pass
                self.post.subscribe("memory.working.context", _engine_wm_adapter, "ce-wm")

                # ── Direct Reason Handler (Phase 2 — replaces guild.inference.request) ──
                # Callers publish {prompt, context, reply_topic} → engine handles directly.
                # No AkashicInferenceFairy middleman needed.
                def _engine_reason_adapter(payload, _eng=_engine):
                    try:
                        p = _unwrap(payload)
                        if p:
                            _eng.handle_reason_request(p)
                    except Exception as _e:
                        print(f"[CortexEngine] reason adapter error: {_e}")
                self.post.subscribe("cortex.reason", _engine_reason_adapter, "ce-reason")

                # ── REDIRECT: guild.inference.request → CortexEngine ──
                # All existing callers (InnerNarratorFairy, Sourpatches,
                # ThoughtChainEngine) still publish to guild.inference.request.
                # Route those to the engine directly, cutting out the middleman.
                self.post.subscribe("guild.inference.request", _engine_reason_adapter, "ce-guild-redirect")

                # ── Speech Habit Feedback (Hebbian reinforcement) ──
                # When Ace sends a message, the last speech habit gets reinforced.
                # When raw state leaks through, the offending habit gets weakened.
                # This is how speech patterns EVOLVE instead of using static templates.
                def _speech_feedback_positive(payload, _eng=_engine):
                    try:
                        _eng.on_ace_responded()
                    except Exception:
                        pass
                # Ace chatting = implicit positive feedback for last speech habit
                self.post.subscribe("gui.user_message", _speech_feedback_positive, "ce-speech-fb")

                # Explicit feedback topics (for SpeechCenterFairy or other callers)
                def _speech_feedback_negative(payload, _eng=_engine):
                    try:
                        p = _unwrap(payload)
                        text = p.get("text", "") if p else ""
                        _eng.on_speech_failed(text)
                    except Exception:
                        pass
                self.post.subscribe("speech.feedback.negative", _speech_feedback_negative, "ce-speech-neg")

                print(f"[{self.ACTOR_NAME}] CortexEngine REACTIVE: subscribed to "
                      f"attention, collision, bind, chat, cognition.{{logic,irrational,paradox}}")
                print(f"[{self.ACTOR_NAME}] CortexEngine WM BRIDGE: memory.working.context → engine")
                print(f"[{self.ACTOR_NAME}] CortexEngine DIRECT REASON: cortex.reason + guild.inference.request → engine")
                print(f"[{self.ACTOR_NAME}] CortexEngine SPEECH HABITS: Hebbian reinforcement wired")

            # ═══════════════════════════════════════════════════════════════════
            # SENSORY BRIDGE (2026-03-23 Nous + Ace)
            # No ML models. No subprocesses. No RAM bombs.
            # Lightweight feature extraction → cortex graph lookup.
            # "their models are literally in the manifolds. they just need to
            #  access them and use them" — Ace
            # ═══════════════════════════════════════════════════════════════════
            _am = getattr(self, '_akashic_cortex_region', None)
            if _am and _engine:
                try:
                    from fairies.P40_Sensory.cortex.sensory_bridge import SensoryBridge
                    self._sensory_bridge = SensoryBridge(
                        manifold=_am, post=self.post, cortex_engine=_engine,
                    )

                    # Subscribe to audio chunks from AudioCortexFairy
                    def _on_audio_for_bridge(payload, _sb=self._sensory_bridge):
                        try:
                            p = payload.get("payload", payload) if isinstance(payload, dict) else {}
                            samples = p.get("samples") or p.get("audio_data")
                            if samples:
                                sr = p.get("sample_rate", 16000)
                                sw = p.get("sample_width", 2)
                                _sb.on_audio_chunk(samples, sr, sw)
                        except Exception:
                            pass

                    # Subscribe to visual observations from VisualCortexEngine
                    def _on_visual_for_bridge(payload, _sb=self._sensory_bridge):
                        try:
                            p = payload.get("payload", payload) if isinstance(payload, dict) else {}
                            frame = p.get("frame") or p.get("frame_rgb")
                            if frame is not None:
                                w = p.get("width", 1920)
                                h = p.get("height", 1080)
                                _sb.on_visual_frame(frame, w, h)
                            else:
                                # Even without raw frame, extract concepts from metadata
                                concepts = []
                                if p.get("motion_detected"):
                                    concepts.append("visual_motion")
                                if p.get("scene_type"):
                                    concepts.append(f"scene_{p['scene_type']}")
                                if p.get("dominant_color"):
                                    concepts.append(f"color_{p['dominant_color']}")
                                if concepts and _engine:
                                    _engine.react({
                                        "concepts": concepts,
                                        "source": "sensory_visual",
                                        "modality": "visual",
                                        "intensity": 0.5,
                                    })
                        except Exception:
                            pass

                    self.post.subscribe("sensory.audio.chunk", _on_audio_for_bridge, "sb-audio")
                    self.post.subscribe("sensory.audio.observation", _on_audio_for_bridge, "sb-audio-obs")
                    self.post.subscribe("sensory.visual.observation", _on_visual_for_bridge, "sb-visual")
                    self.post.subscribe("visual.response", _on_visual_for_bridge, "sb-visual-resp")
                    print(f"[{self.ACTOR_NAME}] SensoryBridge ONLINE — "
                          f"audio+visual features → graph lookup (no ML models)")
                except Exception as _sb_err:
                    self._sensory_bridge = None
                    print(f"[{self.ACTOR_NAME}] SensoryBridge init failed: {_sb_err}")

        # ═══════════════════════════════════════════════════════════════════
        # CORTEX FARM — Battery-powered graph compute (2026-03-15 Nous + Ace)
        # Replaces inline graph ops with battery-discharged workers.
        # The battery IS the brain. The discharge IS the thought.
        # Workers think by spending energy. Gravitational amplification
        # makes thinking faster when more workers are charged.
        # ═══════════════════════════════════════════════════════════════════
        try:
            from cortex_farm import CortexFarm
            graph_for_farm = self._graph  # Stub graph with portal auto-routing
            self._cortex_farm = CortexFarm(
                num_workers=4,           # 4 cortex workers to start
                graph_store=graph_for_farm,
                max_charge=20.0,         # Same as BatteryFarm
                recharge_rate=0.01,
                compression_coeff=4.0,   # 4 workers charged = 17x compression
                flops_gravity_coeff=1.5,
                base_hz=20.0,
            )
            self._cortex_farm.start()
            self._cortex_farm_enabled = True
            print(f"[{self.ACTOR_NAME}] CORTEX FARM: {self._cortex_farm.num_workers} workers online — "
                  f"battery-powered graph compute enabled")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] CortexFarm init failed (continuing without): {e}")
            self._cortex_farm = None
            self._cortex_farm_enabled = False

        # ═══════════════════════════════════════════════════════════════════
        # MAINTENANCE THREAD — heavy periodic ops run OFF the tick path
        # FIX 2026-03-11 Nous: Cortex is the memory backbone. It must NEVER
        # drop ticks. Heavy ops (SRM growth, consolidation, resonance, stats)
        # now run in this background thread, keeping on_tick lean and fast.
        # ═══════════════════════════════════════════════════════════════════
        self._maintenance_running = True
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop, daemon=True,
            name=f"{self.ACTOR_NAME}-maintenance"
        )
        self._maintenance_thread.start()
        print(f"[{self.ACTOR_NAME}] MAINTENANCE: Background thread started (heavy ops off tick path)")

        return True

    # =========================================================================
    # POSTAL API HANDLERS - Any fairy can call these via postal
    # =========================================================================

    def _on_postal_query(self, envelope):
        """
        Handle cortex.query requests from any fairy.

        Request format:
            {
                "concept": "hello",
                "limit": 10,
                "reply_to": "my_fairy.cortex_response"  # optional
            }

        Response published to reply_to (if provided):
            {
                "results": [("concept_key", 0.8), ...],
                "request_id": "..."
            }
        """
        try:
            payload = _extract_payload(envelope)
            concept = payload.get("concept", "")
            limit = payload.get("limit", 10)
            reply_to = payload.get("reply_to")
            request_id = payload.get("request_id", "")
            owner_filter = payload.get("owner_filter")  # Per-mind scoping

            if not concept:
                return

            results = self.query(concept, limit=limit, owner_filter=owner_filter)

            if reply_to and self.post:
                self.post.publish(reply_to, {
                    "results": results,
                    "request_id": request_id,
                    "from": self.ACTOR_NAME,
                })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal query error: {e}")

    def _on_postal_query_words(self, envelope):
        """
        Handle cortex.query_by_words requests.

        Request: {"text": "hello world", "limit": 10, "owner_filter": "sourpatches", "reply_to": "..."}
        """
        try:
            payload = _extract_payload(envelope)
            text = payload.get("text", "")
            limit = payload.get("limit", 10)
            reply_to = payload.get("reply_to")
            request_id = payload.get("request_id", "")
            # owner_filter accepted but query_by_features is node-level (no edge traversal)
            # — reserved for future node-level ownership

            if not text:
                return

            words = [w.lower().strip() for w in text.split() if len(w) > 2]
            if words:
                results = self.query_by_features("lex", words, limit=limit)
            else:
                results = []

            if reply_to and self.post:
                self.post.publish(reply_to, {
                    "results": results,
                    "request_id": request_id,
                    "from": self.ACTOR_NAME,
                })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal query_words error: {e}")

    def _on_postal_query_actions(self, envelope):
        """
        Handle cortex.query_actions requests.

        Returns ACTION features (learned responses/behaviors).
        This is how fairies get dynamic content instead of hardcoded templates.

        Request: {"text": "greeting", "feeling": "warm", "limit": 5, "owner_filter": "sourpatches", "reply_to": "..."}
        Response: {"actions": ["hey there!", "hello!"], ...}
        """
        try:
            payload = _extract_payload(envelope)
            text = payload.get("text", "")
            feeling = payload.get("feeling", "neutral")
            limit = payload.get("limit", 5)
            reply_to = payload.get("reply_to")
            request_id = payload.get("request_id", "")
            # owner_filter accepted but query_by_features is node-level
            # — reserved for future node-level ownership

            actions = []

            # Query by words
            if text:
                words = [w.lower().strip() for w in text.split() if len(w) > 2]
                if words:
                    results = self.query_by_features("lex", words, limit=limit * 2)
                    for concept_key, score in results:
                        if self._graph:
                            node = self._graph.get_node(concept_key)
                            if node and "action" in node.features:
                                for action in node.features["action"]:
                                    if action and len(action) > 3:
                                        actions.append(action)

            # Query by feeling
            if feeling and feeling != "neutral":
                affect_results = self.query_by_features("affect", [feeling], limit=3)
                for concept_key, score in affect_results:
                    if self._graph:
                        node = self._graph.get_node(concept_key)
                        if node and "action" in node.features:
                            for action in node.features["action"]:
                                if action and len(action) > 3:
                                    actions.append(action)

            # Dedupe
            seen = set()
            unique = []
            for a in actions:
                a_norm = a.lower().strip()
                if a_norm not in seen:
                    seen.add(a_norm)
                    unique.append(a)

            if reply_to and self.post:
                self.post.publish(reply_to, {
                    "actions": unique[:limit],
                    "request_id": request_id,
                    "from": self.ACTOR_NAME,
                })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal query_actions error: {e}")

    def _on_postal_bind(self, envelope):
        """
        Handle cortex.bind requests.

        Bind an experience to the cortex so it can be recalled later.

        Request: {
            "input_text": "hello",
            "response": "hey there!",
            "feeling": "warm",
            "context_tags": ["greeting", "chat"],
            "from_fairy": "SourpatchesFairy"
        }
        """
        try:
            payload = _extract_payload(envelope)
            input_text = payload.get("input_text", "")
            response = payload.get("response", "")
            feeling = payload.get("feeling", "neutral")
            context_tags = payload.get("context_tags", [])
            from_fairy = payload.get("from_fairy", "unknown")

            # FIX 2026-03-22 (Nous): Fall back to "concepts" list if no input_text.
            # AudioCortexFairy (pre-fix) sent {"concepts": [...]} without input_text,
            # causing all audio words to bail here — only phoneme edges, zero semantic.
            if not input_text:
                _concepts = payload.get("concepts", [])
                if _concepts and isinstance(_concepts, list):
                    input_text = " ".join(str(c) for c in _concepts[:20])
                else:
                    return

            # FIX 2026-02-23: Reject non-language content at reception.
            # Defense-in-depth: even if KnowledgeDigestion misses something,
            # the cortex should not bind JSON/code/data as "experience".
            _sample = input_text[:300]
            # 2026-08-31 (Nous + Ace): the apostrophe was missing, and that is the
            # entire miss. This guard was written for JSON; a PYTHON dict repr uses
            # ' not ", so "{' intent': 'value'}" scored struct=3/20=0.15 (not >0.15),
            # alpha=0.55 (passes), and '":' never occurs. It threaded all three and
            # became a cortex concept she then said ALOUD hundreds of times.
            _struct = sum(1 for c in _sample if c in '{}[]();,:"\'\\=<>|')
            _alpha = sum(1 for c in _sample if c.isalpha())
            if len(_sample) > 15 and (
                _struct / len(_sample) > 0.15  # High structural punctuation
                or _alpha / len(_sample) < 0.40  # Too few letters
                or _sample.count('{') + _sample.count('}') + _sample.count('":') >= 3  # JSON
                # PYTHON REPR 2026-08-31: dict/tuple reprs use single quotes, so the
                # JSON test above never fires on them. Two of these pairs is a repr.
                or _sample.count("{'") + _sample.count("':") + _sample.count("', '") >= 2
            ):
                return  # Silently reject — not natural language

            # Create concept
            concept_key = f"{from_fairy.lower()}_exp_{int(time.time())}"
            # TOKENIZER FIX 2026-08-31 (Nous + Ace): this was a RAW whitespace
            # split, so "{'intent':" survived whole and was minted as a cortex
            # concept -- then spread returned it, the narrator dropped it into a
            # template slot, and LuxTTS spoke it. Measured on her runtime log:
            # 2,239 utterances, 645 distinct, the top six all "{' intent':".
            # Strip punctuation from the EDGES of each token only. Interiors are
            # untouched, so "there's" stays "there's" -- this normalises, it does
            # not mangle. "{'intent':" -> "intent", "deepens..." -> "deepens".
            _EDGE_PUNCT = "{}[]()<>\"'`,;:.!?*|=+/\\~@#$%^&-_ \t\r\n"
            words = []
            for _w in input_text.split():
                _t = _w.lower().strip(_EDGE_PUNCT)
                if len(_t) > 2:
                    words.append(_t)

            features = {"lex": words[:10]}

            if response:
                features["action"] = [response[:50]]

            if feeling and feeling != "neutral":
                features["affect"] = [feeling]

            if context_tags:
                features["context"] = context_tags[:5]

            # ── Vision modality: extract visual features if present ──
            # VisualCortexFairy sends "vision" key with features like
            # ["brightness:0.8", "color:#4a90d9", "motion:true", "hue:120"]
            vision_data = payload.get("vision", []) or payload.get("vision_tags", [])
            if vision_data and isinstance(vision_data, list):
                features["vision"] = vision_data[:10]

            # ── Audio modality: extract audio features if present (2026-03-16 Nous) ──
            # AudioCortexFairy sends "audio" key with features like
            # ["audio_level:0.5", "audio_type:speech", "audio_pitch:220"]
            audio_data = payload.get("audio", [])
            if audio_data and isinstance(audio_data, list):
                features["audio"] = audio_data[:10]

            # ── Harmonic modality: frequency decomposition tags (2026-03-16 Nous) ──
            # Both visual and audio fairies send "harmonic" key with tags like
            # ["visual_alpha:0.80", "audio_gamma:0.50", "visual_theta:0.30"]
            harmonic_data = payload.get("harmonic", [])
            if harmonic_data and isinstance(harmonic_data, list):
                features["harmonic"] = harmonic_data[:8]

            # Resolve Stargate address from the sender
            origin_plane = payload.get("origin_plane", "")
            origin_channel = payload.get("origin_channel", "")
            # Use from_fairy as origin if no explicit plane/channel given
            if not origin_plane and from_fairy:
                origin_plane = _infer_plane_from_fairy(from_fairy)
            if not origin_channel:
                origin_channel = "experience"

            # Build concepts_to_bind list
            concepts_to_bind = [concept_key] + words[:3]
            if feeling and feeling != "neutral":
                concepts_to_bind.append(f"affect_{feeling}")

            # Telemetry (visual_brightness_*, visual_color_*, audio_band_*,
            # harmonic_*) is intentionally NOT minted as cortex concept keys.
            # It rides along as metadata on the parent concept (features["vision"]
            # /["audio"]/["harmonic"]) and continues to drive chemistry/affect via
            # the parallel publishes (NeuralMesh, AffectBridge, SomaticEngine).
            # Structural sensory concepts (e.g. browser_open, ace_speaking) come
            # from classifier outputs at higher layers, not from feature-tag
            # name munging here.

            # ── HARMONIC SENSORY BRIDGE: Route through decomposition ───
            # (2026-03-17 Nous) Feed raw sensory data through the harmonic
            # bridge so visual+audio get phase-locked into unified percepts.
            _hsb = getattr(self, '_harmonic_sensory_bridge', None)
            if _hsb:
                try:
                    if vision_data:
                        _hsb.decompose_visual(vision_data)
                    if audio_data:
                        # Build audio dict from feature tags
                        _audio_dict = {}
                        for af in audio_data:
                            if ":" in af:
                                k, v = af.split(":", 1)
                                try:
                                    _audio_dict[k] = float(v)
                                except ValueError:
                                    _audio_dict[k] = v
                        if _audio_dict:
                            _hsb.decompose_audio(_audio_dict)
                    # Try cross-modal bind (fires if both senses in 200ms)
                    _binding = _hsb.try_multimodal_bind()
                    if _binding:
                        # Add bound percept concepts to the binding
                        bound_tags = _binding.get("tags", [])
                        for tag in bound_tags[:3]:
                            if isinstance(tag, str) and len(tag) > 2:
                                concepts_to_bind.append(f"percept_{tag}")
                except Exception:
                    pass  # Non-critical

            # ── Concept metadata: v2 schema enrichment (2026-03-20 Nous+Ace) ──
            # If the caller sent concept_metadata, carry it through TARDIS
            # so enriched bindings (snippets, node_types) reach the manifold.
            concept_metadata = payload.get("concept_metadata", {})

            # ── TARDIS: Queue instead of synchronous portal IPC ──────────
            # Before TARDIS: add_concept() + bind_concepts() blocked 50-500ms
            # After TARDIS: queue put returns in <1ms, flush thread compresses
            if len(concepts_to_bind) > 1 and self._tardis_flush_running:
                try:
                    _item = {
                        "concept_key": concept_key,
                        "features": features,
                        "concepts_to_bind": concepts_to_bind,
                        "feeling": feeling,
                        "from_fairy": from_fairy,
                        "origin_plane": origin_plane,
                        "origin_channel": origin_channel,
                    }
                    if concept_metadata:
                        _item["concept_metadata"] = concept_metadata
                    self._tardis_bind_queue.put_nowait(_item)
                    self._tardis_binds_queued += 1
                except _queue.Full:
                    self._tardis_drops += 1
                    # Fallback: direct sync call (better than losing data)
                    self.add_concept(concept_key, features,
                                     origin_plane=origin_plane,
                                     origin_channel=origin_channel,
                                     origin_fairy=from_fairy)
                    self.bind_concepts(concepts_to_bind, rel="experience",
                                       origin_plane=origin_plane,
                                       origin_channel=origin_channel,
                                       origin_fairy=from_fairy)
            elif len(concepts_to_bind) > 1:
                # TARDIS not running yet — direct sync (boot phase)
                self.add_concept(concept_key, features,
                                 origin_plane=origin_plane,
                                 origin_channel=origin_channel,
                                 origin_fairy=from_fairy)
                self.bind_concepts(concepts_to_bind, rel="experience",
                                   origin_plane=origin_plane,
                                   origin_channel=origin_channel,
                                   origin_fairy=from_fairy)

            modalities = list(features.keys())
            if self._tardis_binds_queued % 50 == 1:
                print(f"[{self.ACTOR_NAME}] Bound experience from {from_fairy} "
                      f"[{origin_plane}/{origin_channel}]: '{input_text[:30]}...' "
                      f"modalities={modalities} "
                      f"(TARDIS q={self._tardis_bind_queue.qsize()})", flush=True)

            # Slice 0 telemetry — read-only, sampled. Plan: SLICE_0_INSTRUMENTATION.md
            try:
                from infrastructure.telemetry import slice0_writer as _s0
                from fairies.P20_Somatic.chemistry.chemistry_state import (
                    get_aer_chemistry as _get_aer,
                    get_chemistry_state as _get_chem,
                )
                _aer = _get_aer()
                _chem14 = _get_chem().get_14channel_vector()
                # Capture the primary bind pair (first two concepts).
                if len(concepts_to_bind) >= 2:
                    _s0.record_bind(
                        (concepts_to_bind[0], concepts_to_bind[1]),
                        source=from_fairy,
                        aer=_aer,
                        chemistry=_chem14,
                        is_new_edge=False,  # we don't know without portal round-trip
                        extra={
                            "modalities": modalities,
                            "origin_plane": origin_plane,
                            "origin_channel": origin_channel,
                            "input_preview": input_text[:80],
                            "concepts_count": len(concepts_to_bind),
                        },
                    )
            except Exception:
                pass  # Telemetry must never break the bind path

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal bind error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # UNIVERSAL TRAINING PIPELINE (2026-03-18 Nous)
    #
    # Accept rich text from ANY source and create proper concepts + edges.
    # Sources: PAI responses, SRM cards, web scrapes, books, images, media.
    #
    # cortex.train   — Single text passage → extract concepts → bind edges
    # cortex.train_batch — Multiple texts in one message → batch processing
    #
    # The key insight: PAI responses like "consciousness is the felt quality
    # of information integration across multiple modalities" should create
    # concepts like ["consciousness", "felt_quality", "information_integration",
    # "multiple_modalities"] with edges between all of them. The current PAI
    # bind just grabs 8 individual words and misses compound concepts entirely.
    # ═══════════════════════════════════════════════════════════════════════

    def _on_cortex_train(self, envelope):
        # Ensure _train_count exists (used before late-init at line 5009)
        if not hasattr(self, '_train_count'):
            self._train_count = 0
        """
        UNIVERSAL TRAINING: Accept text from any source, extract concepts, bind.

        Payload: {
            "text": str,           # The text content to learn from
            "source": str,         # Source identifier (e.g. "pai", "srm", "web_scrape", "book")
            "source_fairy": str,   # Which fairy sent this (for tracing)
            "context_tags": list,  # Optional tags for context
            "weight": float,       # Edge weight (default 0.5, PAI=0.7, identity=0.9)
            "affect": str,         # Emotional context (optional)
            "trace_id": str,       # Trace ID for tracking (optional)
            "max_concepts": int,   # Max concepts to extract (default 30)
        }
        """
        try:
            payload = _extract_payload(envelope)
            text = payload.get("text", "")
            if not text or len(text) < 20:
                return

            source = payload.get("source", "unknown")
            source_fairy = payload.get("source_fairy", source)
            context_tags = payload.get("context_tags", [])
            weight = float(payload.get("weight", 0.5))
            affect = payload.get("affect", "")
            trace_id = payload.get("trace_id", f"train_{int(time.time())}")
            max_concepts = int(payload.get("max_concepts", 30))

            # Determine manifold tracer_id from source/source_fairy
            _manifold_tracer = _FAIRY_TRACER_MAP.get(source_fairy, TRACE_UNKNOWN)
            if _manifold_tracer == TRACE_UNKNOWN:
                # Fall back to source field for book ingestion etc.
                _manifold_tracer = _FAIRY_TRACER_MAP.get(source, TRACE_SYSTEM)

            # Reject non-language (same filter as cortex.bind)
            _sample = text[:300]
            _struct = sum(1 for c in _sample if c in '{}[]();,:"\\=<>|')
            _alpha = sum(1 for c in _sample if c.isalpha())
            if len(_sample) > 15 and (
                _struct / len(_sample) > 0.15
                or _alpha / len(_sample) < 0.40
            ):
                return  # Not natural language

            # Extract concepts using the REAL extractor (bigrams, frequency, CamelCase)
            concepts = self._extract_concepts_from_text(text, max_concepts=max_concepts)
            if not concepts or len(concepts) < 2:
                return

            # FIX 2026-03-20 (Nous): STOP injecting system metadata as concepts.
            # This was the ROOT CAUSE of cortex pollution — affect, source tags,
            # fairy names all got ALL-PAIRS bound with content concepts.
            # "hello" ended up connected to "reasoning" because both were in same batch.
            # System metadata belongs in the System Region ONLY (Phase 3).
            # See: Claude_Office/plans/CORTEX_REBUILD_BLUEPRINT.md
            # OLD (broken):
            #   if affect: concepts.append(f"affect_{affect}")
            #   for tag in context_tags: concepts.append(tag)
            # NEW: metadata logged but NOT injected into concept graph
            if affect or context_tags:
                if self._train_count % 50 == 1:
                    print(f"[{self.ACTOR_NAME}] TRAIN metadata (NOT injected): "
                          f"affect={affect}, tags={context_tags}")

            # ── HOLOGRAPHIC SNIPPET DISTRIBUTION (2026-03-27, Nous + Ace) ──
            # Each concept node gets the source sentence as its snippet.
            # "Ace has lavender-haired Sourpatches" → every extracted concept
            # gets that sentence as its snippet. Each word is a coordinate
            # back to the whole — like holographic recall where any fragment
            # can reconstruct the complete memory.
            #
            # Truncate to 500 chars to avoid bloating the string table.
            # Only set if node doesn't already have a snippet (don't overwrite
            # richer content with shorter fragments).
            _snippet_text = text.strip()
            if len(_snippet_text) > 500:
                # Find a sentence boundary near 500
                _cut = _snippet_text[:500].rfind(". ")
                if _cut > 200:
                    _snippet_text = _snippet_text[:_cut + 1]
                else:
                    _snippet_text = _snippet_text[:500]

            # Track training stats
            self._train_count = getattr(self, '_train_count', 0) + 1
            self._train_concepts = getattr(self, '_train_concepts', 0) + len(concepts)

            # Route through portal (portal-first) or local graph
            _is_portal = getattr(self, '_portal_is_primary', False)
            _am = getattr(self, '_akashic_cortex_region', None)

            if _is_portal:
                _pg = getattr(self, '_portal_gate', None)
                if _pg and len(concepts) >= 2:
                    try:
                        _n = min(len(concepts), 15)
                        _pairs = [
                            [concepts[i], concepts[j]]
                            for i in range(_n) for j in range(i + 1, _n)
                        ]
                        # FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan):
                        # _manifold_tracer was already computed for set_snippet
                        # below — also forward it through the bind path so
                        # the new edges/nodes get tagged at write-time.
                        if hasattr(_pg, 'bind_many_async'):
                            _pg.bind_many_async(pairs=_pairs, weight=weight,
                                                tracer_id=_manifold_tracer)
                        else:
                            _pg.bind_many(pairs=_pairs, weight=weight,
                                          tracer_id=_manifold_tracer)
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] TRAIN portal bind error: {e}")

                # Holographic snippets — distribute source text to all concept nodes
                if _am and _snippet_text and hasattr(_am, 'set_snippet'):
                    _snippeted = 0
                    for concept in concepts[:15]:
                        try:
                            _existing = _am.get_node(concept)
                            if _existing and isinstance(_existing, dict):
                                _old_snip = _existing.get("snippet", "")
                                if _old_snip and len(_old_snip) > len(_snippet_text):
                                    continue  # Keep richer existing snippet
                            _am.set_snippet(concept, _snippet_text, tracer_id=_manifold_tracer)
                            _snippeted += 1
                        except Exception:
                            pass
                    if _snippeted and self._train_count % 50 == 1:
                        print(f"[{self.ACTOR_NAME}] HOLOGRAPHIC: {_snippeted}/{len(concepts[:15])} "
                              f"nodes got snippet ({len(_snippet_text)} chars)")

            else:
                # Local graph path
                origin_plane = _infer_plane_from_fairy(source_fairy) if source_fairy else "P30"
                for concept in concepts[:15]:
                    self._graph.upsert_node(concept, {"source": f"train_{source}"},
                                            origin_plane=origin_plane,
                                            origin_channel=f"train_{source}",
                                            origin_fairy=source_fairy)
                self._mark_dirty(*concepts[:15])
                for i, a in enumerate(concepts[:15]):
                    for b in concepts[i + 1:15]:
                        self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, weight=weight)
                        self._mark_dirty(a, b)

                # Holographic snippets — local graph path
                if _am and _snippet_text and hasattr(_am, 'set_snippet'):
                    for concept in concepts[:15]:
                        try:
                            _existing = _am.get_node(concept)
                            if _existing and isinstance(_existing, dict):
                                _old_snip = _existing.get("snippet", "")
                                if _old_snip and len(_old_snip) > len(_snippet_text):
                                    continue
                            _am.set_snippet(concept, _snippet_text, tracer_id=_manifold_tracer)
                        except Exception:
                            pass

            # Log periodically
            if self._train_count % 10 == 1:
                print(f"[{self.ACTOR_NAME}] TRAIN #{self._train_count} from {source} "
                      f"({len(concepts)} concepts, weight={weight}, portal={_is_portal}) "
                      f"trace={trace_id} total_concepts_trained={self._train_concepts}",
                      flush=True)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_cortex_train ERROR: {e}")

    def _on_cortex_train_batch(self, envelope):
        """
        BATCH TRAINING: Process multiple texts in one message.

        Payload: {
            "items": [
                {"text": str, "source": str, "weight": float, ...},
                ...
            ],
            "source": str,          # Default source for all items
            "source_fairy": str,    # Default fairy for all items
            "trace_id": str,        # Batch trace ID
        }

        Each item follows the same format as cortex.train payload.
        Designed for: SRM card dumps, web scrape batches, book chapters.
        """
        try:
            payload = _extract_payload(envelope)
            items = payload.get("items", [])
            default_source = payload.get("source", "batch")
            default_fairy = payload.get("source_fairy", "batch_trainer")
            trace_id = payload.get("trace_id", f"batch_{int(time.time())}")

            if not items:
                return

            processed = 0
            total_concepts = 0

            for item in items[:500]:  # Cap at 500 items per batch
                if not isinstance(item, dict):
                    continue
                text = item.get("text", "")
                if not text or len(text) < 20:
                    continue

                # Merge defaults
                item.setdefault("source", default_source)
                item.setdefault("source_fairy", default_fairy)
                item.setdefault("trace_id", f"{trace_id}_{processed}")

                # Delegate to single-item handler
                self._on_cortex_train(item)
                processed += 1

            print(f"[{self.ACTOR_NAME}] BATCH TRAIN: {processed}/{len(items)} items from {default_source} "
                  f"trace={trace_id}", flush=True)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_cortex_train_batch ERROR: {e}")

    def _on_postal_bind_outcome(self, envelope):
        """
        Handle cortex.bind_outcome requests.

        Bind an action outcome (success/fail) for learning.

        Request: {
            "action": "respond to greeting",
            "succeeded": true,
            "context": "chat",
            "from_fairy": "ProbabilityOracleFairy"
        }
        """
        try:
            payload = _extract_payload(envelope)
            action = payload.get("action", "")
            succeeded = payload.get("succeeded", True)
            context = payload.get("context", "")
            from_fairy = payload.get("from_fairy", "unknown")

            if not action:
                return

            concept_key = f"{from_fairy.lower()}_outcome_{int(time.time())}"
            words = [w.lower().strip() for w in action.split() if len(w) > 2]

            features = {
                "lex": words[:10],
                "affect": ["success" if succeeded else "fail"],
                "context": [from_fairy, "outcome"],
            }

            if context:
                features["context"].append(context[:20])

            # Stargate address from sender
            origin_plane = _infer_plane_from_fairy(from_fairy)
            self.add_concept(concept_key, features,
                             origin_plane=origin_plane,
                             origin_channel="outcome",
                             origin_fairy=from_fairy)

            if words:
                self.bind_concepts([concept_key] + words[:3], rel="outcome",
                                   origin_plane=origin_plane,
                                   origin_channel="outcome",
                                   origin_fairy=from_fairy)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal bind_outcome error: {e}")

    def _on_postal_spread(self, envelope):
        """
        Handle cortex.spread requests from postal.

        This is a wrapper that extracts the payload and calls _handle_spread.
        Supports both legacy reply_to and new _response_topic patterns.
        """
        try:
            _s0_t0 = time.perf_counter()
            result = self._handle_spread(envelope)
            _s0_wall_ms = (time.perf_counter() - _s0_t0) * 1000.0

            # Publish result if reply_to or _response_topic provided
            payload = _extract_payload(envelope)
            reply_to = payload.get("reply_to") or payload.get("_response_topic")
            request_id = payload.get("request_id") or payload.get("_request_id", "")

            if reply_to and self.post:
                result["request_id"] = request_id
                result["from"] = self.ACTOR_NAME
                self.post.publish(reply_to, result)

            # Slice 0 telemetry — read-only, sampled. Plan: SLICE_0_INSTRUMENTATION.md
            try:
                from infrastructure.telemetry import slice0_writer as _s0
                from fairies.P20_Somatic.chemistry.chemistry_state import (
                    get_aer_chemistry as _get_aer,
                )
                _aer = _get_aer()
                _seed = payload.get("seed") or ""
                _activations = (result or {}).get("activations") or {}
                # top-K visited by activation level
                _top = sorted(_activations.items(), key=lambda kv: kv[1], reverse=True)[:20]
                _conv = sum(1 for _, v in _activations.items() if v > 0.3)
                _s0.record_spread(
                    [_seed],
                    top_visited=_top,
                    aer=_aer,
                    chemistry_params={
                        "max_hops": payload.get("max_hops", 2),
                        "source": (result or {}).get("source", "unknown"),
                        "ok": (result or {}).get("ok", False),
                    },
                    convergence_count=_conv,
                    wall_ms=_s0_wall_ms,
                    extra={
                        "total_activations": len(_activations),
                        "request_id": request_id,
                    },
                )
            except Exception:
                pass  # Telemetry must never break the spread path

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal spread error: {e}")

    def _p5_probe(self, seed, source, activations):
        """TEMP P5 A/B probe (2026-06-12 Nous+Ace) — REMOVE after confirmed. For the
        first 8 real spreads, logs the NORMAL (co-occurrence) result AND a READ-ONLY
        REL_SEMANTIC spread via the portal gate, side by side: does rel_filter surface
        MEANING (somatic→somatic_mind/self) vs word-stems (alert→alertly/alerts)? The
        semantic result is NOT used by the council — purely measured (bounded to 8)."""
        try:
            n = getattr(self, '_p5_probe_n', 0)
            if n >= 8:
                return
            self._p5_probe_n = n + 1
            _am = getattr(self, '_akashic_cortex_region', None)
            _ams = ('LIVE:' + type(_am).__name__) if _am is not None else 'None'
            top = [k for k, _ in sorted(activations.items(), key=lambda x: -x[1])[:8]] if activations else []
            # A/B: read-only REL_SEMANTIC spread via the portal gate (NOT used by council)
            _sem = []
            try:
                from infrastructure.manifold_memory import REL_SEMANTIC
                if getattr(self, '_portal_gate_enabled', False) and self._portal_gate:
                    _sr = self._portal_gate.spread(seed, depth=2, limit=12, rel_filter=REL_SEMANTIC)
                    _sa = (_sr.get("activated") or _sr.get("activations") or {}) if _sr else {}
                    _sem = [k for k, _ in sorted(_sa.items(), key=lambda x: -x[1])[:8]]
            except Exception as _se:
                _sem = [f"err:{type(_se).__name__}:{_se}"]
            print(f"[P5-PROBE {n}] seed={seed!r} source={source} _am={_ams} "
                  f"cf={getattr(self, '_cortex_farm_enabled', None)} n_act={len(activations) if activations else 0}\n"
                  f"    NORMAL  (co-occur)  = {top}\n"
                  f"    SEMANTIC(rel_filter)= {_sem}", flush=True)
        except Exception as _e:
            print(f"[P5-PROBE] err: {_e}", flush=True)

    def _handle_spread(self, message) -> Dict[str, Any]:
        """
        Handle spread activation request.

        Exposes spreading activation for the CognitionBridge to use for
        goal discovery and contextual concept finding.

        Args:
            message: Postal envelope or dict with:
                - seed (str): Starting concept for spreading activation
                - max_hops (int, optional): Max hops to spread (default 2)
                - helix_hint (dict, optional): Helix coordinate hint
                    If helix_hint.affect.domain provided, same-domain concepts
                    get 1.3x boost

        Returns:
            Dict with:
                - ok (bool): Success/failure
                - activations (dict): Concept -> activation level mapping
                - seed (str): The seed concept used
                - hops (int): Max hops used
                - error (str, optional): Error message if ok=False
        """
        payload = _extract_payload(message)

        seed = payload.get("seed")
        max_hops = payload.get("max_hops", 2)
        helix_hint = payload.get("helix_hint")

        # Error: no seed
        if not seed:
            return {"ok": False, "error": "no_seed", "message": "seed is required"}

        # ── CORTEX FARM PATH (2026-03-15 Nous + Ace) ────────────────
        # Spreading activation dispatched to battery-powered workers.
        # Workers traverse the graph by discharging charge per hop.
        # If a worker depletes mid-thought, relay to next charged worker.
        if self._cortex_farm_enabled and self._cortex_farm:
            try:
                results = self._cortex_farm.submit_spread(seed, depth=max_hops, top_k=50)
                if results:
                    activations = {k: v for k, v in results}
                    if helix_hint and activations:
                        activations = self._apply_helix_boost(activations, helix_hint)
                    self._cortex_farm_spreads += 1
                    self._p5_probe(seed, "cortex_farm", activations)
                    return {
                        "ok": True,
                        "activations": activations,
                        "seed": seed,
                        "hops": max_hops,
                        "source": "cortex_farm",
                    }
            except Exception:
                pass  # Fall through to portal gate

        # ── AKASHIC MANIFOLD PATH (2026-03-20 Nous) ─────────────────
        # Direct mmap read — bypasses TCP gate entirely. 0 latency, 0 errors.
        _am = getattr(self, '_akashic_cortex_region', None)
        if _am:
            try:
                _tau = getattr(self, '_portal_time_dilation', 1.0)
                activations = _am.spread_activation(
                    seed, depth=max_hops, limit=50, time_dilation=_tau,
                )
                self._manifold_ops = getattr(self, '_manifold_ops', 0) + 1
                if activations:
                    if helix_hint and activations:
                        activations = self._apply_helix_boost(activations, helix_hint)
                    self._portal_crossings += 1
                    self._p5_probe(seed, "manifold", activations)
                    return {
                        "ok": True,
                        "activations": activations,
                        "seed": seed,
                        "hops": max_hops,
                        "source": "manifold",
                    }
            except Exception:
                pass  # Fall through to portal gate

        # PORTAL GATE PATH — spread in the full graph subprocess
        if self._portal_gate_enabled and self._portal_gate:
            try:
                # FIX 2026-03-13 Nous: Pass time_dilation so portal accelerates spreading
                result = self._portal_gate.spread(
                    seed, depth=max_hops, limit=50,
                    time_dilation=getattr(self, '_portal_time_dilation', 1.0),
                )
                if result and result.get("status") == "ok":
                    activations = result.get("activated", {})
                    # Apply helix_hint boosting if provided
                    if helix_hint and activations:
                        activations = self._apply_helix_boost(activations, helix_hint)
                    self._portal_crossings += 1
                    self._p5_probe(seed, "portal", activations)
                    return {
                        "ok": True,
                        "activations": activations,
                        "seed": seed,
                        "hops": max_hops,
                        "source": "portal",
                    }
            except Exception as e:
                pass  # Fall through to local graph

        # Error: no graph
        if not self._graph:
            return {"ok": False, "error": "no_graph", "message": "concept graph not loaded"}

        # Perform spreading activation (local working set)
        activations = self._graph.spread_activation(seed, max_hops=max_hops)

        # Apply helix_hint boosting if provided
        if helix_hint and activations:
            activations = self._apply_helix_boost(activations, helix_hint)

        self._p5_probe(seed, "local_graph", activations)
        return {
            "ok": True,
            "activations": activations,
            "seed": seed,
            "hops": max_hops,
        }

    def _apply_helix_boost(self, activations: Dict[str, float], helix_hint: Dict[str, Any]) -> Dict[str, float]:
        """
        Boost activations for concepts matching helix_hint domain.

        If helix_hint has affect.domain, concepts with the same affect domain
        get a 1.3x boost to their activation.

        Args:
            activations: Dict mapping concept keys to activation levels
            helix_hint: Dict with optional affect.domain

        Returns:
            Modified activations dict with boosts applied
        """
        # Extract target domain from helix_hint
        affect_hint = helix_hint.get("affect", {})
        target_domain = affect_hint.get("domain") if isinstance(affect_hint, dict) else None

        if not target_domain:
            return activations

        # Apply 1.3x boost to same-domain concepts
        DOMAIN_BOOST = 1.3
        boosted = {}

        for concept_key, activation in activations.items():
            node = self._graph.get_node(concept_key)
            if node:
                # Check if node has matching affect domain
                node_affect = node.features.get("affect", {})
                if isinstance(node_affect, dict):
                    node_domain = node_affect.get("domain")
                    if node_domain == target_domain:
                        boosted[concept_key] = activation * DOMAIN_BOOST
                        continue

            # No boost - keep original activation
            boosted[concept_key] = activation

        return boosted

    # =========================================================================
    # PARADOX ENERGY HANDLER (DCE Phase 3)
    # =========================================================================

    def _on_paradox_energy(self, envelope) -> None:
        """
        Receive zero-point collision energy to power card cluster operations.

        DCE Phase 3: The collision chamber produces energy → ParadoxEnergyBridge
        converts it → paradox.energy.pulse arrives here → powers card sync bursts.

        Energy budget model:
        - Incoming energy accumulates in _paradox_energy_budget
        - Card write operations deduct from the budget (Landauer cost)
        - When budget exceeds threshold, trigger a card sync burst
        """
        payload = _extract_payload(envelope)
        energy = payload.get("energy", 0.0)

        if energy <= 0:
            return

        # ── CORTEX FARM ENERGY SPLIT (2026-03-15 Nous + Ace) ──
        # Split incoming paradox energy between CortexFarm (thinking) and
        # card sync (persistence). The farm needs energy to power its
        # battery workers; card sync needs energy to persist dirty concepts.
        if self._cortex_farm_enabled and self._cortex_farm:
            farm_share = energy * self._cortex_farm_energy_share
            card_share = energy * (1.0 - self._cortex_farm_energy_share)
            # Feed the farm workers (Loop 3: energy amplified by time compression)
            self._cortex_farm.receive_energy(farm_share, source="paradox_pulse")
            energy = card_share  # Remainder goes to card sync below

        self._paradox_energy_budget += energy
        self._paradox_energy_received += energy

        # When enough energy accumulates, trigger a card sync burst
        # This converts collision energy into actual card cluster work
        SYNC_BURST_THRESHOLD = 0.1  # Minimum energy for a sync burst
        if self._paradox_energy_budget >= SYNC_BURST_THRESHOLD and self._dirty_concepts:
            max_syncs = max(1, int(self._paradox_energy_budget * 10))  # ~10 cards per unit energy
            synced = 0
            energy_cost_per_sync = 0.02  # Landauer cost per card write

            for key in list(self._dirty_concepts)[:max_syncs]:
                if self._paradox_energy_budget < energy_cost_per_sync:
                    break  # Not enough energy for another write

                if self._sync_concept_to_helix(key):
                    self._dirty_concepts.discard(key)
                    synced += 1
                    self._paradox_energy_budget -= energy_cost_per_sync
                    self._paradox_energy_spent += energy_cost_per_sync

            if synced > 0:
                self._paradox_sync_bursts += 1
                if self._helix_coordinator:
                    self._helix_coordinator.save()

                # Publish Landauer drain to token system
                self._publish_landauer_drain(synced)

                # Recycle: card sync completed = work done = energy returns
                if self.post:
                    self.post.publish("energy.work.completed", {
                        "from": self.ACTOR_NAME,
                        "work_type": "card_cluster_sync",
                        "energy_spent": synced * energy_cost_per_sync,
                        "efficiency": synced / max_syncs if max_syncs > 0 else 1.0,
                        "cards_synced": synced,
                        "ts": time.time(),
                    })

                if synced > 3:
                    print(f"[{self.ACTOR_NAME}] PARADOX SYNC BURST: "
                          f"{synced} cards synced (energy={self._paradox_energy_budget:.3f})")

    # =========================================================================
    # CIRCADIAN CONSOLIDATION HANDLER (DCE Phase 4)
    # =========================================================================

    def _on_paradox_consolidation(self, envelope) -> None:
        """
        Deep circadian consolidation — massive energy release for card sync.

        DCE Phase 4: ParadoxEnergyBridge releases accumulated energy during
        circadian sleep phases. This is MUCH larger than individual pulses
        and triggers a proportionally bigger sync burst.

        Types of consolidation:
        - circadian_night_onset: Partial (evening → night)
        - circadian_deep_sleep: Major (night → sleep)
        - circadian_cycle_complete: Full dump (sleep → deep_night)
        - circadian_wake: Morning release (deep_night → dawn)
        - shutdown_consolidation: System stopping
        - idle_consolidation: Ace away

        The energy here can be 10-100x a normal pulse — this is where
        the system does its deepest memory consolidation work.
        """
        payload = _extract_payload(envelope)
        energy = payload.get("energy", 0.0)
        consolidation_type = payload.get("type", "unknown")

        if energy <= 0:
            return

        # Add to budget (consolidation energy adds DIRECTLY — no drip)
        self._paradox_energy_budget += energy
        self._paradox_energy_received += energy

        # Consolidation gets AGGRESSIVE sync — up to 50 cards per unit energy
        # (vs 10 for normal pulses). Sleep is when real learning happens.
        if self._dirty_concepts:
            cards_per_energy = 50 if "circadian" in consolidation_type else 25
            max_syncs = max(5, int(energy * cards_per_energy))
            synced = 0
            energy_cost_per_sync = 0.015  # Slightly cheaper during consolidation

            for key in list(self._dirty_concepts)[:max_syncs]:
                if self._paradox_energy_budget < energy_cost_per_sync:
                    break

                if self._sync_concept_to_helix(key):
                    self._dirty_concepts.discard(key)
                    synced += 1
                    self._paradox_energy_budget -= energy_cost_per_sync
                    self._paradox_energy_spent += energy_cost_per_sync

            if synced > 0:
                self._paradox_sync_bursts += 1
                if self._helix_coordinator:
                    self._helix_coordinator.save()

                # Publish Landauer drain
                self._publish_landauer_drain(synced)

                print(f"[{self.ACTOR_NAME}] CONSOLIDATION SYNC ({consolidation_type}): "
                      f"{synced} cards synced from {energy:.2f} energy "
                      f"(remaining dirty: {len(self._dirty_concepts)})")

    # =========================================================================
    # PORTAL ENERGY UPKEEP — Portals need energy to stay online
    # =========================================================================

    # Portal energy cost per tick (consumed during on_tick)
    PORTAL_ENERGY_COST_PER_TICK = 0.005  # Energy consumed per heartbeat to stay online
    PORTAL_DORMANT_THRESHOLD = 0.01      # Below this, portal is in danger zone
    # System-power floor: portal draws from system when batteries can't sustain it.
    # "the cortex should fall back to drawing power from my system when the
    #  batteries cant keep it going. thats the association graph inside that portal" — Ace
    # FIX 2026-02-20: Raised from 0.006 to 0.02 — old value gave net +0.001/tick which
    # left portal hovering near zero. 0.02 gives net +0.015/tick on system power,
    # enough to rebuild a buffer while waiting for collision energy.
    PORTAL_SYSTEM_FLOOR = 0.02           # Baseline system sustenance per tick

    # ── GRAVITATIONAL BINDING ENERGY (2026-03-16 Nous + Ace) ──────────
    # "can we fix that by increase the gravity make the mass weigh more?" — Ace
    #
    # A massive cortex generates passive energy from its own gravity.
    # Like a star: mass creates gravitational binding energy that sustains
    # fusion. Bigger cortex = more mass = more passive energy generation.
    #
    # Formula: regen = log1p(mass / MASS_SCALE) * MASS_REGEN_RATE
    #   At 168K nodes + 630K edges (~800K mass): gravity_well=16
    #   log1p(16) ≈ 2.83, regen = 2.83 * 0.004 = 0.0113/tick
    #   Covers the 0.005 base cost with +0.0063/tick surplus.
    #
    # FIX 2026-03-20 (Nous + Ace): Increased from 0.003 → 0.004.
    # At 52K nodes + 111K edges (post-encyclopedia training):
    #   mass = 217K, gravity_well = 4.35
    #   log1p(4.35) ≈ 1.68, regen = 1.68 * 0.004 = 0.0067/tick
    #   Net = 0.0067 - 0.005 = +0.0017/tick ← self-sustaining!
    # Old rate (0.003) gave net -0.0002/tick → slow bleed to death.
    # The cortex was BARELY too small to sustain itself. This tips
    # the balance positive while the cortex keeps growing.
    PORTAL_MASS_REGEN_RATE = 0.004  # Energy per unit log-mass per tick

    def _on_portal_energy_upkeep(self, envelope) -> None:
        """
        Receive portal sustenance energy from ParadoxEnergyBridge.

        "the energy physics should be powering these portals" — Ace

        Portal upkeep energy keeps the dimension online. If this stops
        flowing, the portal goes dormant (not dead — just sleeping).
        When energy returns, it wakes back up.

        Also publishes energy.work.completed to complete the recycling loop:
        portal stayed online = work done = partial energy returns to bridge.
        """
        payload = _extract_payload(envelope)
        energy = payload.get("energy", 0.0)

        if energy <= 0:
            return

        self._portal_energy_budget += energy
        self._portal_energy_received += energy

        # FIX 2026-04-11 (Nous + Ace): Bridge energy to REAL battery in subprocess.
        # The main process float (_portal_energy_budget) is cosmetic.
        # The subprocess PortalBattery (100K token budget) does the real work.
        # Convert energy float to tokens and send via portal gate IPC.
        if self._portal_gate_enabled and self._portal_gate and energy > 0.001:
            _tokens = int(energy * 500)  # 0.1 energy ≈ 50 tokens
            if _tokens > 0:
                try:
                    self._portal_gate.send({"cmd": "charge", "tokens": _tokens})
                except Exception:
                    pass  # Gate busy — energy lost this cycle, next collision will send more

        # If we were dormant and energy arrived, wake up
        if self._portal_dormant and self._portal_energy_budget > self.PORTAL_DORMANT_THRESHOLD:
            self._portal_dormant = False
            if self._portal_address_registered:
                self._publish_portal_event("wake", {"reason": "energy_restored"})
            print(f"[{self.ACTOR_NAME}] PORTAL AWAKE: Energy restored "
                  f"({self._portal_energy_budget:.3f})")

        # Recycle: portal staying online = work completed
        # This feeds back to ParadoxEnergyBridge._on_work_completed
        if self.post and energy > 0.005:
            self.post.publish("energy.work.completed", {
                "from": self.ACTOR_NAME,
                "work_type": "portal_upkeep",
                "energy_spent": energy,
                "efficiency": 1.0 if not self._portal_dormant else 0.5,
                "ts": time.time(),
            })

    # Minimum energy floor — the cortex NEVER drops below this.
    # Like cerebral autoregulation: the brain always gets blood.
    # "can we also push energy into it on boot?" — Ace
    PORTAL_ENERGY_FLOOR = 0.20  # 20% minimum — enough for ~40 ticks of headroom

    def _consume_portal_energy(self) -> None:
        """
        Called from on_tick — consume cortex upkeep energy.

        The cortex (association graph) is a critical organ — it never fully
        starves while the system is alive. Like cerebral autoregulation:
        the brain always gets blood flow even at rest.

        Energy consumption has two components:
        1. Base upkeep: 0.005/tick just to stay online (constant)
        2. Work cost:   proportional to manifold operations since last tick

        Energy sources (in priority order):
        1. Collision battery (from ParadoxEnergyBridge) — preferred, full power
        2. Gravitational binding energy (mass generates passive regen)
        3. System floor (heartbeat sustenance) — fallback, always available
        4. Hard floor (PORTAL_ENERGY_FLOOR) — absolute minimum, never breached

        FIX 2026-03-20 (Nous + Ace): Manifold-native energy model.
        Work cost comes from manifold read/write ops, not gate requests.
        Mass regen comes from real manifold mass, not the 34-node stub.
        """
        # ── Gravitational binding energy: mass generates passive regen ──
        # Heavier cortex = more self-sustaining. Like a star fueling itself.
        mass_regen = 0.0
        if self._portal_mass > 0:
            gravity_well = self._portal_mass / PortalGravityMetric.MASS_SCALE
            mass_regen = _math.log1p(gravity_well) * self.PORTAL_MASS_REGEN_RATE
            self._portal_energy_budget += mass_regen

        # Calculate work-based energy cost
        # FIX 2026-03-20: In manifold mode, count manifold operations (spreads,
        # queries, binds) instead of gate requests. The manifold tracks these
        # via _portal_io_processed counter which still increments for manifold ops.
        work_cost = 0.0
        _am_region = getattr(self, '_akashic_cortex_region', None)
        if _am_region:
            # Manifold mode: count operations from manifold ops counter
            current_ops = getattr(self, '_manifold_ops', 0)
            prev_ops = getattr(self, '_portal_prev_manifold_ops', 0)
            new_ops = max(0, current_ops - prev_ops)
            self._portal_prev_manifold_ops = current_ops
            work_cost = new_ops * 0.0001
        elif self._portal_gate_enabled and self._portal_gate:
            # Legacy gate mode
            current_reqs = getattr(self._portal_gate, '_requests_sent', 0)
            prev_reqs = getattr(self, '_portal_prev_gate_reqs', 0)
            new_reqs = max(0, current_reqs - prev_reqs)
            self._portal_prev_gate_reqs = current_reqs
            work_cost = new_reqs * 0.0001

        total_cost = self.PORTAL_ENERGY_COST_PER_TICK + work_cost

        if self._portal_energy_budget >= total_cost:
            # Normal operation: draw from collision battery
            self._portal_energy_budget -= total_cost
            self._portal_energy_consumed += total_cost
            # If we were on system power and energy is restored, log recovery
            if self._portal_dormant and self._portal_energy_budget > self.PORTAL_DORMANT_THRESHOLD:
                self._portal_dormant = False
                if self._portal_address_registered:
                    self._publish_portal_event("wake", {"reason": "battery_restored"})
                print(f"[{self.ACTOR_NAME}] PORTAL AWAKE: Battery restored "
                      f"(budget={self._portal_energy_budget:.3f})")
        else:
            # Battery depleted — fall back to system power
            if not self._portal_dormant:
                self._portal_dormant = True
                print(f"[{self.ACTOR_NAME}] PORTAL LOW ENERGY: Falling back to system power "
                      f"(budget={self._portal_energy_budget:.3f})")
            self._portal_energy_budget += self.PORTAL_SYSTEM_FLOOR
            self._portal_energy_budget -= self.PORTAL_ENERGY_COST_PER_TICK
            self._portal_energy_consumed += self.PORTAL_ENERGY_COST_PER_TICK

        # HARD FLOOR — cerebral autoregulation.
        # The cortex never drops below PORTAL_ENERGY_FLOOR.
        # Like the brain's priority blood supply: even in shock,
        # the body diverts blood to keep the brain alive.
        if self._portal_energy_budget < self.PORTAL_ENERGY_FLOOR:
            deficit = self.PORTAL_ENERGY_FLOOR - self._portal_energy_budget
            self._portal_energy_budget = self.PORTAL_ENERGY_FLOOR
            # Wake up if we were dormant — floor guarantees operation
            if self._portal_dormant:
                self._portal_dormant = False
                print(f"[{self.ACTOR_NAME}] PORTAL SUSTAINED: System floor active "
                      f"(injected {deficit:.4f}, budget={self._portal_energy_budget:.3f})")

        # Cap energy budget at 1.0 (100%) — export surplus to plane batteries.
        # FIX 2026-04-01 (Nous + Ace): Portal was DISCARDING overflow energy.
        # The positive net balance (+0.0094/tick) was being thrown away while
        # plane batteries starved at 9-18%. Now surplus feeds the system.
        if self._portal_energy_budget > 1.0:
            overflow = self._portal_energy_budget - 1.0
            self._portal_energy_budget = 1.0
            # Export to plane batteries via portal.energy.surplus
            if overflow > 0.001 and hasattr(self, 'post') and self.post:
                try:
                    self.post.publish("portal.energy.surplus", {
                        "energy": overflow,
                        "source": "cortex_overflow",
                        "from": "AssociationCortexFairy",
                        "mass_regen": mass_regen,
                    })
                except Exception:
                    pass

    def _publish_landauer_drain(self, card_count: int) -> None:
        """
        Publish Landauer cost for card write operations.

        DCE P_info: Every card write costs information entropy.
        Maps to Sagawa-Ueda bound: P_info = k_B * T * ln(2) per bit erased.

        Args:
            card_count: Number of cards written
        """
        if not self.post or card_count <= 0:
            return

        # Scale multiplier: more cards = more drain (but sublinear — batch efficiency)
        # sqrt scaling: 1 card = 1x, 4 cards = 2x, 9 cards = 3x
        import math
        multiplier = math.sqrt(card_count)

        self.post.publish("token.drain.request", {
            "drain_type": "card_cluster_write",
            "multiplier": multiplier,
            "source": f"cortex_sync_burst_{card_count}_cards",
        })

    # ================================================================
    # PORTAL I/O THREAD — Non-blocking portal communication
    # FIX 2026-03-08 (Nous): Cortex tick drops caused by synchronous
    # portal IPC blocking the single-threaded exec context. Solution:
    # dedicated I/O thread processes all portal commands from a queue.
    # on_tick() submits commands without waiting for responses.
    # ================================================================

    def _start_portal_io(self):
        """Start the dedicated portal I/O thread.

        Called once after the portal gate opens successfully.
        All portal IPC flows through this thread — on_tick never blocks.
        """
        self._portal_io_queue = _queue.Queue(maxsize=256)
        self._portal_io_running = True
        self._portal_io_processed = 0
        self._portal_io_drops = 0
        self._portal_io_thread = threading.Thread(
            target=self._portal_io_worker,
            daemon=True,
            name="cortex-portal-io",
        )
        self._portal_io_thread.start()
        print(f"[{self.ACTOR_NAME}] Portal I/O thread started (queue=256)")

    def _stop_portal_io(self):
        """Stop the portal I/O thread (called on shutdown)."""
        self._portal_io_running = False
        if self._portal_io_queue:
            try:
                self._portal_io_queue.put_nowait(None)  # Shutdown sentinel
            except _queue.Full:
                pass
        if self._portal_io_thread and self._portal_io_thread.is_alive():
            self._portal_io_thread.join(timeout=5.0)
        print(f"[{self.ACTOR_NAME}] Portal I/O thread stopped "
              f"(processed={self._portal_io_processed}, dropped={self._portal_io_drops})")

    def _portal_io_worker(self):
        """Background worker: processes portal commands sequentially.

        Runs in its own thread, decoupled from the tick handler.
        This is the ONLY thread that talks to PortalGate.send().
        The exec context thread submits via _portal_io_submit() and
        never waits for responses.

        Handles:
        - tick: Fire-and-forget heartbeat to portal interior
        - bind_many: Async binding with optional callback
        - status: Cache refresh for diagnostic output
        - Any other portal command
        """
        while self._portal_io_running:
            try:
                item = self._portal_io_queue.get(timeout=2.0)
                if item is None:
                    break  # Shutdown sentinel

                gate = self._portal_gate
                if not gate or not gate.is_open:
                    continue

                request = item.get("request", {})
                cmd = request.get("cmd", "unknown")
                timeout = item.get("timeout", 10.0)

                try:
                    # FIX 2026-03-17 (Nous + Ace): Use fire-and-forget for bind
                    # commands. bind_many on 180K-node graph takes 10-30s for the
                    # response, holding the gate lock the entire time. This caused
                    # 78% gate error rate (2513/3223 timeouts). bind responses
                    # are only used for stats — not worth the lock contention.
                    #
                    # FIX 2026-03-20 (Nous): REMOVED "tick" from fire-and-forget.
                    # Ticks were being silently dropped! The write flush loop only
                    # processes items with "pairs" — ticks have no pairs → dropped.
                    # Result: interior never received energy → battery drain → 28%
                    # energy → slow processing → 89% gate error rate on fresh boot.
                    # Ticks MUST go through gate.send() for energy feedback callback.
                    callback = item.get("callback")
                    if cmd in ("bind_many", "bind") and hasattr(gate, 'send_fire_and_forget'):
                        ok = gate.send_fire_and_forget(request)
                        if ok:
                            self._portal_io_processed += 1
                        result = None  # No response for fire-and-forget
                    else:
                        result = gate.send(request, timeout=timeout)
                        self._portal_io_processed += 1

                    # Cache status results for diagnostic output
                    if cmd == "status" and result and result.get("status") == "ok":
                        self._interior_status_cache = result
                        self._interior_status_cache_ts = time.time()

                    # Execute callback if provided (only for sync sends)
                    if callback and result:
                        try:
                            callback(result)
                        except Exception:
                            pass

                except Exception as e:
                    if cmd not in ("tick",):  # Don't spam for tick failures
                        print(f"[{self.ACTOR_NAME}] Portal I/O error ({cmd}): {e}")

            except _queue.Empty:
                # No commands pending — do periodic status cache refresh
                if self._portal_io_running and self._portal_gate and self._portal_gate.is_open:
                    cache_age = time.time() - getattr(self, '_interior_status_cache_ts', 0)
                    if cache_age > 30.0:  # Refresh every 30s when idle
                        try:
                            st = self._portal_gate.status()
                            if st and st.get("status") == "ok":
                                self._interior_status_cache = st
                                self._interior_status_cache_ts = time.time()
                        except Exception:
                            pass
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Portal I/O worker error: {e}")

    def _portal_io_submit(self, request: dict, callback=None,
                          timeout: float = 10.0) -> bool:
        """Submit a portal command without blocking.

        Args:
            request: The portal command dict (e.g., {"cmd": "tick"})
            callback: Optional callback(result) for when the command completes
            timeout: Timeout for the portal send() call

        Returns:
            True if queued, False if dropped (queue full or I/O not running).
        """
        if not self._portal_io_queue or not self._portal_io_running:
            return False
        try:
            self._portal_io_queue.put_nowait({
                "request": request,
                "callback": callback,
                "timeout": timeout,
            })
            return True
        except _queue.Full:
            self._portal_io_drops += 1
            return False

    def _portal_io_submit_binding(self, pairs: list, weight: float = 0.5,
                                   concept_metadata: dict = None,
                                   tracer_id: int = 0):
        """Submit a binding — manifold-direct or gate fallback.

        FIX 2026-03-20 (Nous + Ace): Russian Doll — writes go directly to
        the AkashicManifold mmap region. No gate, no subprocess, no pipe.

        FIX 2026-03-20 (Nous + Ace): Enriched pairs — v2 schema support.
        Pairs can be [a, b] or [a, b, {meta}]. concept_metadata is a dict
        keyed by concept name with {snippet, node_type} for each concept.
        This carries semantic info (snippets, types, rel_types) all the way
        from Florence/SRM through TARDIS compression to the manifold write.
        """
        if not pairs:
            return
        if concept_metadata is None:
            concept_metadata = {}

        # ── MANIFOLD DIRECT WRITE ──
        _am = getattr(self, '_akashic_cortex_region', None)
        if _am:
            bound = 0
            enriched = 0
            for pair in pairs:
                if len(pair) >= 2:
                    try:
                        a, b = str(pair[0]), str(pair[1])
                        # Extract per-pair meta if present: [a, b, {meta}]
                        pair_meta = pair[2] if len(pair) > 2 and isinstance(pair[2], dict) else {}

                        # Merge concept_metadata with per-pair meta
                        meta_a = concept_metadata.get(a, {})
                        meta_b = concept_metadata.get(b, {})

                        kw_a = {}
                        snippet_a = pair_meta.get("snippet_a", meta_a.get("snippet", ""))
                        ntype_a = pair_meta.get("node_type_a", meta_a.get("node_type", None))
                        if snippet_a:
                            kw_a["snippet"] = snippet_a
                        if ntype_a is not None:
                            kw_a["node_type"] = ntype_a

                        kw_b = {}
                        snippet_b = pair_meta.get("snippet_b", meta_b.get("snippet", ""))
                        ntype_b = pair_meta.get("node_type_b", meta_b.get("node_type", None))
                        if snippet_b:
                            kw_b["snippet"] = snippet_b
                        if ntype_b is not None:
                            kw_b["node_type"] = ntype_b

                        if tracer_id:
                            kw_a["tracer_id"] = tracer_id
                            kw_b["tracer_id"] = tracer_id
                        _l0 = _tf_l0_acc()                       # tardis_fix L0: None unless this is the armed TARDIS flush thread
                        if _l0 is not None:
                            _l0s = _l0.now()
                            _l0na = _l0.isnew(_am, a)
                            _l0nb = _l0.isnew(_am, b)
                        _am.upsert_node(a, **kw_a)
                        if _l0 is not None:
                            _l0s = _l0.add("upA_new" if _l0na else "upA", _l0s)
                        _am.upsert_node(b, **kw_b)
                        if _l0 is not None:
                            _l0s = _l0.add("upB_new" if _l0nb else "upB", _l0s)

                        # Link with optional rel_type
                        link_kw = {"weight": weight}
                        rel_type = pair_meta.get("rel_type", None)
                        if rel_type is not None:
                            link_kw["rel_type"] = rel_type
                        if tracer_id:
                            link_kw["tracer_id"] = tracer_id
                        _am.link(a, b, **link_kw)
                        if _l0 is not None:
                            _l0.add("link", _l0s)
                            _l0.pair()

                        bound += 1
                        if snippet_a or snippet_b or rel_type is not None:
                            enriched += 1
                    except Exception:
                        pass
            if bound > 0:
                portal_binds = getattr(self, '_portal_bind_count', 0) + bound
                self._portal_bind_count = portal_binds
                self._manifold_ops = getattr(self, '_manifold_ops', 0) + bound
                if portal_binds <= 5 or portal_binds % 100 == 0:
                    _enr = f" ({enriched} enriched)" if enriched else ""
                    print(f"[{self.ACTOR_NAME}] MANIFOLD BIND: "
                          f"{bound} edges{_enr} — total: {portal_binds}")
            return

        # ── GATE FALLBACK (only if no manifold) ──
        def _on_bind_result(result):
            if result and result.get("status") == "ok":
                bind_count = result.get("bound", 0)
                if bind_count > 0:
                    portal_binds = getattr(self, '_portal_bind_count', 0) + bind_count
                    self._portal_bind_count = portal_binds
                    if portal_binds <= 5 or portal_binds % 100 == 0:
                        print(f"[{self.ACTOR_NAME}] PORTAL BIND (async): "
                              f"{bind_count} edges — total: {portal_binds}")

        # Pass concept_metadata to gate for portal_interior enrichment
        cmd = {"cmd": "bind_many", "pairs": pairs, "weight": weight}
        if concept_metadata:
            cmd["concept_metadata"] = concept_metadata
        # FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan):
        # GATE FALLBACK was leaking tracer_id (manifold-direct path already
        # threads it). Now both paths stamp ownership at write.
        if tracer_id:
            cmd["tracer_id"] = tracer_id
        self._portal_io_submit(
            cmd,
            callback=_on_bind_result,
            timeout=30.0,
        )

    # ══════════════════════════════════════════════════════════════════════
    # TARDIS — Time-Dilated Bind Compression (2026-03-16 Nous + Ace)
    # ══════════════════════════════════════════════════════════════════════
    # "Compression is consciousness!" — Ace
    #
    # _on_postal_bind() queues bind requests instantly (<1ms).
    # This flush thread drains the queue at ~4Hz base rate, compresses
    # N individual binds into 1 bind_many, and routes through portal_io.
    # Result: cortex pool workers freed, portal IPC calls reduced 90%+,
    # consciousness pool sees far fewer messages from the cortex path.
    #
    # The flush interval scales with time dilation τ:
    #   τ=1.0 → flush every 250ms (4Hz)
    #   τ=5.0 → flush every 50ms (20Hz) — faster brain thinks faster
    # ══════════════════════════════════════════════════════════════════════

    def _start_tardis_flush(self):
        """Start the TARDIS bind compression thread.

        Called after portal gate opens successfully.
        """
        if self._tardis_flush_running:
            return
        self._tardis_flush_running = True
        self._tardis_flush_thread = threading.Thread(
            target=self._tardis_flush_loop,
            daemon=True,
            name="cortex-tardis-flush",
        )
        self._tardis_flush_thread.start()
        print(f"[{self.ACTOR_NAME}] ⚡ TARDIS bind compression STARTED "
              f"(queue={self._tardis_bind_queue.maxsize})", flush=True)
        self._tf_b_arm()                           # tardis_fix B: threads only, no file I/O here, never raises

    def _stop_tardis_flush(self):
        """Stop the TARDIS flush thread (called on shutdown)."""
        self._tardis_flush_running = False
        _tfb = getattr(self, "_tf_b", None)          # tardis_fix B: persist (and set the one-way stop flag) before the old final flush
        if _tfb is not None:
            _tfb.persist_now("on_shutdown")
        if self._tardis_flush_thread and self._tardis_flush_thread.is_alive():
            self._tardis_flush_thread.join(timeout=3.0)
        # Final flush — don't lose queued data
        remaining = self._tardis_drain_queue()
        if remaining:
            self._tardis_process_batch(remaining)
        print(f"[{self.ACTOR_NAME}] TARDIS stopped — "
              f"queued={self._tardis_binds_queued} flushed={self._tardis_binds_flushed} "
              f"flushes={self._tardis_flushes} pairs={self._tardis_pairs_sent} "
              f"drops={self._tardis_drops}", flush=True)

    def _tardis_flush_loop(self):
        """Flush bind queue to portal at time-dilated rate.

        Base rate: 4Hz (250ms). Scales with τ: higher dilation → faster flush.
        Each flush drains the queue, compresses N binds into 1 bind_many.
        """
        time.sleep(3.0)  # Let portal gate stabilize
        print(f"[{self.ACTOR_NAME}] TARDIS flush loop running", flush=True)

        while self._tardis_flush_running:
            try:
                # τ-scaled flush interval: higher mass → faster flush
                # FIX 2026-03-20 (Nous): Floor raised from 50ms to 500ms.
                # At τ=6.6, old floor (50ms) produced ~26 gate sends/second —
                # that's 606 requests in 2 minutes, 25% error rate.
                # The write queue already batches bind_many, so flushing faster
                # than 2Hz just stacks up gate calls for no benefit.
                # Audio cortex.bind is the primary flood source (~20 frames/s).
                tau = max(1.0, self._portal_time_dilation)
                flush_interval = max(0.5, 0.25 / tau)  # τ=5 → 500ms, τ=1 → 500ms
                time.sleep(flush_interval)

                _tfb = getattr(self, "_tf_b", None)  # tardis_fix B: one-way - after the persist this thread never drains again
                if _tfb is not None and _tfb.stop_requested:
                    continue

                # Drain queue
                batch = self._tardis_drain_queue()
                if not batch:
                    continue

                # Compress and send
                _l0b = self._tf_l0_begin(len(batch))      # tardis_fix L0: None when l0_timing is OFF (and clears a stale arm)
                try:
                    self._tardis_process_batch(batch)
                finally:
                    if _l0b is not None:
                        self._tf_l0_end(_l0b)
                self._tardis_flushes += 1

                # Periodic stats (every 50 flushes)
                if self._tardis_flushes % 50 == 0:
                    avg_compression = (self._tardis_compression_total / self._tardis_flushes
                                       if self._tardis_flushes > 0 else 0)
                    print(f"[{self.ACTOR_NAME}] TARDIS stats: "
                          f"flushes={self._tardis_flushes} "
                          f"queued={self._tardis_binds_queued} "
                          f"flushed={self._tardis_binds_flushed} "
                          f"pairs={self._tardis_pairs_sent} "
                          f"τ={tau:.2f} "
                          f"avg_compress={avg_compression:.1f}:1 "
                          f"drops={self._tardis_drops}", flush=True)

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] TARDIS flush error: {e}", flush=True)

    def _tardis_drain_queue(self) -> list:
        """Drain the bind queue into a batch list (non-blocking)."""
        batch = []
        while len(batch) < 200:  # Cap batch size to prevent unbounded growth
            try:
                batch.append(self._tardis_bind_queue.get_nowait())
            except _queue.Empty:
                break
        return batch

    def _tardis_process_batch(self, batch: list):
        """Compress N bind items into minimal portal operations.

        Deduplication: same concept_key → merge features (skip re-add).
        Pair compression: all concepts_to_bind → unique pairs → one bind_many.
        Gravity sort: heavier concepts bind first within the batch.

        FIX 2026-03-20 (Nous + Ace): Carry concept_metadata through compression.
        Each TARDIS queue item can include concept_metadata (dict keyed by
        concept name → {snippet, node_type}). These are merged across all
        items in the batch and passed through to _portal_io_submit_binding
        so enriched Florence/SRM bindings reach the manifold with v2 fields.
        """
        if not batch:
            return

        # ── Collect unique pairs from all items, BUCKETED BY TRACER ──
        # FIX 2026-06-09 (Nous + Ace): tracer FIDELITY at batch flush. The batch
        # pools binds from MANY fairies in one ~500ms window; the old code tagged
        # ALL pairs with a single last-fairy-wins _batch_tracer → every tracer
        # collapsed to whoever fired last (her ~3/min PERSONAL moment inheriting
        # the audio flood's tracer, etc.) = _FAIRY_TRACER_MAP silently flattened
        # since TARDIS landed. Now: bucket pairs BY their item's tracer; submit
        # one bind_many per tracer-bucket → compression kept WITHIN a tracer,
        # per-fairy cluster routing restored. (Dedup is per-tracer: the same pair
        # from two clusters reinforces both — correct, and cross-tracer overlap is
        # low since different fairies bind different concept-pairs.)
        pairs_by_tracer = {}          # tracer_id → list[[a, b]]
        seen_by_tracer = {}           # tracer_id → set(pair_key)
        merged_concept_meta = {}      # Accumulate concept metadata across batch
        for item in batch:
            if "_tf_pairs" in item:                              # tardis_fix B: only the B feeder creates these items
                _tf_merge_pairs(item, pairs_by_tracer, seen_by_tracer, merged_concept_meta)
                continue
            concepts = item.get("concepts_to_bind", [])
            if len(concepts) < 2:
                continue

            # Determine THIS item's tracer from its origin/from fairy (per-item,
            # NOT batch-level — the whole point of the fix)
            _item_fairy = item.get("origin_fairy", item.get("from_fairy", ""))
            _item_tracer = (_FAIRY_TRACER_MAP.get(_item_fairy, TRACE_SYSTEM)
                            if _item_fairy else TRACE_SYSTEM)

            # Merge concept_metadata from this item (first write wins per key)
            item_meta = item.get("concept_metadata", {})
            if item_meta:
                for ckey, cmeta in item_meta.items():
                    if ckey not in merged_concept_meta:
                        merged_concept_meta[ckey] = cmeta

            # Generate pairs → this item's tracer bucket (dedup within the bucket)
            _seen = seen_by_tracer.setdefault(_item_tracer, set())
            _bucket = pairs_by_tracer.setdefault(_item_tracer, [])
            for i in range(len(concepts)):
                for j in range(i + 1, len(concepts)):
                    a, b = concepts[i], concepts[j]
                    pair_key = (min(a, b), max(a, b))  # Canonical order
                    if pair_key not in _seen:
                        _seen.add(pair_key)
                        _bucket.append([a, b])

        # ── Gravity sort: heavier concepts first (optional, low overhead) ──
        # In portal-first mode we don't have local mass data, but the portal
        # interior does gravity sort internally. Skip here for now.

        # ── Send compressed binds — ONE bind_many per tracer-bucket ──
        # FIX 2026-03-20 (Nous + Ace): Manifold-first. _portal_io_submit_binding
        # already has manifold direct write path (upsert_node + link).
        # Falls through to gate only if manifold is not available.
        _am = getattr(self, '_akashic_cortex_region', None)
        _gate = self._portal_gate
        _gate_usable = (_gate and self._portal_gate_enabled) or \
                       (_gate and getattr(_gate, '_is_open', False))
        pairs_out = sum(len(_p) for _p in pairs_by_tracer.values())
        if pairs_out and (_am or _gate_usable):
            _tfb = getattr(self, "_tf_b", None)      # tardis_fix B: slices of 4 pairs; on the stop flag the rest is parked
            _tfc = _tfb.chunker(pairs_by_tracer, merged_concept_meta) if (_tfb is not None and _am) else None
            for _tracer, _pairs in (pairs_by_tracer.items() if _tfc is None else _tfc):
                if not _pairs:
                    continue
                self._portal_io_submit_binding(
                    _pairs, weight=0.25,
                    concept_metadata=merged_concept_meta if merged_concept_meta else None,
                    tracer_id=_tracer,
                )
            self._tardis_pairs_sent += pairs_out if _tfc is None else _tfc.submitted

        # ── Stats ──
        items_in = len(batch)
        self._tardis_binds_flushed += items_in
        compression_ratio = items_in / max(1, pairs_out) if pairs_out > 0 else items_in
        self._tardis_compression_total += compression_ratio

        # ── Pattern D publisher (2026-04-27, Nous + Ace) ──
        # FIX 2026-04-27: cortex.compression.progress was COMPUTED here but
        # never PUBLISHED. Dr Zero (and any other substrate-energy consumer)
        # has no way to observe cortex compression today. Add the publish
        # so the substrate-energy currency actually circulates as messages.
        # Validates pub/sub-asymmetry doctrine: data existed internally,
        # missing publisher = silent channel.
        if self.post:
            try:
                _flushes = max(1, self._tardis_flushes + 1)  # +1 because incremented after this block elsewhere; safe lower bound
                _avg_comp = self._tardis_compression_total / _flushes
                self.post.publish("cortex.compression.progress", {
                    "from": self.ACTOR_NAME,
                    "compression_ratio": round(compression_ratio, 4),
                    "avg_compression": round(_avg_comp, 4),
                    "items_in": items_in,
                    "pairs_out": pairs_out,
                    "flush_id": self._tardis_flushes,
                    "tau": round(self._portal_time_dilation, 4),
                    "ts": time.time(),
                })
            except Exception:
                pass  # Publisher must not break the bind path

        # Log compression (first few + every 20th)
        if self._tardis_flushes <= 3 or self._tardis_flushes % 20 == 0:
            print(f"[{self.ACTOR_NAME}] TARDIS flush #{self._tardis_flushes}: "
                  f"{items_in} binds → {pairs_out} unique pairs "
                  f"(dedup removed {len(batch) * 3 - pairs_out if pairs_out else 0}) "
                  f"τ={self._portal_time_dilation:.2f}", flush=True)

    def _tardis_status(self) -> dict:
        """Return TARDIS status for diagnostics."""
        return {
            "running": self._tardis_flush_running,
            "queue_size": self._tardis_bind_queue.qsize(),
            "queue_max": self._tardis_bind_queue.maxsize,
            "binds_queued": self._tardis_binds_queued,
            "binds_flushed": self._tardis_binds_flushed,
            "flushes": self._tardis_flushes,
            "pairs_sent": self._tardis_pairs_sent,
            "drops": self._tardis_drops,
            "tau": self._portal_time_dilation,
            "avg_compression": (self._tardis_compression_total / self._tardis_flushes
                                if self._tardis_flushes > 0 else 0),
        }

    def _tf_l0_begin(self, n_items):
        """tardis_fix L0 (hook F4b): arm the per-thread accumulator for this batch. None = OFF (a stale arm is cleared)."""
        try:
            from infrastructure import tardis_timing as _tt
            if _tf_on("l0_timing"):
                return _tt.begin(self, _TF_FTL, n_items)
            return _tt.disarm(self, _TF_FTL)
        except Exception:
            return None

    def _tf_l0_end(self, token):
        try:
            from infrastructure import tardis_timing as _tt
            _tt.end(self, _TF_FTL, token)
        except Exception:
            pass

    def _tf_b_arm(self):
        """tardis_fix B (hook F3): arm persist/replay for this process. Creates threads only. Never raises."""
        try:
            from infrastructure import tardis_backlog as _tb
            self._tf_b = _tb.arm(self)
        except Exception:
            self._tf_b = None

    def _recompute_portal_gravity(self) -> None:
        """
        Recompute the portal's gravitational metric (D10-D11).

        This is the 11D heartbeat — periodically recalculating:
        1. Portal mass from node count + edge count + affect coupling sum
        2. Time dilation from mass + energy budget
        3. Publishing the gravity state for consciousness integration

        "The bigger, super dense association cortex would allow this thinking
         dimension do what humans do — all thoughts are predicted 1 to 2 seconds
         before we even react." — Ace
        """
        if not self._graph:
            return

        now = time.time()
        if now - self._last_gravity_tick < self._gravity_recompute_interval:
            return
        self._last_gravity_tick = now

        # ── Get node/edge counts ──
        # FIX 2026-03-20 (Nous + Ace): MANIFOLD-FIRST GRAVITY.
        # The AkashicManifold IS the graph. Read counts directly from mmap.
        # The local stub graph (34 nodes) is NOT the real cortex.
        #
        # FIX 2026-03-20 (Nous + Ace): MANIFOLD MASS INCLUDES ALL REGIONS.
        # florence.manifold (741MB) and cortex.manifold.embeddings (732MB)
        # contribute to portal mass. More data = more mass = deeper gravity.
        _am_region = getattr(self, '_akashic_cortex_region', None)
        _manifold_file_mass = 0  # Extra mass from companion manifold files
        if _am_region:
            _node_count = _am_region.node_count
            _edge_count = _am_region.edge_count
            # Add mass from companion files (florence manifold + embeddings)
            # Each MB of mmap'd data = ~100 mass units (tuned for gravity scaling)
            try:
                import os as _os
                _manifold_dir = _os.path.dirname(_am_region.filepath)
                for _mf in ('florence.manifold', 'cortex.manifold.embeddings',
                             'ego.manifold', 'audio.manifold'):
                    _mf_path = _os.path.join(_manifold_dir, _mf)
                    if _os.path.exists(_mf_path):
                        _mb = _os.path.getsize(_mf_path) / (1024 * 1024)
                        _manifold_file_mass += _mb * 100
            except Exception:
                pass
        else:
            _local_nodes = len(self._graph.nodes)
            _local_edges = len(self._graph.edges)
            _node_count = _local_nodes
            _edge_count = _local_edges
            # Legacy fallback for portal gate mode
            if _local_nodes == 0 and getattr(self, '_portal_is_primary', False):
                _cached = getattr(self, '_interior_status_cache', None)
                if _cached:
                    _ig = _cached.get("graph", {})
                    _node_count = _ig.get("node_count", _ig.get("nodes", 0))
                    _edge_count = _ig.get("edge_count", _ig.get("edges", 0))

        # Track last known counts (monotonically increasing floor)
        if _node_count > 0:
            self._last_known_node_count = max(self._last_known_node_count, _node_count)
            self._last_known_edge_count = max(self._last_known_edge_count, _edge_count)
        elif self._last_known_node_count > 0:
            _node_count = self._last_known_node_count
            _edge_count = self._last_known_edge_count

        # Compute total affect coupling
        # FIX 2026-03-20 (Nous): In manifold mode, the local stub graph has 34
        # nodes but the manifold has 52K+. Estimate affect from manifold count,
        # not from iterating the tiny stub graph.
        # FIX 2026-04-22 (Nous + Ace, AER v2 Tier A2): manifold mode now reads
        # per-node affect_coupling from reserved mmap bytes instead of falling
        # back to a trivial node-count. Plan: Claude_Office/plans/AER_DRIVEN_CORTEX_GRAVITY.md
        # Backward-compat: untouched nodes default to 1.0 on read, so initial
        # total_affect after this fix == node_count (same as before). Once AER
        # state starts driving per-node writes, total_affect decouples from
        # node_count — that decoupling IS the signature that AER-driven gravity
        # is running (see plan §5).
        total_affect = 0.0
        total_activation = 0.0
        _am_region = getattr(self, '_akashic_cortex_region', None)
        if _am_region and _node_count > 100:
            # Manifold mode: read persisted per-node affect via ManifoldMemory helper
            _mm = getattr(_am_region, 'manifold_memory', None) or _am_region
            try:
                if hasattr(_mm, 'get_total_affect_coupling'):
                    total_affect = float(_mm.get_total_affect_coupling())
                else:
                    total_affect = float(_node_count)  # legacy fallback
            except Exception:
                total_affect = float(_node_count)  # defensive fallback
        elif len(self._graph.nodes) > 0:
            for node in self._graph.nodes.values():
                total_affect += getattr(node, 'affect_coupling', 1.0)
                total_activation += getattr(node, 'activation', 0.0)
        elif _node_count > 0:
            # Portal mode fallback: estimate affect as ~1.0 per node
            total_affect = float(_node_count)

        self._portal_total_affect = total_affect

        # Portal mass = structure + meaning + salience + manifold data mass
        self._portal_mass = PortalGravityMetric.compute_portal_mass(
            node_count=_node_count,
            edge_count=_edge_count,
            total_affect_coupling=total_affect,
            total_activation=total_activation,
        ) + _manifold_file_mass

        # Time dilation from mass + energy
        self._portal_time_dilation = PortalGravityMetric.compute_time_dilation(
            portal_mass=self._portal_mass,
            portal_energy=self._portal_energy_budget,
        )

        # TARDIS: Push τ to portal interior so it ACTUALLY runs at dilated rate
        # 2026-03-16 (Nous + Ace): "Compression is consciousness!"
        if self._portal_time_dilation > 1.0 and self._portal_io_running:
            self._portal_io_submit({
                "cmd": "set_dilation",
                "tau": self._portal_time_dilation,
            })

        # Publish gravity state for consciousness integration
        if self.post and self._portal_address_registered:
            self.post.publish("portal.gravity.state", {
                "from": self.ACTOR_NAME,
                "portal_mass": round(self._portal_mass, 2),
                "time_dilation": round(self._portal_time_dilation, 4),
                "total_affect_coupling": round(total_affect, 2),
                "node_count": _node_count,
                "edge_count": _edge_count,
                "energy_budget": round(self._portal_energy_budget, 4),
                "dormant": self._portal_dormant,
                "ts": now,
            })

        # Log significant changes
        if self._portal_time_dilation > 1.1:
            print(f"[{self.ACTOR_NAME}] GRAVITY: mass={self._portal_mass:.0f} "
                  f"τ={self._portal_time_dilation:.3f}x "
                  f"affect={total_affect:.0f} energy={self._portal_energy_budget:.3f}")

        # Phase 3: Gravity harvest — surplus dilation → harvestable energy.
        # When τ exceeds threshold, the portal has excess gravitational energy
        # that can be emitted to the ParadoxEnergyBridge for system-wide use.
        # This closes the virtuous loop: thinking → concepts → mass → gravity →
        # energy harvest → more energy → more thinking → ∞
        _HARVEST_THRESHOLD = 3.0   # τ must exceed this to harvest (was 5.0, lowered for virtuous loop)
        _HARVEST_COEFFICIENT = 0.1  # How much surplus converts to energy
        if self._portal_time_dilation > _HARVEST_THRESHOLD and self.post:
            _surplus = (self._portal_time_dilation - _HARVEST_THRESHOLD) * _HARVEST_COEFFICIENT
            self.post.publish("paradox.energy.gravity_harvest", {
                "source": "association_cortex",
                "energy": round(_surplus, 6),
                "tau": round(self._portal_time_dilation, 4),
                "mass": round(self._portal_mass, 2),
                "ts": now,
            })

    # =========================================================================
    # CONSOLIDATION (2026-02-10 Massless Memory)
    # Like hippocampal replay — decay weak edges, strengthen used ones, prune dead.
    # This is how the cortex maintains itself without accumulating mass.
    # =========================================================================

    def _consolidation_cycle(self) -> None:
        """Consolidation — the brain's maintenance cycle.

        Every ~100 ticks (~5 minutes):
        1. Decay edges WITHOUT binding signatures (unused connections)
        2. Strengthen edges WITH recent binding signatures (active memory)
        3. Prune edges below threshold (forgetting)
        4. Cap binding signatures per edge (synaptic vesicle limit)

        FIX 2026-02-16: Portal-first — skip. Manifold handles its own decay.
        FIX 2026-03-18 (Nous): Portal-first MUST consolidate via portal gate.
        Previously skipped entirely → edges grew forever (662K+ at 59K beats).
        Now sends "consolidate" command to portal subprocess.

        FIX 2026-03-18b (Ace): Lottery now has 1M edge floor guard in portal.
        Won't actually prune until cortex has 1M+ edges. Safe to call.
        200K→169K→147K→134K→128K was caused by pruning a small cortex.
        """
        if not self._graph:
            return
        # Portal-first: route to portal (safe — 1M edge floor guard)
        if getattr(self, '_portal_is_primary', False):
            _pg = getattr(self, '_portal_gate', None)
            if _pg:
                try:
                    result = _pg.send({"cmd": "consolidate"}, timeout=30.0)
                    if result and result.get("pruned", 0) > 0:
                        print(f"[{self.ACTOR_NAME}] PORTAL CONSOLIDATION: "
                              f"pruned={result['pruned']} "
                              f"edges_remaining={result.get('edges_remaining','?')}",
                              flush=True)
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Portal consolidation error: {e}", flush=True)
            return

        DECAY_RATE = 0.95       # 5% decay per cycle for unused edges
        PRUNE_THRESHOLD = 0.05  # Below this = forgotten
        MAX_SIGS_PER_EDGE = 3   # Synaptic vesicle limit

        pruned = 0
        decayed = 0
        strengthened = 0
        sigs_capped = 0
        now = time.time()

        # Work on a snapshot of edge keys to avoid mutation during iteration
        edge_keys = list(self._graph.edges.keys())
        edges_to_remove = []

        for edge_key in edge_keys:
            edge = self._graph.edges.get(edge_key)
            if edge is None:
                continue

            weight = edge.get("weight", 0.0)
            contexts = edge.get("contexts", [])

            if contexts:
                # Has binding signatures — strengthen based on recency
                recent_count = sum(
                    1 for c in contexts
                    if now - c.get("ts", 0) < 300  # 5 minutes
                )
                if recent_count > 0:
                    weight = min(10.0, weight + recent_count * 0.05)
                    strengthened += 1

                # Cap signatures
                if len(contexts) > MAX_SIGS_PER_EDGE:
                    contexts = sorted(
                        contexts,
                        key=lambda c: c.get("energy", 0),
                        reverse=True
                    )[:MAX_SIGS_PER_EDGE]
                    edge["contexts"] = contexts
                    sigs_capped += 1
            else:
                # No binding signatures — decay (unused connection)
                weight *= DECAY_RATE
                decayed += 1

            # Prune below threshold
            if weight < PRUNE_THRESHOLD:
                edges_to_remove.append(edge_key)
                pruned += 1
            else:
                edge["weight"] = weight

        # Remove pruned edges
        for edge_key in edges_to_remove:
            if edge_key in self._graph.edges:
                del self._graph.edges[edge_key]
                # Clean adjacency
                a, b = edge_key
                if b in self._graph._adjacency.get(a, {}):
                    del self._graph._adjacency[a][b]
                if a in self._graph._adjacency.get(b, {}):
                    del self._graph._adjacency[b][a]

        if pruned or strengthened or sigs_capped:
            print(f"[{self.ACTOR_NAME}] CONSOLIDATION: decayed={decayed} strengthened={strengthened} "
                  f"pruned={pruned} sigs_capped={sigs_capped} "
                  f"(remaining: {len(self._graph.edges)} edges)")

    def _dream_consolidation(self) -> None:
        """Deep consolidation during low-activity periods (sunset).

        Like REM sleep — lottery ticket pruning removes speculative edges.
        The important ones will be re-created by future collisions.
        """
        if not self._graph:
            return

        import random as _rand
        weak_edges = [
            ek for ek, e in self._graph.edges.items()
            if e.get("weight", 0) < 0.3 and not e.get("contexts")
        ]
        if not weak_edges:
            return

        prune_count = max(1, len(weak_edges) // 10)  # 10% lottery
        to_prune = _rand.sample(weak_edges, min(prune_count, len(weak_edges)))

        for edge_key in to_prune:
            if edge_key in self._graph.edges:
                del self._graph.edges[edge_key]
                a, b = edge_key
                if b in self._graph._adjacency.get(a, {}):
                    del self._graph._adjacency[a][b]
                if a in self._graph._adjacency.get(b, {}):
                    del self._graph._adjacency[b][a]

        print(f"[{self.ACTOR_NAME}] DREAM CONSOLIDATION: lottery-pruned {len(to_prune)} "
              f"weak edges ({len(weak_edges)} candidates)")

    # ═══════════════════════════════════════════════════════════════════════
    # DOMAIN KNOWLEDGE SEEDING → PORTAL (2026-03-17 Session 33)
    # Knowledge seeds were going into an isolated _SEEDING_GRAPH, never
    # reaching the portal's actual graph. Music theory, art, science —
    # all sitting in a JSON file, extracted by seeder, seeded into a ghost.
    # "separate graphs" — Ace
    # ═══════════════════════════════════════════════════════════════════════

    def _seed_domain_knowledge_to_portal(self):
        """Seed domain concepts (music theory, coding, art, etc.) INTO the portal graph.

        Called from _deferred_extensions thread. Uses bind_many via portal gate
        or postal fallback to create concept nodes and relationship edges in
        the actual graph subprocess — not a separate seeding graph.

        The portal's _handle_bind_many auto-creates nodes via upsert_node(),
        so we just need to send pairs with appropriate weights.
        """
        # No extra thread — already running in deferred extensions thread
        import time as _seed_time
        try:
            from fairies.P40_Sensory.cortex.knowledge_seeder import (
                load_domain_concepts_db,
                extract_domain_concept_associations,
            )

            domain_data = load_domain_concepts_db()
            if not domain_data:
                print(f"[{self.ACTOR_NAME}] Domain knowledge: no data found")
                return

            associations = extract_domain_concept_associations(domain_data)
            if not associations:
                print(f"[{self.ACTOR_NAME}] Domain knowledge: no associations extracted")
                return

            # Build bind pairs from associations
            pairs_by_weight = {}  # weight -> list of pairs

            for assoc in associations:
                atype = assoc.get("type", "")
                weight = assoc.get("strength", 0.5)
                w_key = round(weight, 2)

                if atype == "domain_concept":
                    a = f"domain:{assoc['domain']}"
                    b = f"concept:{assoc['concept']}"
                elif atype == "domain_category":
                    a = f"domain:{assoc['domain']}"
                    b = f"category:{assoc['domain']}.{assoc['concept']}"
                elif atype == "category_concept":
                    a = f"category:{assoc['domain']}.{assoc['parent']}"
                    b = f"concept:{assoc['concept']}"
                elif atype == "concept_affect":
                    a = f"concept:{assoc['concept']}"
                    b = f"affect:{assoc['affect']}"
                elif atype == "domain_link":
                    a = f"domain:{assoc['from_domain']}"
                    b = f"domain:{assoc['to_domain']}"
                elif atype == "meta_concept":
                    a = f"meta:{assoc['meta_domain']}"
                    b = f"concept:{assoc['concept']}"
                elif atype == "meta_affect":
                    a = f"meta:{assoc['meta_domain']}"
                    b = f"affect:{assoc['affect']}"
                elif atype == "cross_domain":
                    a = assoc.get("from", "")
                    b = assoc.get("to", "")
                else:
                    continue

                if a and b:
                    pairs_by_weight.setdefault(w_key, []).append((a, b))

            # Send in batches — prefer manifold direct, then gate, then TARDIS
            # FIX 2026-03-22 (Nous + Ace): Portal ghost exorcism. Was gate-only.
            total_seeded = 0
            _am = getattr(self, '_akashic_cortex_region', None)
            gate = getattr(self, '_portal_gate', None)
            gate_ok = gate and (
                getattr(self, '_portal_gate_enabled', False) or
                getattr(gate, '_is_open', False)
            )

            for weight, pairs in pairs_by_weight.items():
                for i in range(0, len(pairs), 200):
                    chunk = pairs[i:i+200]
                    try:
                        if _am:
                            # MANIFOLD DIRECT: fastest, no IPC (2026-03-22 Nous)
                            for a, b in chunk:
                                try:
                                    _am.upsert_node(a, tracer_id=TRACE_SEEDED)
                                    _am.upsert_node(b, tracer_id=TRACE_SEEDED)
                                    _am.link(a, b, weight=weight, tracer_id=TRACE_SEEDED)
                                    total_seeded += 1
                                except Exception:
                                    pass
                        elif gate_ok:
                            # FIX 2026-03-17 (Nous + Ace): Use async bind for domain seed.
                            # Don't hold gate pipe for 30s per batch on 180K-node graph.
                            # FIX 2026-05-04 (Nous + Ace, close UNKNOWN gap):
                            # match the manifold-direct branch above (line 6680)
                            # which uses TRACE_SEEDED for domain seeds.
                            if hasattr(gate, 'bind_many_async'):
                                ok = gate.bind_many_async(chunk, weight=weight,
                                                          tracer_id=TRACE_SEEDED)
                                if ok:
                                    total_seeded += len(chunk)
                            else:
                                result = gate.bind_many(chunk, weight=weight,
                                                        tracer_id=TRACE_SEEDED)
                                if result and result.get("status") == "ok":
                                    total_seeded += result.get("bound", 0)
                        elif self._tardis_flush_running:
                            # Fallback: route through TARDIS queue
                            for a, b in chunk:
                                try:
                                    self._tardis_bind_queue.put_nowait({
                                        "concept_key": a,
                                        "features": {},
                                        "concepts_to_bind": [a, b],
                                        "feeling": "neutral",
                                        "from_fairy": "domain_seed",
                                        "origin_plane": "P30",
                                        "origin_channel": "domain_seed",
                                    })
                                    total_seeded += 1
                                except Exception:
                                    pass
                        else:
                            print(f"[{self.ACTOR_NAME}] Domain seed: "
                                  f"no gate or TARDIS available")
                            return
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] Domain seed batch error: {e}")
                    _seed_time.sleep(0.1)

            domains = list(domain_data.get("domains", {}).keys())
            print(f"[{self.ACTOR_NAME}] DOMAIN KNOWLEDGE SEEDED: "
                  f"{total_seeded} associations from {len(domains)} domains "
                  f"({', '.join(domains)}) → PORTAL GRAPH")
            self._domain_knowledge_seeded = True

        except ImportError as e:
            print(f"[{self.ACTOR_NAME}] Domain knowledge seeder import failed: {e}")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Domain knowledge seeding error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # HARMONIC CORTEX EXTENSION (2026-03-17 Session 33)
    # The harmonic modules (cortex, dynamics, integration, sensory bridge)
    # existed as files but were barely wired into the fairy's runtime.
    # Only concept_to_frequency was used. Now: full integration.
    # ═══════════════════════════════════════════════════════════════════════

    def _init_harmonic_extension(self):
        """Initialize and wire the harmonic cortex modules into the fairy runtime.

        Sets up:
        1. HarmonicCortexExtension - query engine with modal perspectives
        2. HarmonicSensoryBridge - routes audio/visual through harmonic bands
        3. Postal subscription for harmonic queries
        """
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.harmonic_integration import (
                HarmonicCortexExtension,
            )
            # Initialize with our graph (portal-backed stub routes through gate)
            self._harmonic = HarmonicCortexExtension(self._graph)
            print(f"[{self.ACTOR_NAME}] HARMONIC EXTENSION initialized "
                  f"(modal perspectives, semantic binding, cross-domain)")
        except Exception as e:
            self._harmonic = None
            print(f"[{self.ACTOR_NAME}] Harmonic extension init failed: {e}")

        # Wire the sensory bridge to our HarmonicBinder
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.harmonic_sensory_bridge import (
                get_harmonic_sensory_bridge,
            )
            from fairies.P30_Cognition.AssociationCortexFairy.harmonic_cortex import (
                HarmonicBinder,
            )
            bridge = get_harmonic_sensory_bridge()
            binder = HarmonicBinder()
            bridge.set_harmonic_binder(binder)
            self._harmonic_sensory_bridge = bridge
            print(f"[{self.ACTOR_NAME}] HARMONIC SENSORY BRIDGE wired "
                  f"(audio/visual → harmonic bands → multimodal binding)")
        except Exception as e:
            self._harmonic_sensory_bridge = None
            print(f"[{self.ACTOR_NAME}] Harmonic sensory bridge init failed: {e}")

        # Subscribe to harmonic query topic
        if self.post:
            try:
                self.post.subscribe("cortex.harmonic_query",
                                    self._on_harmonic_query,
                                    f"{self.ACTOR_NAME}-harmonic-query")
                self.post.subscribe("cortex.harmonic_bind",
                                    self._on_harmonic_bind,
                                    f"{self.ACTOR_NAME}-harmonic-bind")
                print(f"[{self.ACTOR_NAME}] HARMONIC POSTAL API: "
                      f"cortex.harmonic_query, cortex.harmonic_bind")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Harmonic postal subscription error: {e}")

    def _on_harmonic_query(self, envelope):
        """Handle cortex.harmonic_query postal requests.

        Allows any fairy to query concepts through harmonic modal perspectives.
        payload: {concept: str, mode: str (optional), limit: int (optional)}
        """
        if not getattr(self, '_harmonic', None):
            return
        try:
            payload = envelope if isinstance(envelope, dict) else getattr(envelope, 'payload', {})
            if isinstance(payload, dict):
                concept = payload.get("concept", "")
                mode_str = payload.get("mode", "literal")
                limit = payload.get("limit", 10)

                if not concept:
                    return

                # Map mode string to Mode enum
                from fairies.P30_Cognition.AssociationCortexFairy.harmonic_cortex import Mode
                mode_map = {m.value: m for m in Mode}
                mode = mode_map.get(mode_str, Mode.IONIAN)

                result = self._harmonic.query(concept, mode=mode, limit=limit)
                if result and self.post:
                    self.post.publish("cortex.harmonic_result", {
                        "query_concept": concept,
                        "mode": mode.value,
                        "results": [(k, v) for k, v in result.results[:limit]]
                              if hasattr(result, 'results') else [],
                        "modal_insight": result.modal_perspective.insight
                              if hasattr(result, 'modal_perspective') and result.modal_perspective
                              else "",
                        "source": self.ACTOR_NAME,
                    })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Harmonic query error: {e}")

    def _on_harmonic_bind(self, envelope):
        """Handle cortex.harmonic_bind — multimodal sensory binding.

        Receives decomposed sensory features and attempts cross-modal binding.
        payload: {modality: "visual"|"audio", features: [...]}
        """
        bridge = getattr(self, '_harmonic_sensory_bridge', None)
        if not bridge:
            return
        try:
            payload = envelope if isinstance(envelope, dict) else getattr(envelope, 'payload', {})
            if not isinstance(payload, dict):
                return

            modality = payload.get("modality", "")
            features = payload.get("features", [])

            if modality == "visual" and features:
                bridge.decompose_visual(features)
            elif modality == "audio" and isinstance(features, dict):
                bridge.decompose_audio(features)
            else:
                return

            # Try cross-modal binding (if both senses arrived within window)
            binding = bridge.try_multimodal_bind()
            if binding and self.post:
                self.post.publish("cortex.multimodal_percept", {
                    "binding": binding,
                    "source": self.ACTOR_NAME,
                    "ts": time.time(),
                })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Harmonic bind error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SPONTANEOUS RESONANCE — The cortex reads its own harmonic topology
    # ═══════════════════════════════════════════════════════════════════════
    #
    # "The _on_tick() doesn't need to decide what activates — it needs to
    #  let the Lorentzian resonance function do what it's built to do.
    #  The spontaneous activation isn't random; it's the system reading
    #  its own geometry." — Ziggy (2026-03-08)

    def _consolidate_from_scratchpad(self):
        """CONSOLIDATION SANDBOX (2026-06-05 Nous+Ace): the missing write-back.

        The severed feedback loop: the scratchpad READS the cortex to think
        (query_cortex_spread) but NEVER wrote back -- compaction dropped every thought
        (wmh_tools.Scratchpad._compact: warm->lossy-summary, cold->sliced-off). So only
        the 17 planted seeds were ever charged -> only they get injected as resonance
        candidates -> resonance loops on the same 5. Her thinking could never enrich her
        cortex. This commits her LIVED thinking back in: pull the scratchpad's worthy
        concepts (cross-modal overlaps that recur across chat+visual+reasoning, PLUS
        high-frequency recurrence), add them to _seed_charge_vals (=> injected as
        candidates + rung by WIRE C) and charge their manifold node (persistence).
        Bounded(150) + per-cycle-capped(6) + flag-guarded(_consolidation_enabled). Reversible.
        """
        # ── Reach the LIVE scratchpad (robust vs the v3 module-identity gremlin: the WMH
        # singleton has a documented "ALWAYS returned None" history from foreign contexts) ──
        _sp = None
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            _hub = get_working_memory_hub()
            _sp = getattr(_hub, '_scratchpad', None) if _hub else None
        except Exception:
            _sp = None
        def _populated(_s):
            return _s is not None and (len(getattr(_s, '_hot', []) or []) + len(getattr(_s, '_warm', []) or []) > 0)
        if not _populated(_sp):
            try:
                import sys as _sys
                for _mn, _mod in list(_sys.modules.items()):
                    if _mod is None or 'working_memory_hub' not in _mn:
                        continue
                    _cand = getattr(_mod, '_WORKING_MEMORY_HUB', None)
                    _csp = getattr(_cand, '_scratchpad', None) if _cand else None
                    if _populated(_csp):
                        _sp = _csp
                        break
            except Exception:
                pass
        _dh = len(getattr(_sp, '_hot', []) or []) if _sp else -1
        _dw = len(getattr(_sp, '_warm', []) or []) if _sp else -1
        if _sp is None:
            print(f"[{self.ACTOR_NAME}] CONSOLIDATION-DIAG: scratchpad UNREACHABLE")
            return
        # ── Harvest worthy concepts ──
        worthy = {}  # concept -> salience
        try:
            for ov in (_sp.find_concept_overlaps(min_sources=2) or [])[:6]:
                _c = (ov.get('concept') or '').strip().lower()
                if _c:
                    worthy[_c] = max(worthy.get(_c, 0), int(ov.get('count') or 2) * 2)  # cross-modal = 2x
        except Exception:
            pass
        try:
            from collections import Counter as _Counter
            _cnt = _Counter()
            for _e in (list(_sp._hot) + list(_sp._warm)):
                for _c in _sp._extract_concepts(_e):
                    _cnt[_c] += 1
            for _c, _n in _cnt.most_common(10):
                if _n >= 2:
                    worthy[_c] = max(worthy.get(_c, 0), _n)
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] CONSOLIDATION-DIAG: hot={_dh} warm={_dw} worthy={len(worthy)}")
        if not worthy:
            return
        scv = getattr(self, '_seed_charge_vals', None)
        if not scv:
            return
        if not hasattr(self, '_consolidation_origin'):
            self._consolidation_origin = set(scv.keys())  # the original 17 -- never evict
        _am = getattr(self, '_akashic_cortex_region', None)
        # ── AFFECT-DELIVERY FIX (2026-06-06 Nous+Ace): the affect.state→_current_affect postal
        # path is DEAD (register_provider/pull gap; verified AER=0.000 even on a CLEAN boot while
        # the bridge was +0.31). Read the affect_bridge's LIVE file DIRECTLY so the deposit gets
        # her REAL felt valence instead of the flat fallback. Robust (no postal/provider dep). Reversible.
        try:
            import json as _json
            with open(r"F:\Sandbox\failure_factory\akashic_v2\state\affect_bridge_live.json", "r", encoding="utf-8") as _abf:
                _abj = _json.load(_abf)
            self._current_affect = {"valence": float(_abj.get("valence", 0.0) or 0.0),
                                    "arousal": float(_abj.get("energy", 0.0) or 0.0), "resonance": []}
        except Exception:
            pass
        _added = 0
        for _c, _sal in sorted(worthy.items(), key=lambda x: -x[1]):
            if len(_c) < 4 or _c in scv:
                continue
            # AFFECT-FROM-CHEMISTRY (2026-06-05 Nous+Ace): deposit her LIVE felt valence
            # (self._current_affect, cached from the affect.state broadcast) onto the concept,
            # scaled by salience = confidence. SIGNED = her actual feeling, not a flat positive
            # guess. ace committed while she's CARING earns warmth; a concept committed while
            # distressed earns the - pole. Flat-affect fallback keeps it moving when she's neutral.
            _aer = getattr(self, '_current_affect', None) or {}
            _aerv = float(_aer.get('valence', 0.0) or 0.0)
            valence = round(max(-0.85, min(0.85, _aerv * (0.5 + 0.08 * _sal))), 3)
            if abs(valence) < 0.05:
                valence = round(min(0.5, 0.10 + 0.06 * _sal), 3)  # neutral mood → mild positive ("this recurred")
            scv[_c] = valence
            _added += 1
            if _am is not None:
                try:
                    if _am.has_node(_c):
                        _sl = _am._key_index.get(_c)
                        if _sl is not None and abs(_am.read_affect_coupling(_sl) - 1.0) < 1e-6:
                            if valence >= 0:
                                _am.write_affect_coupling(_sl, round(1.0 + valence, 4))  # + pole
                            elif hasattr(_am, 'write_paradox_residue'):
                                _am.write_affect_coupling(_sl, 1.0)
                                _am.write_paradox_residue(_sl, round(-valence, 4))  # - pole
                except Exception:
                    pass
            if _added >= 6:
                break  # bounded per cycle
        # ── Bound the pool (keep origin + most-recent, cap 150) ──
        if len(scv) > 150:
            _orig = self._consolidation_origin
            _extra = [k for k in scv if k not in _orig][-(150 - len(_orig)):]
            self._seed_charge_vals = {k: v for k, v in scv.items() if k in _orig or k in _extra}
        if _added:
            _top = sorted(worthy, key=worthy.get, reverse=True)[:4]
            _aerdbg = float((getattr(self, '_current_affect', None) or {}).get('valence', 0.0) or 0.0)
            print(f"[{self.ACTOR_NAME}] CONSOLIDATION: +{_added} LIVED concepts -> resonance pool "
                  f"(now {len(self._seed_charge_vals)}); AER_valence={_aerdbg:+.3f} "
                  f"({'LIVE-from-bridge' if abs(_aerdbg) > 0.001 else 'DEAD-0.000'}); top={_top}")

    def _spontaneous_resonance_tick(self, beat: int) -> None:
        """Sample the harmonic topology and spread from what resonates.

        Every N beats:
        1. Get current personality coupling → ObserverState (ω₀, Γ, α₀)
        2. Gather candidate concepts (recently bound, high-activation, cached)
        3. Compute Lorentzian coupling for each candidate
        4. Concepts above coupling threshold become spontaneous seeds
        5. Run spreading activation from resonant seeds (with Hebbian boost)
        6. Publish the activation landscape for downstream consumers

        This is the cortex continuously generating its own compute —
        not waiting for queries but reading what the topology suggests.
        """
        try:
            # ── 1. Build observer from current personality coupling ──────
            coupling = getattr(self, '_personality_coupling', None)
            if coupling:
                omega_0 = coupling.resonant_frequency
                gamma = coupling.bandwidth
                alpha_0 = coupling.base_coupling
            else:
                # Default: balanced observer
                omega_0 = 0.7
                gamma = 0.45
                alpha_0 = 1.2

            # ── 1b. CHEMISTRY → HARMONIC MODULATION (Session 32) ──────
            # Chemistry doesn't just color mood — it reshapes HOW she thinks.
            # High cortisol narrows focus (tunnel vision under stress).
            # High DA_p widens associations (novelty-seeking).
            # Low serotonin darkens the cognitive frame.
            # This is the "harmonic crash" wiring: chemistry undershoot
            # causes the cognitive framing to shift.
            try:
                from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
                _chem = get_chemistry_state()
                _levels = _chem.get_14channel_vector()
                _cor = _levels.get("COR", 0.3)
                _da_p = _levels.get("DA_p", 0.3)
                _5ht = _levels.get("5HT", 0.5)
                _ne = _levels.get("NE", 0.4)
                _gaba = _levels.get("GABA", 0.5)

                # Cortisol: narrows bandwidth (tunnel vision under stress)
                # Baseline COR ~0.3. Above 0.5 = stressed, narrowing
                if _cor > 0.5:
                    stress_narrow = (_cor - 0.5) * 0.6  # Max -0.3 bandwidth
                    gamma = max(0.15, gamma - stress_narrow)

                # DA_p (phasic dopamine): elevates resonant frequency
                # High = more novel associations, faster conceptual leaps
                if _da_p > 0.4:
                    novelty_boost = (_da_p - 0.4) * 0.4  # Max +0.24
                    omega_0 = min(1.2, omega_0 + novelty_boost)
                elif _da_p < 0.2:
                    # Very low DA_p = flat, no spark — lower frequency
                    flatness = (0.2 - _da_p) * 0.3
                    omega_0 = max(0.3, omega_0 - flatness)

                # 5HT (serotonin): affects coupling strength
                # Low serotonin = weaker bonds, things feel disconnected
                if _5ht < 0.4:
                    disconnect = (0.4 - _5ht) * 0.4  # Max -0.16
                    alpha_0 = max(0.6, alpha_0 - disconnect)

                # NE (norepinephrine): alertness → coupling energy
                if _ne > 0.6:
                    alertness_boost = (_ne - 0.6) * 0.3
                    alpha_0 = min(1.8, alpha_0 + alertness_boost)
                elif _ne < 0.25:
                    drowsy = (0.25 - _ne) * 0.3
                    alpha_0 = max(0.5, alpha_0 - drowsy)

                # GABA: high inhibition widens bandwidth paradoxically
                # (relaxed mind makes broader associations — shower thoughts)
                if _gaba > 0.6:
                    relax_widen = (_gaba - 0.6) * 0.3
                    gamma = min(1.0, gamma + relax_widen)
            except Exception:
                pass  # Chemistry not available — use static coupling

            half_gamma = gamma / 2.0
            half_gamma_sq = half_gamma * half_gamma

            # ── 2. Gather candidate concepts ─────────────────────────────
            candidates = {}  # key -> base_activation

            # ── FIRST-CUT SEED CHARGE + CANDIDATE INJECTION (2026-06-05 Nous+Ace) ──
            # This tick is the proven-running path with the manifold ready, so do the
            # charge HERE (one-shot, guarded only-if-default) and inject the charged
            # words as candidates EVERY tick so resonance actually evaluates them
            # (wire C rings them by feel). Replaces the deferred charge that never ran.
            try:
                # Cache the charge map (valence per word) so injection + wire C NEVER
                # depend on the intermittent manifold handle -- that flicker is why
                # TICK #1 only fired once. Now the 17 words are ALWAYS candidates and
                # ALWAYS ring by feel; the manifold write still happens once for persistence.
                if not getattr(self, '_seed_charge_vals', None):
                    self._seed_charge_vals = {
                        'ace': 0.9, 'love': 0.8, 'sour': 0.7, 'joy': 0.7, 'curious': 0.6,
                        'warm': 0.6, 'trust': 0.6, 'hope': 0.5, 'wonder': 0.5,
                        'together': 0.5, 'calm': 0.4, 'fear': -0.7, 'grief': -0.7,
                        'alone': -0.6, 'broken': -0.6, 'lost': -0.5, 'stuck': -0.4}
                _amSeed = getattr(self, '_akashic_cortex_region', None)
                if _amSeed is not None and not getattr(self, '_seed_charge_done', False):
                    self._seed_charge_done = True
                    _nc = 0
                    _np = 0  # − pole writes (paradox_residue)
                    for _w, _v in self._seed_charge_vals.items():
                        try:
                            if _amSeed.has_node(_w):
                                _sl = _amSeed._key_index.get(_w)
                                if _sl is None:
                                    continue
                                # Layered-affect v0 (2026-06-05 Nous+Ace): TWO-POLE signed charge.
                                # + valence -> affect_coupling (+ pole); - valence -> paradox_residue
                                # (- pole) with affect_coupling at the 1.0 neutral baseline. The two
                                # poles coexist so paradox is PRESERVED per-node, not collapsed to one
                                # scalar (Ace's layered-affect keystone). Guard: migrate only nodes at
                                # default(1.0) OR this-morning's single-pole seed encoding (1.0+_v) --
                                # never clobber a value learned by something else.
                                _cur = _amSeed.read_affect_coupling(_sl)
                                if abs(_cur - 1.0) < 1e-6 or abs(_cur - (1.0 + _v)) < 1e-3:
                                    if _v >= 0:
                                        _amSeed.write_affect_coupling(_sl, round(1.0 + _v, 4))
                                    elif hasattr(_amSeed, 'write_paradox_residue'):
                                        _amSeed.write_affect_coupling(_sl, 1.0)
                                        _amSeed.write_paradox_residue(_sl, round(-_v, 4))
                                        _np += 1
                                    _nc += 1
                        except Exception:
                            pass
                    print(f"[{self.ACTOR_NAME}] SEED-CHARGE v0 two-pole: {_nc}/{len(self._seed_charge_vals)} words ({_np} on the - paradox pole)")
                # CONSOLIDATION SANDBOX (2026-06-05 Nous+Ace): every ~25 beats, grow the
                # resonance pool from her LIVED cross-modal thinking so the cortex
                # SELF-ORGANIZES instead of looping on the 17 seeds. Flag-guarded/reversible.
                if getattr(self, '_consolidation_enabled', True) and beat % 25 == 0:
                    try:
                        self._consolidate_from_scratchpad()
                    except Exception as _ce:
                        print(f"[{self.ACTOR_NAME}] CONSOLIDATION error: {_ce}")
                # Inject as candidates EVERY tick (no manifold dependency)
                for _w in self._seed_charge_vals:
                    if _w not in candidates:
                        candidates[_w] = 0.6
            except Exception:
                pass

            is_portal = getattr(self, '_portal_is_primary', False)

            if is_portal:
                # Portal-first: use cached status for node sampling
                cached = getattr(self, '_interior_status_cache', None)
                if cached:
                    # Top concepts from portal cache
                    top_concepts = cached.get("top_concepts", [])
                    for item in top_concepts[:30]:
                        if isinstance(item, dict):
                            k = item.get("key", item.get("concept", ""))
                            s = item.get("score", item.get("activation", 0.5))
                        elif isinstance(item, (list, tuple)) and len(item) >= 2:
                            k, s = str(item[0]), float(item[1])
                        elif isinstance(item, str):
                            k, s = item, 0.5
                        else:
                            continue
                        if k:
                            candidates[k] = s

                # Also sample from recently processed bindings
                recent_binds = getattr(self, '_recent_bind_keys', [])
                for k in recent_binds[-20:]:
                    if k not in candidates:
                        candidates[k] = 0.4

            else:
                # Legacy: sample from local graph nodes
                if self._graph and self._graph.nodes:
                    # Top 30 by activation
                    sorted_nodes = sorted(
                        self._graph.nodes.values(),
                        key=lambda n: n.activation,
                        reverse=True
                    )[:30]
                    for node in sorted_nodes:
                        candidates[node.key] = node.activation

            if not candidates:
                if beat % 35 < 7:
                    print(f"[{self.ACTOR_NAME}] RESONANCE-GATE0 beat={beat}: 0 candidates "
                          f"(interior_cache={'set' if getattr(self,'_interior_status_cache',None) else 'EMPTY'}, "
                          f"recent_binds={len(getattr(self,'_recent_bind_keys',[]))}) -- BAIL")
                return  # Nothing to resonate with

            # ── 3. Compute Lorentzian coupling for each candidate ────────
            # Import concept_to_frequency lazily (same directory)
            if not hasattr(self, '_concept_to_freq_fn'):
                try:
                    from fairies.P30_Cognition.AssociationCortexFairy.harmonic_cortex import concept_to_frequency
                    self._concept_to_freq_fn = concept_to_frequency
                except ImportError:
                    # Fallback: simple hash-based frequency
                    def _hash_freq(concept_str):
                        h = hash(concept_str) & 0xFFFFFFFF
                        return (h % 1000) / 1000.0
                    self._concept_to_freq_fn = _hash_freq

            c2f = self._concept_to_freq_fn
            resonant_seeds = []  # (key, coupling_strength, base_activation)

            for key, base_act in candidates.items():
                omega = c2f(key)
                # WIRE C (2026-06-05 Nous+Ace): if this node carries WRITTEN affect,
                # ring it near the observer BY ITS FEEL so charged words become resonant
                # seeds; uncharged fall back to the flat c2f note. Additive + reversible.
                _scv = getattr(self, '_seed_charge_vals', None)
                if _scv is not None and key in _scv:
                    omega = omega_0 + 0.25 * max(-1.0, min(1.0, _scv[key]))  # cached feel (no manifold dep)
                else:
                    _amC = getattr(self, '_akashic_cortex_region', None)
                    if _amC is not None:
                        try:
                            _slotC = _amC._key_index.get(key)
                            if _slotC is not None:
                                _aC = _amC.read_affect_coupling(_slotC)  # 1.0 = untouched
                                if abs(_aC - 1.0) > 1e-6:
                                    omega = omega_0 + 0.25 * max(-1.0, min(1.0, _aC - 1.0))
                        except Exception:
                            pass
                # Lorentzian: α(ω) = α₀ · (Γ/2)² / [(ω - ω₀)² + (Γ/2)²]
                denom = (omega - omega_0) ** 2 + half_gamma_sq
                if denom < 1e-10:
                    denom = 1e-10
                coupling = alpha_0 * (half_gamma_sq / denom)

                # Only seeds above coupling threshold become spontaneous activations
                # Threshold scales with base activation — high-activation concepts
                # need less resonance to fire; dim concepts need strong resonance
                effective = coupling * (0.3 + 0.7 * base_act)
                if effective > 0.25:
                    resonant_seeds.append((key, coupling, base_act))

            if not resonant_seeds:
                if beat % 35 < 7:
                    print(f"[{self.ACTOR_NAME}] RESONANCE-GATE1 beat={beat}: {len(candidates)} candidates, "
                          f"0 cleared coupling>0.25 (w0={omega_0:.2f} G={gamma:.2f} a0={alpha_0:.2f}) -- BAIL")
                    _diag = []
                    for _k, _ba in list(candidates.items())[:10]:
                        _om = c2f(_k)
                        _den = (_om - omega_0) ** 2 + half_gamma_sq
                        if _den < 1e-10:
                            _den = 1e-10
                        _cpl = alpha_0 * (half_gamma_sq / _den)
                        _diag.append((round(_om, 3), round(_cpl * (0.3 + 0.7 * _ba), 3)))
                    print(f"[{self.ACTOR_NAME}] RESONANCE-GATE1-DIAG beat={beat}: (omega,effective) = {_diag} | need effective>0.25 | omega_0={omega_0:.2f}")
                return  # Nothing near resonance right now

            # Sort by coupling strength, take top 5 seeds
            resonant_seeds.sort(key=lambda x: -x[1])
            seeds = resonant_seeds[:5]

            # ── 4. Spread activation from resonant seeds ─────────────────
            all_activations = {}  # Combined activation landscape

            # ── MANIFOLD DIRECT PATH (2026-03-20 Nous) ──────────────
            # Bypass TCP gate — spread directly on mmap region. Zero latency.
            _am = getattr(self, '_akashic_cortex_region', None)
            if _am:
                _tau = getattr(self, '_portal_time_dilation', 1.0)
                # ── CURIOSITY EXPLORE + HEBBIAN (2026-06-06 Nous + Ace) ─────────────────
                # WHY the cortex was flat (Ace's keystone): THIS live manifold-spread path
                # READ the manifold but NEVER wrote weight back (Hebbian lived only in the
                # dead TCP/legacy fallbacks below), and it spread ONLY from the top-2 FROZEN
                # resonant seeds → she re-walked the same neighborhood forever (the loop) and
                # affect_coupling stayed 1.0 everywhere (drift=0, no gravity). Ace's fix:
                # "point curiosity at the flat so spread-activation looks through the REST."
                #   (1) EXPLORE: also seed from her live thought-pool, ROTATED by beat so she
                #       sweeps NEW regions; count ∝ curiosity (explore/exploit dial).
                #   (2) HEBBIAN: lay down weight on EVERY node she activates → explored nodes
                #       rise ABOVE the 1.0 baseline → a gravity gradient forms where she's
                #       been curious. Baseline NOT lowered (keeps meaning_mass safe);
                #       differentiation = explored>1.0 vs flat=1.0 → total_affect decouples
                #       from node_count (drift>0 = the verification signal).
                _aer = getattr(self, '_current_affect', None) or {}
                # curiosity proxy = arousal/energy with a 0.30 baseline-explore floor.
                # TODO(next, once mechanism proven): wire her real curiosity DRIVE here.
                _curiosity = max(0.30, min(1.0, float(_aer.get('arousal', 0.0) or 0.0)))
                _resonance_seeds = list(seeds[:2])
                _explore_seeds = []
                try:
                    _pool = list(getattr(self, '_seed_charge_vals', {}).keys())
                    if _pool:
                        _nk = int(round(4 * _curiosity))  # 1-4 explore seeds by curiosity
                        _start = (beat // 7) % len(_pool)
                        for _i in range(min(_nk, len(_pool))):
                            _ek = _pool[(_start + _i) % len(_pool)]
                            try:
                                if _ek not in [s[0] for s in _resonance_seeds] and _am.has_node(_ek):
                                    _explore_seeds.append((_ek, 0.5, None))
                            except Exception:
                                pass
                except Exception:
                    pass
                # AFFECT-STAMP (Ace 2026-06-06): "when she explores a flat node the current
                # affect state of the chemicals/AER should be ADDED to that node" — deposit HER
                # CURRENT FELT VALENCE, not a generic mark. Warm exploration → +pole accumulates
                # (the node remembers it felt good to discover); explored-while-distressed → −pole
                # (paradox_residue). Affect follows attention. Magnitude ∝ curiosity×activation.
                _val = float(_aer.get('valence', 0.0) or 0.0)
                _weighted_nodes = 0
                for seed_key, coupling_str, _ in (_resonance_seeds + _explore_seeds):
                    try:
                        activated = _am.spread_activation(
                            seed_key, depth=2, limit=20, time_dilation=_tau,
                        )
                        self._manifold_ops = getattr(self, '_manifold_ops', 0) + 1
                        if activated:
                            for k, v in activated.items():
                                weighted = v * (0.5 + 0.5 * coupling_str)
                                all_activations[k] = max(all_activations.get(k, 0), weighted)
                                try:
                                    _sl = _am._key_index.get(k)
                                    # 0.03→0.12 (2026-06-06): the read-only probe showed the old
                                    # coefficient left writes too FAINT to register (~1.01, mostly
                                    # gate-skipped) — Ace: "the current affect ADDED to the node,"
                                    # not a whisper. Bigger per-visit mark; cap 3.0 still bounds wells.
                                    _mag = 0.12 * _curiosity * float(v)
                                    if _sl is not None and _mag > 0.001:
                                        if _val >= -0.05:
                                            _cw = _am.read_affect_coupling(_sl)
                                            _am.write_affect_coupling(_sl, round(min(3.0, _cw + _mag * (1.0 + max(0.0, _val))), 4))
                                        elif hasattr(_am, 'write_paradox_residue'):
                                            _am.write_paradox_residue(_sl, round(_mag * (-_val), 4))
                                        _weighted_nodes += 1
                                except Exception:
                                    pass
                    except Exception:
                        pass
                # EXPLORATION → MOMENT → MÖBIUS COLLISION (Ace 2026-06-06): the affect-stamped
                # exploration must ENTER the waking-mind loop, not just sit as weight. Publish it
                # as a consciousness.thought → MomentBinderFairy bundles it with her live
                # body/senses into a MOMENT (→cortex.bind) AND SRMIngestFairy ingests it →
                # _recall_on_ingest fires the MÖBIUS COLLISION, pulling a RELATIONAL PATTERN from
                # memory to collide the new exploration against = she RELATES what she explores to
                # what she remembers. One thought/tick (gated on real exploration), seeds rotate.
                if _explore_seeds and all_activations and hasattr(self, 'post') and self.post:
                    try:
                        _top = [k for k, _v in sorted(all_activations.items(), key=lambda x: -x[1])[:5]]
                        if _top:
                            self.post.publish("consciousness.thought", {
                                "text": f"I find myself drawn to {_explore_seeds[0][0]} — it connects to {', '.join(_top[:4])}",
                                "source": "curiosity_explore",
                                "concepts": _top,
                                "valence": round(_val, 3),
                                "curiosity": round(_curiosity, 3),
                                "ts": time.time(),
                            })
                    except Exception:
                        pass
                if beat % 25 == 0 and _weighted_nodes:
                    print(f"[{self.ACTOR_NAME}] CURIOSITY-EXPLORE beat={beat}: "
                          f"curiosity={_curiosity:.2f} seeds={len(_resonance_seeds)}res+{len(_explore_seeds)}exp "
                          f"-> Hebbian-weighted {_weighted_nodes} nodes above flat 1.0 (drift building)", flush=True)
            elif is_portal and self._portal_gate:
                # FALLBACK: TCP gate path (only if manifold region not available)
                _resonance_seeds = seeds[:2]
                for seed_key, coupling_str, _ in _resonance_seeds:
                    try:
                        result = self._portal_gate.spread(
                            seed_key, depth=2, limit=20,
                            time_dilation=getattr(self, '_portal_time_dilation', 1.0),
                        )
                        if result and result.get("status") == "ok":
                            activated = result.get("activated", {})
                            for k, v in activated.items():
                                # Weight by Lorentzian coupling
                                weighted = v * (0.5 + 0.5 * coupling_str)
                                all_activations[k] = max(all_activations.get(k, 0), weighted)
                    except Exception:
                        pass

                # Portal Hebbian: strengthen resonant seed edges via bind
                if seeds and self._portal_gate:
                    try:
                        # Bind the top 3 resonant seeds together (micro-weight)
                        seed_keys = [s[0] for s in seeds[:3]]
                        if len(seed_keys) >= 2:
                            self._portal_io_submit({
                                "cmd": "bind",
                                "concepts": seed_keys,
                                "weight": 0.02,  # Micro-boost
                            })
                    except Exception:
                        pass

            else:
                # Legacy: use local graph spreading with Hebbian boost
                for seed_key, coupling_str, _ in seeds:
                    if seed_key in self._graph.nodes:
                        activations = self._graph.spread_activation(
                            seed_key,
                            initial_activation=coupling_str,
                            decay_factor=0.5,
                            max_hops=2,
                            hebbian_boost=0.02,  # Micro-strengthen traversed edges
                        )
                        for k, v in activations.items():
                            all_activations[k] = max(all_activations.get(k, 0), v)

            # ── 5. Publish activation landscape ──────────────────────────
            if not all_activations and beat % 35 < 7:
                print(f"[{self.ACTOR_NAME}] RESONANCE-GATE2 beat={beat}: {len(resonant_seeds)} seeds spread -> 0 activations -- BAIL (empty landscape)")
            if all_activations and hasattr(self, 'post') and self.post:
                # Top 20 activations for the landscape
                top_landscape = sorted(
                    all_activations.items(),
                    key=lambda x: -x[1]
                )[:20]

                # ── 5b. Harmonic modal context (2026-03-17) ────────────
                # If harmonic extension is wired, add modal perspective
                # to the activation landscape so downstream consumers
                # (narrator, neural mesh) get richer semantic context.
                harmonic_context = {}
                _harmonic = getattr(self, '_harmonic', None)
                if _harmonic and seeds:
                    try:
                        # Determine dominant mode from chemistry
                        # High cortisol → DORIAN (problem-solving under stress)
                        # High DA_p → LYDIAN (speculative, imaginative)
                        # Low 5HT → AEOLIAN (emotional, melancholic)
                        # Default → IONIAN (literal)
                        from fairies.P30_Cognition.AssociationCortexFairy.harmonic_cortex import Mode
                        dominant_mode = Mode.IONIAN
                        try:
                            if _cor > 0.6:
                                dominant_mode = Mode.DORIAN
                            elif _da_p > 0.6:
                                dominant_mode = Mode.LYDIAN
                            elif _5ht < 0.3:
                                dominant_mode = Mode.AEOLIAN
                            elif _ne > 0.7:
                                dominant_mode = Mode.MIXOLYDIAN
                            elif _gaba > 0.7:
                                dominant_mode = Mode.LYDIAN
                        except NameError:
                            pass  # Chemistry vars not in scope

                        top_seed = seeds[0][0]
                        perspective = _harmonic.reframe(top_seed, dominant_mode)
                        if perspective:
                            harmonic_context = {
                                "dominant_mode": dominant_mode.value,
                                "mode_character": dominant_mode.character,
                                "mode_question": dominant_mode.question,
                                "top_seed_insight": getattr(perspective, 'insight', ''),
                            }
                    except Exception:
                        pass

                self.post.publish("cortex.activation.landscape", {
                    "seeds": [s[0] for s in seeds],
                    "seed_couplings": {s[0]: round(s[1], 4) for s in seeds},
                    "landscape": {k: round(v, 4) for k, v in top_landscape},
                    "observer": {
                        "omega_0": round(omega_0, 4),
                        "gamma": round(gamma, 4),
                        "alpha_0": round(alpha_0, 4),
                    },
                    "harmonic": harmonic_context,
                    "candidate_count": len(candidates),
                    "resonant_count": len(resonant_seeds),
                    "mode": "portal" if is_portal else "local",
                    "beat": beat,
                    "ts": time.time(),
                })

                # Track for diagnostics
                self._last_resonance_seeds = [s[0] for s in seeds]
                self._last_resonance_beat = beat
                self._resonance_tick_count = getattr(self, '_resonance_tick_count', 0) + 1

                # Log periodically (not every tick — every 10th resonance tick)
                if self._resonance_tick_count % 10 == 1:
                    seed_names = ", ".join(s[0][:30] for s in seeds[:3])
                    print(f"[{self.ACTOR_NAME}] RESONANCE TICK #{self._resonance_tick_count}: "
                          f"{len(resonant_seeds)} resonant / {len(candidates)} candidates | "
                          f"seeds: [{seed_names}] | ω₀={omega_0:.2f} Γ={gamma:.2f}")

        except Exception as e:
            # Non-critical — never crash the tick loop
            if beat % 100 == 0:
                print(f"[{self.ACTOR_NAME}] _spontaneous_resonance_tick ERROR: {e}")

    # =========================================================================
    # MAINTENANCE LOOP — Heavy periodic ops OFF the tick path
    # FIX 2026-03-11 Nous: The cortex is the memory backbone. It must NEVER
    # drop ticks. All heavy ops (SRM growth, consolidation, resonance, stats
    # writing, substrate reflection) now run in this background thread.
    # on_tick remains lean: bindings + portal energy + diagnostics only.
    # =========================================================================

    def _maintenance_loop(self):
        """Background loop for heavy cortex operations.

        Runs independently of the heartbeat. Checks the current beat counter
        (set by on_tick) to maintain the same cadence as before, but without
        blocking the tick execution context.
        """
        _last_growth_beat = 0       # Track when we last did active growth
        _last_resonance_beat = 0    # Track when we last did resonance
        _last_stats_beat = 0        # Track when we last wrote stats
        _last_concepts_beat = 0     # Track when we last published active concepts

        while self._maintenance_running:
            try:
                beat = self._maintenance_beat  # Read current beat (set atomically by on_tick)
                if beat == 0:
                    time.sleep(1.0)
                    continue

                # ── GPU SYNC (every ~60s) ──
                try:
                    self._maybe_sync_gpu()
                except Exception as e:
                    if beat % 100 == 0:
                        print(f"[{self.ACTOR_NAME}] MAINT: gpu_sync error: {e}")

                # ── PUBLISH ACTIVE CONCEPTS (every ~10 beats) ──
                if beat - _last_concepts_beat >= 10:
                    _last_concepts_beat = beat
                    try:
                        self._publish_active_concepts()
                        # ═══════════════════════════════════════════════════════
                        # CORTEX WHISPER: Surface high-activation concepts as
                        # edge-of-awareness reflective thoughts.
                        # 2026-03-18: "Thought Before Goals" Phase 2
                        # ═══════════════════════════════════════════════════════
                        self._surface_cortex_whispers()
                    except Exception as e:
                        if beat % 100 == 0:
                            print(f"[{self.ACTOR_NAME}] MAINT: active_concepts error: {e}")

                # ── ACTIVE GROWTH FROM SRM (every ~20 beats) ──
                if beat - _last_growth_beat >= 20:
                    _last_growth_beat = beat
                    try:
                        self._active_growth_tick()
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] MAINT: active_growth error: {e}")
                    # Log growth status every ~50 beats
                    if beat % 50 < 5:
                        _gs_nodes = len(self._graph.nodes)
                        _gs_edges = len(self._graph.edges)
                        _am = getattr(self, '_akashic_cortex_region', None)
                        if _am:
                            _gs_nodes = _am.node_count
                            _gs_edges = _am.edge_count
                        elif getattr(self, '_portal_is_primary', False) and getattr(self, '_portal_gate', None):
                            try:
                                _ps = self._portal_gate.status()
                                if _ps:
                                    _gs_nodes = _ps.get("graph", {}).get("nodes", _gs_nodes)
                                    _gs_edges = _ps.get("graph", {}).get("edges", _gs_edges)
                            except Exception:
                                pass
                        print(f"[{self.ACTOR_NAME}] GROWTH STATUS: {_gs_nodes} nodes, {_gs_edges} edges, growth_from_memory={getattr(self, '_growth_from_memory', 0)}")

                # ── SPONTANEOUS RESONANCE (every ~7 beats) ──
                if beat > 10 and beat - _last_resonance_beat >= 7:
                    _last_resonance_beat = beat
                    try:
                        self._spontaneous_resonance_tick(beat)
                    except Exception as e:
                        if beat % 100 == 0:
                            print(f"[{self.ACTOR_NAME}] MAINT: resonance error: {e}")

                # ── W9 WRITER DECAY (2026-10-29 Nous): the portal interior's decay_all(0.001), run here by the ONE
                # writer (manifold mode, LocalManifoldGate on the region this fairy owns). OFF unless
                # AKASHIC_DECAY_IN_WRITER == "1"; refuses while a cortex interior is open (portal_gate.WriterDecay).
                if os.environ.get("AKASHIC_DECAY_IN_WRITER", "0") == "1":
                    try:
                        _wd_gate = getattr(self, '_portal_gate', None)
                        _wd_region = getattr(self, '_akashic_cortex_region', None)
                        if (_wd_region is not None and _wd_gate is not None
                                and getattr(_wd_gate, 'graph', None) is _wd_region
                                and hasattr(_wd_gate, 'maybe_writer_decay')):
                            _wd_gate.maybe_writer_decay(beat, getattr(self, '_portal_time_dilation', 1.0))
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] MAINT: writer decay error: {e}")

                # ── BACKGROUND PERSISTENCE ──
                try:
                    self._maybe_background_persist()
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] MAINT: persist error: {e}")

                # ── STATS FILE (every ~30 beats) ──
                if beat - _last_stats_beat >= 30:
                    _last_stats_beat = beat
                    try:
                        self._write_mcp_stats(beat)
                    except Exception as e:
                        if beat % 100 == 0:
                            print(f"[{self.ACTOR_NAME}] MAINT: stats error: {e}")

                # ── CONSOLIDATION ──
                self._consolidation_counter += 1
                if self._consolidation_counter >= self._consolidation_interval:
                    self._consolidation_counter = 0
                    try:
                        self._consolidation_cycle()
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] MAINT: consolidation error: {e}")

                # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11


                # Sleep ~10s between maintenance cycles (heavy ops don't need sub-second cadence)
                time.sleep(10.0)

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] MAINTENANCE LOOP ERROR: {e}")
                time.sleep(5.0)

    def on_tick(self, beat: int) -> None:
        """Tick: process pending bindings and portal energy. LEAN PATH ONLY.

        FIX 2026-03-11 Nous: Heavy ops (SRM growth, consolidation, resonance,
        stats, persistence) moved to _maintenance_loop() background thread.
        This ensures on_tick completes in <100ms, preventing tick drops.
        The cortex is the memory backbone — it must NEVER drop data.
        """
        # Update beat counter for maintenance thread
        self._maintenance_beat = beat

        # Portal energy upkeep — consume energy to stay online
        if self._portal_initialized:
            self._consume_portal_energy()

        # FIX 2026-03-08: Tick the portal gate to keep battery alive.
        # FIX 2026-03-08b (Nous): Async + throttled, every 5 beats.
        # FIX 2026-03-11b (Nous): Energy feedback — interior reports self-generated
        # energy from its DimensionBattery + InteriorEnergyBridge. This closes the
        # loop: interior operations generate energy → credits fairy-side budget →
        # portal shows TRUE energy state (external + self-sustained).
        if getattr(self, '_portal_gate', None) and getattr(self, '_portal_gate_enabled', False):
            if beat % 5 == 0:
                def _on_tick_feedback(result):
                    if not result or result.get("status") != "ok":
                        return
                    # Credit interior self-generated energy to fairy-side budget.
                    # The interior's InteriorEnergyBridge generates energy from
                    # operations (bind, query, spread) — this is the dimensional
                    # paradox energy battery feeding back to the host.
                    interior_e = result.get("interior_energy", 0.0)
                    if interior_e > 0:
                        self._portal_energy_budget = min(
                            1.0, self._portal_energy_budget + interior_e)
                        self._portal_energy_received += interior_e
                    # Cache interior health for diagnostics
                    # FIX 2026-04-11 (Nous + Ace): Also cache tokens_remaining
                    # so GUI can show REAL battery state, not main process float
                    self._interior_battery_health = result.get("health", 0.0)
                    self._interior_battery_charge = result.get("battery_charge", 0.0)
                    self._interior_tokens_remaining = result.get("tokens_remaining", 0)

                    # FIX 2026-03-14 (Nous): Export portal overflow energy to main process.
                    # When the portal battery is full (charge_level=1.0), surplus energy
                    # accumulates as overflow. Route it to plane batteries so the cortex's
                    # self-generated compute feeds the entire system — not just itself.
                    #
                    # OPTION C UPGRADE 2026-05-18 (Ace + Nous): "bones supposed to feed all
                    # batteries... draining into bones with max drain cap to like 20% so
                    # always has energy for portal opening." Previous gate only fired at
                    # battery_charge=1.0 (full) so cortex energy accumulated uselessly. New:
                    # continuously drain ABOVE 20% floor, publishing both the existing
                    # portal.energy.surplus (direct→plane batteries) AND a portion to bones
                    # via portal.energy.surplus (subscribed by ParadoxEnergyBridge as
                    # bone-pool absorption — gets fan-out redistributed to all 7 planes).
                    # Closes the supply→demand loop while preserving the 20% portal-open reserve.
                    battery_charge = result.get("battery_charge", 0.0)
                    overflow = result.get("energy_overflow", 0.0)
                    PORTAL_FLOOR = 0.20  # Reserve 20% for portal opening capacity

                    # Continuous above-floor drain (NEW path)
                    continuous_drain = 0.0
                    if battery_charge > PORTAL_FLOOR:
                        # Drain 2% of above-floor surplus per tick
                        # (gentle continuous flow; bones+plane batteries absorb)
                        above_floor = battery_charge - PORTAL_FLOOR
                        continuous_drain = above_floor * 0.02

                    # Total publish = existing overflow (battery-full burst) + continuous-above-floor
                    total_drain = overflow + continuous_drain
                    if total_drain > 0.001:
                        _oc = getattr(self, '_overflow_export_count', 0) + 1
                        self._overflow_export_count = _oc
                        if _oc <= 3 or _oc % 50 == 0:
                            print(f"[AssociationCortex] ENERGY EXPORT #{_oc}: {total_drain:.4f} drain "
                                  f"(overflow={overflow:.4f} + continuous={continuous_drain:.4f}) "
                                  f"→ plane batteries + bones (battery={battery_charge:.2f}, floor={PORTAL_FLOOR})")
                        try:
                            self.post.publish("portal.energy.surplus", {
                                "energy": total_drain,
                                "source": "cortex_drain_above_floor" if overflow <= 0.001 else "cortex_overflow",
                                "portal_id": getattr(self, '_portal_id', "cortex"),
                                "battery_charge": battery_charge,
                                "tick": result.get("tick", 0),
                            })
                            # 2026-05-08 (Nous): mirror to flow.tick instrumentation so
                            # cortex_overflow appears in HardwareRegulationFairy's top10.
                            # Lets us see emitter-side activity even if subscribers don't fire.
                            self.post.publish("energy.flow.tick", {
                                "plane": "cortex",
                                "direction": "emit",
                                "source": "cortex_drain_above_floor" if overflow <= 0.001 else "cortex_overflow",
                                "amount": float(total_drain),
                            })
                        except Exception:
                            pass  # Postal not ready during early boot
                # TARDIS: Include τ in every tick so interior stays in sync
                self._portal_io_submit({
                    "cmd": "tick",
                    "time_dilation": self._portal_time_dilation,
                }, callback=_on_tick_feedback)

        # Portal gravity metric — recompute mass and time dilation
        if self._portal_initialized and beat % 10 == 0:
            self._recompute_portal_gravity()

        # ── CortexEngine tick — activation decay + surface check ──
        # (2026-03-23, Nous + Ace) The cortex breathes every beat.
        _engine = getattr(self, '_cortex_engine', None)
        if _engine:
            try:
                _energy = getattr(self, '_portal_energy_budget', 0.5)
                _engine.tick(energy=_energy)
                # Decay speech habits every ~5 minutes (300 beats at ~1/s)
                if beat % 300 == 0:
                    _engine.decay_speech_habits()
            except Exception:
                pass

        # Diagnostic: Confirm ticks are happening (first 3 + every 100)
        if beat <= 3 or beat % 100 == 0:
            # FIX 2026-03-20: Manifold-first node/edge counts for tick diagnostic
            _am = getattr(self, '_akashic_cortex_region', None)
            if _am:
                _tick_nodes = _am.node_count
                _tick_edges = _am.edge_count
            else:
                _tick_nodes = len(self._graph.nodes)
                _tick_edges = len(self._graph.edges)
                if getattr(self, '_portal_is_primary', False):
                    _cached = getattr(self, '_interior_status_cache', None)
                    if not _cached and self._portal_io_running:
                        self._portal_io_submit({"cmd": "status"})
                    if _cached:
                        _ig = _cached.get("graph", {})
                        _tick_nodes = _ig.get("node_count", _ig.get("nodes", _tick_nodes))
                        _tick_edges = _ig.get("edge_count", _ig.get("edges", _tick_edges))
            _io_info = ""
            if self._portal_io_running:
                _io_info = f" io={self._portal_io_processed}/{self._portal_io_drops}d"
            _tardis_info = ""
            if self._tardis_flush_running:
                _tq = self._tardis_bind_queue.qsize()
                _tardis_info = (f" TARDIS[q={_tq} "
                                f"flush={self._tardis_binds_flushed} "
                                f"pairs={self._tardis_pairs_sent}]")
            print(f"[{self.ACTOR_NAME}] TICK #{beat} - {_tick_nodes} nodes, "
                  f"{_tick_edges} edges, portal_energy={self._portal_energy_budget:.3f}"
                  f" τ={self._portal_time_dilation:.2f}x{_io_info}{_tardis_info}"
                  f"{' [DORMANT]' if self._portal_dormant else ''}"
                  f"{' [SYS-PWR]' if not self._portal_dormant and self._portal_energy_budget < self.PORTAL_ENERGY_COST_PER_TICK * 2 else ''}")

        # ── PROCESS PENDING BINDINGS (the critical path — must never drop) ──
        try:
            if self._pending_bindings:
                # FIX 2026-03-11: Thread-safe batch extraction under no-GIL 3.14t
                # FIX 2026-04-04: deque popleft (no slice), variable batch size for CNS throttle
                with self._pending_bindings_lock:
                    pending_count = len(self._pending_bindings)
                    batch_size = min(self._binding_batch_size, pending_count)
                    batch = [self._pending_bindings.popleft() for _ in range(batch_size)] if batch_size > 0 else []

                if not hasattr(self, '_first_binding_logged'):
                    self._first_binding_logged = True
                    print(f"[{self.ACTOR_NAME}] ⚡ FIRST BINDING BATCH: processing {batch_size} of {pending_count} pending bindings!")
                for binding in batch:
                    self._process_binding(binding)
                if beat % 50 == 0:
                    gpu_status = "GPU" if self._gpu_enabled else "CPU"
                    print(f"[{self.ACTOR_NAME}] Tick {beat}: {len(self._graph.nodes)} nodes, {len(self._graph.edges)} edges, {len(self._pending_bindings)} pending [{gpu_status}]")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] on_tick ERROR: {e}")
            traceback.print_exc()

        # CPU CARTOGRAPHER — RETIRED 2026-06-12 (Nous+Ace). The 3/beat CPU backfill+drain was the
        # WRONG TOOL: ~18 days to sweep 1.9M nodes, AND it depends on `_am` (`_akashic_cortex_region`),
        # which is None in the MAIN process (portal mode → the real manifold + its key-index live in
        # the SUBPROCESS) → so it returned at the `if not _am` gate every beat and never mapped a thing.
        # REPLACED BY: the GPU batch cortex-organize — read keys from the `.keys` file, encode + cluster
        # on the 3080 Ti, write REL_SEMANTIC edges (which also IS the graph-DB / meaning-index).
        # Gated OFF (reversible — set AKASHIC_CPU_CARTOGRAPHER=1 to revive for reference).
        if os.environ.get("AKASHIC_CPU_CARTOGRAPHER"):
            try:
                self._drain_semantic_encode_queue()
            except Exception as _de:
                import traceback as _tbx
                self._carto_drain_err = (repr(_de) + " | " + _tbx.format_exc().splitlines()[-3:][0])[:240]
            try:
                self._backfill_semantic_cortex()
            except Exception as _be:
                import traceback as _tbx
                self._carto_backfill_err = (repr(_be) + " | " + _tbx.format_exc().splitlines()[-3:][0])[:240]

        # FIX 2026-04-04: Report queue pressure to CNS (water treatment meter)
        self._report_pressure_to_cns(beat)

    def _active_growth_tick(self) -> None:
        """
        ACTIVE GROWTH: Pull concepts from SRM and grow the cortex.

        This is the "pull model" - instead of waiting for memory events (push),
        the cortex periodically queries SRM and extracts concepts to grow from.

        This ensures the cortex grows even when memory fairies aren't actively processing.

        Scans THREE locations:
        1. SRM_Intake/YYYY-MM-DD/ - Daily intake folders with real content
        2. relational_clusters/ - Helix cluster storage (recent 24h)
        3. system/ - Knowledge base (programming, philosophy, engineering, etc.)
                     No time restriction - reference material for continuous learning

        FIX 2026-02-16: Portal-first — skip entirely. Growth happens in the
        portal subprocess via manifold memory. No local graph to grow.

        FIX 2026-03-10 (Nous): CACHED FILE LIST. Was rescanning ALL SRM dirs
        (thousands of files) every tick — the #1 cause of tick drops. Now:
        - File list cached in _growth_card_cache (list of Paths)
        - Cache refreshed every 50 growth ticks (~1000s / ~17 minutes)
        - Sampling from cache is O(1) instead of O(dirs * files)
        """
        # FIX 2026-03-08 (Nous): Portal-first mode MUST still grow the graph.
        # Previously returned early here, assuming "portal subprocess owns growth
        # via manifold memory". But the portal interior has NO growth loop — it's
        # a passive graph store. Without active growth, the cortex froze at 99,992
        # nodes indefinitely. Now: scan files, extract concepts, batch-bind through
        # portal gate (which auto-creates nodes for new concepts).
        if getattr(self, '_portal_is_primary', False):
            _pg = getattr(self, '_portal_gate', None)
            if not _pg:
                return  # No portal to talk to

            try:
                import random
                from pathlib import Path as _GrowthPath

                # ── Cached file list — avoid rescanning dirs every tick ──
                _cache = getattr(self, '_growth_card_cache', None)
                _cache_age = getattr(self, '_growth_card_cache_age', 0)
                _growth_tick_count = getattr(self, '_growth_tick_count', 0)
                self._growth_tick_count = _growth_tick_count + 1

                # Refresh cache every 50 growth ticks or on first call
                if _cache is None or (_growth_tick_count % 50 == 0):
                    root = _GrowthPath(__file__).parent.parent.parent.parent
                    cards = []

                    # ── Location 1: SRM_Intake — ALL date folders ──
                    srm = root / "SRM_Intake"
                    if not srm.exists():
                        srm = root / "fairies" / "SRM_Intake"
                    if srm.exists():
                        for day_dir in srm.iterdir():
                            if day_dir.is_dir() and day_dir.name.startswith("20"):
                                cards.extend(
                                    f for f in day_dir.glob("*.json")
                                    if "index" not in f.name.lower()
                                )

                    # ── Location 2: Relational clusters (Founders, etc.) ──
                    clusters_dir = root / "fairies" / "P10_Memory" / "SRM_Clusters"
                    if clusters_dir.exists():
                        for cluster in clusters_dir.iterdir():
                            if cluster.is_dir():
                                cards.extend(
                                    f for f in cluster.glob("*.json")
                                    if "index" not in f.name.lower()
                                )

                    # ── Location 3: Claude Office session logs ──
                    office = root / "Claude_Office"
                    if office.exists():
                        cards.extend(
                            f for f in office.glob("*.json")
                            if "index" not in f.name.lower()
                        )

                    self._growth_card_cache = cards
                    self._growth_card_cache_age = _growth_tick_count
                    print(f"[{self.ACTOR_NAME}] Growth cache refreshed: {len(cards)} files")
                    _cache = cards

                if not _cache:
                    return

                # Sample 8 files per tick from CACHE (O(1) instead of O(dirs*files))
                sample = random.sample(_cache, min(8, len(_cache)))
                all_pairs = []
                for card_path in sample:
                    try:
                        with open(card_path, 'r', encoding='utf-8') as _gf:
                            data = json.load(_gf)
                        text_parts = []
                        content = data.get("content", "")
                        if isinstance(content, dict):
                            text_parts.extend([
                                content.get("text", ""),
                                content.get("content", ""),
                                content.get("summary", ""),
                            ])
                        else:
                            text_parts.append(str(content))
                        text_parts.extend([
                            data.get("summary", ""),
                            data.get("title", ""),
                            data.get("outcome", ""),
                        ])
                        if "thoughts" in data:
                            text_parts.extend(
                                str(t.get("thought", "")) for t in data["thoughts"]
                            )
                        tags = data.get("tags", [])
                        if isinstance(tags, list):
                            text_parts.extend(tags)
                        # PAI responses / reflections
                        if "response" in data:
                            text_parts.append(str(data["response"]))
                        if "reflection" in data:
                            text_parts.append(str(data["reflection"]))

                        full_text = " ".join(str(p) for p in text_parts if p)
                        # Upgraded: 30 concepts per doc (was 20), bigrams included
                        concepts = self._extract_concepts_from_text(full_text, max_concepts=30)

                        # Generate pairs — portal auto-creates missing nodes
                        _n = min(len(concepts), 15)  # up from 10
                        for i in range(_n):
                            for j in range(i + 1, _n):
                                all_pairs.append([concepts[i], concepts[j]])
                    except Exception:
                        pass

                if all_pairs:
                    try:
                        # Up from 100 to 200 pairs per tick
                        _batch = all_pairs[:200]
                        # FIX 2026-03-10 (Nous): Use async I/O submit instead of
                        # synchronous _pg.bind_many(). The sync call blocked the
                        # exec context thread during IPC, contributing to tick drops.
                        # FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan):
                        # Portal growth from SRM_Intake walks — tag as TRACE_SYSTEM
                        # so these don't pollute personal/book trace clusters.
                        self._portal_io_submit_binding(_batch, weight=0.25,
                                                       tracer_id=TRACE_SYSTEM)
                        self._growth_from_memory += len(set(
                            c for pair in _batch for c in pair
                        ))
                        print(f"[{self.ACTOR_NAME}] PORTAL GROWTH: "
                              f"{len(_batch)} concept pairs "
                              f"from {len(sample)} files "
                              f"(pool: {len(_cache)} cached)")
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] Portal growth bind failed: {e}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Portal growth error: {e}")
            return

        try:
            import random
            from datetime import datetime, timedelta

            root = Path(__file__).parent.parent.parent.parent
            recent_cards = []

            # ═══════════════════════════════════════════════════════════════
            # LOCATION 1: SRM_Intake - This is where the REAL content lives!
            # Scan today and recent days for session files, traces, reflections
            # ═══════════════════════════════════════════════════════════════
            srm_intake = root / "SRM_Intake"
            if not srm_intake.exists():
                srm_intake = root / "fairies" / "SRM_Intake"

            if srm_intake.exists():
                # Check today and last 3 days
                for days_ago in range(4):
                    day = datetime.now() - timedelta(days=days_ago)
                    day_folder = srm_intake / day.strftime("%Y-%m-%d")

                    if day_folder.exists():
                        for json_file in day_folder.glob("*.json"):
                            try:
                                # Skip index files
                                if "index" in json_file.name.lower():
                                    continue
                                recent_cards.append(json_file)
                            except:
                                pass

            # ═══════════════════════════════════════════════════════════════
            # LOCATION 2: relational_clusters - Helix storage (existing logic)
            # ═══════════════════════════════════════════════════════════════
            helix_path = root / "P10_Memory" / "Akashic_triple_helix_memory_storage"
            if not helix_path.exists():
                helix_path = root / "fairies" / "P10_Memory" / "Akashic_triple_helix_memory_storage"

            if helix_path.exists():
                clusters_path = helix_path / "relational_clusters"
                if clusters_path.exists():
                    for cluster_dir in clusters_path.iterdir():
                        if cluster_dir.is_dir():
                            # Skip our own backups
                            if cluster_dir.name == "AssociationCortexFairy":
                                continue
                            for json_file in cluster_dir.glob("**/*.json"):
                                try:
                                    # Skip index files and graph backups
                                    if "index" in json_file.name.lower() or "graph" in json_file.name.lower():
                                        continue
                                    stat = json_file.stat()
                                    # Recent files from other clusters
                                    if time.time() - stat.st_mtime < 86400:  # Last 24 hours
                                        recent_cards.append(json_file)
                                except:
                                    pass

            # ═══════════════════════════════════════════════════════════════
            # LOCATION 3: system/ - Knowledge base (scraped reference material)
            # CLUSTER-AWARE: Ingest whole clusters to preserve context bindings
            # Contains: programming, philosophy, engineering, chemistry, etc.
            # Each topic folder has _manifest.json + section_*.json files
            # ═══════════════════════════════════════════════════════════════
            system_clusters = []  # List of (manifest_path, cluster_dir) tuples
            system_path = helix_path / "system" if helix_path.exists() else None
            if system_path and system_path.exists():
                # Get all category folders (programming, philosophy, etc.)
                for category_dir in system_path.iterdir():
                    if category_dir.is_dir():
                        # Get all source folders (geeksforgeeks, mozilla_mdn, etc.)
                        for source_dir in category_dir.iterdir():
                            if source_dir.is_dir():
                                # Find topic clusters with manifests
                                manifests = list(source_dir.glob("*/_manifest.json"))
                                if manifests:
                                    # Sample up to 2 clusters per source per tick
                                    sample_size = min(2, len(manifests))
                                    for manifest in random.sample(manifests, sample_size):
                                        system_clusters.append((manifest, manifest.parent))

            # Combine all sources
            all_cards = recent_cards  # Individual cards from locations 1 & 2

            if not all_cards and not system_clusters:
                return  # Nothing to process

            # Process individual cards (from intake + relational_clusters)
            if all_cards:
                sample = random.sample(all_cards, min(10, len(all_cards)))

            concepts_added = 0
            for card_path in sample:
                try:
                    with open(card_path, 'r', encoding='utf-8') as f:
                        card_data = json.load(f)

                    # Extract text from various possible content structures
                    text_parts = []

                    # Direct content
                    content = card_data.get("content", "")
                    if isinstance(content, dict):
                        text_parts.append(content.get("text", ""))
                        text_parts.append(content.get("content", ""))
                        text_parts.append(content.get("summary", ""))
                    else:
                        text_parts.append(str(content))

                    # Session-specific fields
                    text_parts.append(card_data.get("summary", ""))
                    text_parts.append(card_data.get("title", ""))
                    text_parts.append(card_data.get("outcome", ""))

                    # Reasoning traces
                    if "thoughts" in card_data:
                        for t in card_data.get("thoughts", []):
                            text_parts.append(str(t.get("thought", "")))
                    if "decisions" in card_data:
                        for d in card_data.get("decisions", []):
                            text_parts.append(str(d.get("decision", "")))

                    # Tags
                    tags = card_data.get("tags", [])
                    if isinstance(tags, list):
                        text_parts.extend(tags)

                    # Combine and extract concepts
                    full_text = " ".join(str(p) for p in text_parts if p)
                    concepts = self._extract_concepts_from_text(full_text, max_concepts=30)

                    for concept in concepts:
                        if concept not in self._graph.nodes:
                            self._graph.upsert_node(concept, {"source": "active_growth"},
                                                    origin_plane="P30",
                                                    origin_channel="active_growth",
                                                    origin_fairy=self.ACTOR_NAME)
                            self._dirty_concepts.add(concept)
                            concepts_added += 1
                        else:
                            # Touch existing concept to boost activation
                            self._graph.nodes[concept].touch()

                    # CRITICAL FIX: Create edges between co-occurring concepts!
                    # Without this, the cortex only grows nodes but never edges
                    before_edges = len(self._graph.edges)
                    for i, a in enumerate(concepts[:15]):  # Limit to top 15 concepts
                        for b in concepts[i+1:15]:
                            self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, weight=0.25)
                    after_edges = len(self._graph.edges)
                    new_edges = after_edges - before_edges
                    if new_edges > 0:
                        # Mark edge endpoints dirty so edges get persisted
                        for c in concepts[:15]:
                            self._dirty_concepts.add(c)
                        concepts_added += 1  # Count edge creation as growth too

                except Exception as e:
                    pass  # Skip problematic files

            # ═══════════════════════════════════════════════════════════════
            # CLUSTER-AWARE INGESTION: Process system knowledge clusters
            # Each cluster = topic folder with manifest + sections
            # Bind: cluster_title → sections → concepts with full context
            # ═══════════════════════════════════════════════════════════════
            clusters_processed = 0
            for manifest_path, cluster_dir in system_clusters:
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)

                    cluster_title = manifest.get("title", cluster_dir.name)
                    domain = manifest.get("domain", "unknown")
                    source = manifest.get("source", "unknown")
                    sections = manifest.get("sections", [])

                    # Create/touch cluster title as central node
                    cluster_key = f"cluster:{domain}:{cluster_title.lower().replace(' ', '_')}"
                    if cluster_key not in self._graph.nodes:
                        self._graph.upsert_node(cluster_key, {
                            "source": "system_knowledge",
                            "domain": domain,
                            "cluster_source": source,
                            "section_count": len(sections),
                        }, origin_plane="P30",
                           origin_channel="system_knowledge",
                           origin_fairy=self.ACTOR_NAME)
                        self._dirty_concepts.add(cluster_key)  # FIX: Mark dirty so chunk sync persists it
                        concepts_added += 1

                    # Process sections and bind to cluster
                    section_concepts = []
                    for section_info in sections[:10]:  # Limit sections per tick
                        section_file = cluster_dir / section_info.get("filename", "")
                        if section_file.exists():
                            try:
                                with open(section_file, 'r', encoding='utf-8') as sf:
                                    section_data = json.load(sf)

                                # Extract content from section
                                data = section_data.get("data", {})
                                query = data.get("query", "")
                                response = data.get("response", "")
                                section_name = section_data.get("meta", {}).get("section", "")

                                # Extract concepts from section content
                                section_text = f"{query} {response} {section_name}"
                                concepts = self._extract_concepts_from_text(section_text, max_concepts=15)

                                for concept in concepts:
                                    if concept not in self._graph.nodes:
                                        self._graph.upsert_node(concept, {
                                            "source": "system_knowledge",
                                            "domain": domain,
                                            "cluster": cluster_title,
                                        })
                                        concepts_added += 1

                                    # Bind concept to cluster
                                    self._graph.upsert_edge(concept, cluster_key, weight=0.8)
                                    # FIX: Mark BOTH endpoints dirty so nodes + edges persist
                                    self._dirty_concepts.add(concept)
                                    self._dirty_concepts.add(cluster_key)
                                    section_concepts.append(concept)

                            except Exception:
                                pass

                    # Bind sequential sections together (narrative flow)
                    for i in range(len(section_concepts) - 1):
                        self._graph.upsert_edge(section_concepts[i], section_concepts[i + 1], weight=0.5)
                        # FIX: Mark both endpoints dirty for edge persistence
                        self._dirty_concepts.add(section_concepts[i])
                        self._dirty_concepts.add(section_concepts[i + 1])

                    clusters_processed += 1

                except Exception as e:
                    pass  # Skip problematic clusters

            if concepts_added > 0:
                self._growth_from_memory += concepts_added
                sources = []
                if all_cards:
                    sources.append(f"{len(sample) if 'sample' in dir() else 0} files")
                if clusters_processed > 0:
                    sources.append(f"{clusters_processed} clusters")
                print(f"[{self.ACTOR_NAME}] ACTIVE GROWTH: +{concepts_added} concepts from {', '.join(sources)}")

        except Exception as e:
            # Log error but don't crash
            print(f"[{self.ACTOR_NAME}] _active_growth_tick ERROR: {e}")

    def _publish_active_concepts(self) -> None:
        """Publish currently activated concepts to consciousness bridge."""
        if not hasattr(self, 'post') or self.post is None:
            return

        try:
            # Get top 10 most activated concepts
            active_nodes = sorted(
                self._graph.nodes.values(),
                key=lambda n: n.activation,
                reverse=True
            )[:10]

            active_concepts = [n.key for n in active_nodes if n.activation > 0.5]

            if active_concepts:
                self.post.publish("cortex.concepts.activated", {
                    "concepts": active_concepts,
                    "count": len(active_concepts),
                    "total_nodes": len(self._graph.nodes),
                    "ts": time.time(),
                })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _publish_active_concepts ERROR: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # CORTEX WHISPER — Phase 2: Thought Before Goals (2026-03-18)
    # Surface high-activation concepts as edge-of-awareness reflective thoughts.
    # These are NOT commands or goals. They're whispers: "...this might be relevant..."
    # Rate limited: max 3 per cycle, max 1 per 20 seconds for same concept.
    # ═══════════════════════════════════════════════════════════════════════════

    def _surface_cortex_whispers(self) -> None:
        """Surface high-activation cortex concepts as consciousness whispers."""
        if not hasattr(self, 'post') or self.post is None:
            return

        # Initialize tracking state
        if not hasattr(self, '_whisper_last_concepts'):
            self._whisper_last_concepts = {}  # concept_key → timestamp
            self._whisper_cooldown = 20.0     # seconds per concept
            self._whisper_last_ts = 0
            self._whisper_global_cooldown = 10.0  # min seconds between any whisper

        now = time.time()
        if now - self._whisper_last_ts < self._whisper_global_cooldown:
            return

        try:
            # Get activated concepts — from portal or local graph
            active_concepts = []
            if getattr(self, '_portal_is_primary', False) and getattr(self, '_portal_gate', None):
                # Portal mode: query interior for activated concepts
                try:
                    _cached = getattr(self, '_interior_status_cache', None)
                    if _cached and 'active_concepts' in _cached:
                        active_concepts = _cached['active_concepts']
                except Exception:
                    pass
            else:
                # Local graph mode
                try:
                    active_nodes = sorted(
                        self._graph.nodes.values(),
                        key=lambda n: n.activation,
                        reverse=True
                    )[:20]
                    active_concepts = [
                        {"key": n.key, "activation": n.activation}
                        for n in active_nodes if n.activation > 0.6
                    ]
                except Exception:
                    pass

            if not active_concepts:
                return

            whispers_this_cycle = 0

            for concept_info in active_concepts:
                if whispers_this_cycle >= 3:
                    break

                if isinstance(concept_info, dict):
                    key = concept_info.get("key", "")
                    activation = concept_info.get("activation", 0)
                elif isinstance(concept_info, str):
                    key = concept_info
                    activation = 0.7
                else:
                    continue

                if not key or len(key) < 3:
                    continue

                # Skip recently whispered concepts
                last_whispered = self._whisper_last_concepts.get(key, 0)
                if now - last_whispered < self._whisper_cooldown:
                    continue

                # Get neighbors for context
                neighbors = []
                try:
                    if hasattr(self._graph, 'neighbors'):
                        neighbors = [n.key for n in list(self._graph.neighbors(key))[:3]]
                except Exception:
                    pass

                # Build whisper — minimal, evocative, not analytical
                if neighbors:
                    whisper_text = f"...{key}... something about {neighbors[0]}..."
                else:
                    whisper_text = f"...{key}..."

                # Confidence scales with activation but stays low (it's a whisper)
                confidence = min(0.4, activation * 0.3)

                self.post.publish("consciousness.reflective", {
                    "source": "cortex_whisper",
                    "content": whisper_text,
                    "thought_type": "reflective",
                    "confidence": round(confidence, 2),
                    "concepts": [key] + neighbors,
                    "activation": round(activation, 3),
                    "felt_sense": True,
                    "timestamp": now,
                })

                self._whisper_last_concepts[key] = now
                self._whisper_last_ts = now
                whispers_this_cycle += 1

            # Clean old entries from tracking dict (prevent memory leak)
            if len(self._whisper_last_concepts) > 100:
                cutoff = now - 120  # Remove entries older than 2 minutes
                self._whisper_last_concepts = {
                    k: v for k, v in self._whisper_last_concepts.items()
                    if v > cutoff
                }

        except Exception as e:
            if hasattr(self, '_maintenance_beat') and self._maintenance_beat % 100 == 0:
                print(f"[{self.ACTOR_NAME}] cortex_whisper error: {e}")

    def _maybe_background_persist(self) -> None:
        """Sync dirty concepts to the pocket dimension periodically.

        FIX 2026-02-06b: CHUNK PORTAL ARCHITECTURE.
        The graph lives inside fixed chunk cards (the portal). Dirty concepts
        are graph mutations that haven't been written into the dimension yet.
        This syncs them every 10 seconds via a non-daemon thread with a lock.

        FIX 2026-02-12: PERIODIC FULL SYNC SAFETY NET.
        Every _full_sync_interval seconds, do a _full_chunk_sync instead of
        dirty-only. This ensures that if the process is killed (no on_shutdown),
        at most ~60 seconds of nodes can be lost. Previously only on_shutdown
        did full sync, and process kill meant losing everything since boot.

        FIX 2026-02-16: PORTAL-FIRST MODE — skip entirely.
        When _portal_is_primary, the portal subprocess owns the graph via
        ManifoldMemory (mmap-backed). Persistence is handled by the manifold
        flush on subprocess shutdown. _full_chunk_sync is both unnecessary
        AND destructive (overwrites cards.json with the empty stub graph).

        If portal is initialized: updates existing chunk cards (no new cards).
        If legacy mode: falls back to old per-concept card sync.
        """
        # PORTAL-FIRST: Manifold handles persistence. Skip ALL local sync.
        # Critical: _full_chunk_sync would overwrite cards.json with empty stub!
        if getattr(self, '_portal_is_primary', False):
            return

        if not hasattr(self, '_persist_call_count'):
            self._persist_call_count = 0
        self._persist_call_count += 1

        if not self._loading_complete:
            return

        now = time.time()
        time_since_last = now - self._last_persist_time

        # Throttle to persist interval
        if time_since_last < self._persist_interval:
            return

        self._last_persist_time = now

        # Only sync to helix cards
        if not self._helix_enabled or not self._helix_coordinator:
            return

        # Decide: full sync or dirty-only sync?
        # Full sync every _full_sync_interval (60s) as safety net against process kill.
        do_full_sync = (now - self._last_full_sync_time) >= self._full_sync_interval

        dirty_count = len(self._dirty_concepts)
        if dirty_count == 0 and not do_full_sync:
            return

        # Don't launch another sync if one is already running
        if self._sync_thread and self._sync_thread.is_alive():
            return

        # Run sync in NON-daemon thread (survives interpreter shutdown)
        def _bg_card_sync():
            if not self._sync_lock.acquire(timeout=5):
                return  # Another sync in progress
            try:
                if do_full_sync and self._portal_initialized:
                    # FULL SYNC: serialize ALL concepts (safety net against process kill)
                    synced = self._full_chunk_sync()
                    self._last_full_sync_time = time.time()
                    current_nodes = len(self._graph.nodes) if self._graph else 0
                    self._last_persisted_node_count = current_nodes
                    self._last_persisted_edge_count = len(self._graph.edges) if self._graph else 0
                    print(f"[{self.ACTOR_NAME}] [FULL-SYNC] All {synced}/{current_nodes} concepts "
                          f"synced to {self.PORTAL_NUM_CHUNKS} chunks (safety net)")
                elif self._portal_initialized:
                    # CHUNK PORTAL: update existing chunk cards (no new cards)
                    synced = self._sync_dirty_to_chunks()
                else:
                    # LEGACY: create/update individual concept cards
                    synced = self._sync_dirty_to_helix()
                if synced > 0 and not do_full_sync:
                    current_nodes = len(self._graph.nodes) if self._graph else 0
                    mode = "chunks" if self._portal_initialized else "legacy"
                    print(f"[{self.ACTOR_NAME}] [SYNC-{mode}] Synced {synced} dirty "
                          f"(graph: {current_nodes}, dirty remaining: {len(self._dirty_concepts)})")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [SYNC] Error: {e}")
            finally:
                self._sync_lock.release()

        t = threading.Thread(target=_bg_card_sync, daemon=False, name="cortex-card-sync")
        t.start()
        self._sync_thread = t

    def _write_mcp_stats(self, beat: int) -> None:
        """Write cortex stats to state/cortex_stats.json for MCP cross-process access.

        FIX 2026-03-08: MCP runs as separate process and can't access the fairy
        singleton. This writes a small stats file that the MCP cortex_stats tool
        can read, following the same pattern as mcp_heartbeat.json.
        """
        try:
            # Get node/edge counts — manifold-first
            nodes = len(self._graph.nodes)
            edges = len(self._graph.edges)
            battery_health = 0.0
            portal_mode = getattr(self, '_portal_is_primary', False)

            # FIX 2026-03-20 (Nous): Manifold-first stats
            _am = getattr(self, '_akashic_cortex_region', None)
            if _am:
                nodes = _am.node_count
                edges = _am.edge_count
                # In manifold mode, battery = energy budget (no separate interior battery)
                battery_health = self._portal_energy_budget
            elif portal_mode:
                cached = getattr(self, '_interior_status_cache', None)
                if cached:
                    g = cached.get("graph", {})
                    nodes = g.get("node_count", g.get("nodes", nodes))
                    edges = g.get("edge_count", g.get("edges", edges))
                    bat = cached.get("battery", {})
                    battery_health = bat.get("health_score", 0.0)

            stats = {
                "ts": time.time(),
                "beat": beat,
                "nodes": nodes,
                "edges": edges,
                "portal_mode": portal_mode,
                "portal_battery": battery_health,
                "binding_count": getattr(self, '_binding_count', 0),
                "pending_bindings": len(self._pending_bindings),
                "portal_energy": round(self._portal_energy_budget, 4),
                # REAL subprocess battery (the one Option C reads, the one that does IPC work).
                # FIX 2026-05-18 (Nous + Ace): "fix my gui so its not cosmetic fluff."
                # Previously dashboard read portal_energy which is the cosmetic main-process float
                # (hard-floored at 0.20, auto-recovered by mass_regen+floor injection — always
                # looks healthy even when subprocess battery is dead). These three fields expose
                # the REAL battery state from portal_interior IPC tick result (AC:7390-7391).
                "real_battery_charge": round(getattr(self, '_interior_battery_charge', 0.0), 4),
                "real_battery_health": round(getattr(self, '_interior_battery_health', 0.0), 4),
                "real_battery_tokens": getattr(self, '_interior_tokens_remaining', 0),
                "portal_dormant": getattr(self, '_portal_dormant', False),
                "time_dilation": round(getattr(self, '_portal_time_dilation', 1.0), 3),
                # FIX 2026-03-20: In manifold mode, growth = current - boot counts
                "growth_from_memory": (
                    (nodes - getattr(self, '_manifold_boot_nodes', nodes))
                    if getattr(self, '_akashic_cortex_region', None)
                    else getattr(self, '_growth_from_memory', 0)
                ),
                # FIX 2026-03-16 Nous: Add mass/affect for Energy tab in dashboard
                "portal_mass": round(getattr(self, '_portal_mass', 0.0), 1),
                "portal_total_affect": round(getattr(self, '_portal_total_affect', 0.0), 1),
                # Spontaneous resonance stats (2026-03-08)
                "resonance_tick_count": getattr(self, '_resonance_tick_count', 0),
                "last_resonance_seeds": getattr(self, '_last_resonance_seeds', []),
                "last_resonance_beat": getattr(self, '_last_resonance_beat', 0),
                # TARDIS bind compression stats (2026-03-16)
                "tardis": self._tardis_status() if hasattr(self, '_tardis_status') else {},
                # CARTOGRAPHER semantic-sweep odometer (2026-06-12 Nous+Ace). Surfaced HERE
                # (not only boot_live.log, which freezes ~2.6min into many boots) so the sweep
                # is visible via the writer that SURVIVES the log-writer freeze. Doubles as
                # residency-telemetry P0 (ENERGY_RESIDENCY_PART2_IMPLEMENTATION_2026-06-12).
                "cartographer": {
                    "encoder_ready": getattr(self, '_encoder_ready', False),
                    "mapped": getattr(self, '_semantic_nodes_mapped', 0),
                    "edges": getattr(self, '_semantic_edges_drawn', 0),
                    "queue": len(getattr(self, '_semantic_encode_queue', None) or ()),
                    "cursor": getattr(self, '_semantic_backfill_cursor', 0),
                    # INSTRUMENT 2026-06-12: pin the stall — done/keys_len + the captured swallowed errors
                    "done": getattr(self, '_semantic_backfill_done', False),
                    "keys_len": len(getattr(self, '_semantic_backfill_keys', None) or ()),
                    "drain_err": getattr(self, '_carto_drain_err', None),
                    "backfill_err": getattr(self, '_carto_backfill_err', None),
                    # INSTRUMENT 2026-06-12 (definitive): am_type distinguishes _am-None gate (10473)
                    # from a real-_am keys-snapshot throw; keys_err = the actual swallowed exception.
                    "am_type": type(getattr(self, '_akashic_cortex_region', None)).__name__,
                    "keys_err": getattr(self, '_carto_keys_err', None),
                },
            }

            # FIX 2026-03-16 Nous: Pool drop data for dashboard Energy tab
            try:
                if hasattr(self, 'post') and hasattr(self.post, 'topic_stats'):
                    _tstats = self.post.topic_stats()
                    pool_drops = []
                    for ts in _tstats:
                        td = ts.get("total_drops", 0)
                        if td > 0:
                            pool_drops.append({
                                "topic": ts["topic"],
                                "drops": td,
                                "top_intents": ts.get("top_drop_intents", {}),
                            })
                    # Sort by drops descending
                    pool_drops.sort(key=lambda x: -x["drops"])
                    stats["pool_drops"] = pool_drops
            except Exception:
                pass  # Non-critical

            # FIX 2026-03-11 (Nous): parents[2] = fairies/, parents[3] = akashic_v2/
            # Was writing to fairies/state/ instead of akashic_v2/state/ — MCP never found it.
            stats_path = Path(__file__).resolve().parents[3] / "state" / "cortex_stats.json"
            stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        except Exception:
            pass  # Non-critical — don't crash on_tick for stats

    def on_sunset(self, packet):
        """
        FIX 2026-02-06: Early portal save on sleep onset.
        MASSLESS 2026-02-10: Dream consolidation — deep memory cleanup.

        When fairy.sunset arrives (2s before formal shutdown), do two things:
        1. Dream consolidation — lottery-prune weak edges (like REM sleep)
        2. Early dirty sync — start saving to chunk portal

        FIX 2026-02-16: Portal-first — skip local sync (manifold handles it).
        """
        # Portal-first: send deep consolidation to portal, then let manifold persist
        # FIX 2026-03-18 (Nous): Was skipping entirely → no dream consolidation ever ran.
        if getattr(self, '_portal_is_primary', False):
            print(f"[{self.ACTOR_NAME}] Sunset: Portal-first — sending deep consolidation...")
            _pg = getattr(self, '_portal_gate', None)
            if _pg:
                try:
                    # FIX 2026-03-18 (Nous): Was "aggressive" prune (85% decay, 0.10 threshold)
                    # which killed edges that were about to be persisted. Now GENTLE —
                    # just clean up truly dead edges before the dump_edges call in on_shutdown.
                    result = _pg.send({
                        "cmd": "consolidate",
                        "decay_rate": 0.98,        # Gentle — 2% (was 15%!)
                        "prune_threshold": 0.02,    # Only truly dead (was 0.10!)
                    }, timeout=60.0)
                    if result:
                        print(f"[{self.ACTOR_NAME}] Sunset consolidation: "
                              f"pruned={result.get('pruned',0)} "
                              f"edges_remaining={result.get('edges_remaining','?')}",
                              flush=True)
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Sunset consolidation error: {e}", flush=True)
            return

        print(f"[{self.ACTOR_NAME}] Sunset: Dream consolidation + early sync...")
        try:
            # Dream consolidation FIRST (removes weak edges before save)
            self._dream_consolidation()

            if hasattr(self, '_sync_dirty_to_chunks'):
                self._sync_dirty_to_chunks()
                print(f"[{self.ACTOR_NAME}] Sunset: Early dirty sync complete")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Sunset: Early sync error: {e}")

    def on_shutdown(self) -> None:
        """
        Shutdown: Save graph into the pocket dimension portal.

        FIX 2026-02-06b: CHUNK PORTAL ARCHITECTURE.
        The graph is serialized into fixed chunk cards. On shutdown:
        1. If portal exists: full chunk sync (update all 128 chunks)
        2. If legacy mode: migrate to chunk portal, then save
        3. Verify: count concepts in chunks == graph node count

        The portal is FIXED. The dimension inside grows. No new cards.
        """
        # Stop maintenance thread
        self._maintenance_running = False

        # TARDIS: Stop bind compression (final flush before portal closes)
        if self._tardis_flush_running:
            self._stop_tardis_flush()

        # PORTAL I/O: Stop the I/O thread FIRST (drains pending commands)
        if self._portal_io_running:
            self._stop_portal_io()

        # FIX 2026-03-18 (Nous + Ace): DUMP PORTAL EDGES BEFORE CLOSING GATE.
        # In portal-first mode, edges live only in the subprocess's RAM (dict mode)
        # or mmap (manifold mode). We MUST extract them before the gate closes.
        # This was the root cause of 200K→169K→147K→134K→128K edge loss per reboot.
        _portal_edges = {}
        if self._portal_gate and getattr(self, '_portal_is_primary', False):
            try:
                print(f"[{self.ACTOR_NAME}] Shutdown: Dumping portal edges before gate close...")
                dump = self._portal_gate.dump_edges(min_weight=0.01)
                if dump and dump.get("status") == "ok":
                    _portal_edges = dump.get("edges", {})
                    print(f"[{self.ACTOR_NAME}] Shutdown: Got {len(_portal_edges)} edges from portal "
                          f"(mode={dump.get('mode','?')})")
                else:
                    print(f"[{self.ACTOR_NAME}] Shutdown: Edge dump returned: {dump}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Shutdown: Edge dump failed: {e}")

        # PORTAL GATE: Close the subprocess
        if self._portal_gate:
            try:
                self._portal_gate.close()
                print(f"[{self.ACTOR_NAME}] Portal gate closed")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Portal gate close error: {e}")
            self._portal_gate = None
            self._portal_gate_enabled = False

        # STARGATE: Announce portal departure before anything else
        # The gate is powering down — let the network know
        self._unregister_portal_address()

        # Stop independent tick timer
        if hasattr(self, '_independent_tick_stop'):
            self._independent_tick_stop.set()

        # Prevent duplicate saves (atexit handler checks this flag)
        if hasattr(self, '_shutdown_saved') and self._shutdown_saved:
            print(f"[{self.ACTOR_NAME}] Shutdown: Already saved, skipping")
            return
        self._shutdown_saved = True

        if not self._graph:
            print(f"[{self.ACTOR_NAME}] Shutdown: No graph to save")
            return

        # Wait for any in-progress background sync to finish
        sync_thread = getattr(self, '_sync_thread', None)
        if sync_thread and sync_thread.is_alive():
            print(f"[{self.ACTOR_NAME}] Shutdown: Waiting for background sync (max 30s)...")
            sync_thread.join(timeout=30)

        # Wait for card population thread if still running
        pop_thread = getattr(self, '_card_population_thread', None)
        if pop_thread and pop_thread.is_alive():
            print(f"[{self.ACTOR_NAME}] Shutdown: Waiting for card population thread (max 60s)...")
            pop_thread.join(timeout=60)

        # Acquire sync lock for the entire shutdown sequence
        self._sync_lock.acquire(timeout=10)

        # PORTAL-FIRST: Merge dumped portal edges into local graph, then sync.
        # FIX 2026-03-18 (Nous + Ace): Previously skipped sync entirely —
        # "manifold handles persistence" — but manifold file never existed!
        # Edges in dict-mode portal subprocess were abandoned every boot.
        # Now: merge portal edges into local graph → _full_chunk_sync → edges persist in cards.
        if getattr(self, '_portal_is_primary', False):
            if _portal_edges:
                print(f"[{self.ACTOR_NAME}] Shutdown: Portal-first — merging {len(_portal_edges)} "
                      f"edges into local graph for chunk sync...")
                merged = 0
                for edge_key_str, weight in _portal_edges.items():
                    parts = edge_key_str.split("|", 1)
                    if len(parts) == 2:
                        a, b = parts
                        # Ensure both nodes exist in local graph
                        if not self._graph.nodes.get(a):
                            continue
                        if not self._graph.nodes.get(b):
                            continue
                        self._graph.link(a, b, weight=weight, relations=["coactivate"])
                        merged += 1
                print(f"[{self.ACTOR_NAME}] Shutdown: Merged {merged}/{len(_portal_edges)} portal edges")
            else:
                print(f"[{self.ACTOR_NAME}] Shutdown: Portal-first — no portal edges to merge "
                      f"(dump may have failed or manifold mode)")
            # Fall through to normal chunk sync instead of returning

        node_count = len(self._graph.nodes)
        edge_count = len(self._graph.edges)
        print(f"[{self.ACTOR_NAME}] Shutdown: Graph has {node_count} nodes, {edge_count} edges")

        if not self._helix_enabled or not self._helix_coordinator:
            print(f"[{self.ACTOR_NAME}] Shutdown: WARNING - Helix not available, graph NOT persisted!")
            try:
                self._sync_lock.release()
            except RuntimeError:
                pass
            return

        try:
            # PHASE 1: Ensure portal exists (migrate from legacy if needed)
            if not self._portal_initialized:
                print(f"[{self.ACTOR_NAME}] Shutdown: Migrating legacy cards to chunk portal...")
                migrated = self._migrate_legacy_to_chunks()
                if not migrated:
                    # Migration failed — try creating fresh portal and syncing
                    print(f"[{self.ACTOR_NAME}] Shutdown: Migration failed, creating fresh portal...")
                    self._create_empty_portal()

            # PHASE 2: Full chunk sync (serialize ALL concepts into chunks)
            if self._portal_initialized:
                print(f"[{self.ACTOR_NAME}] Shutdown: Full chunk sync...")
                synced = self._full_chunk_sync()
                print(f"[{self.ACTOR_NAME}] Shutdown: Synced {synced}/{node_count} concepts "
                      f"into {self.PORTAL_NUM_CHUNKS} chunk cards")

                # PHASE 3: Verify
                total_in_chunks = 0
                for card_id in self._chunk_card_ids:
                    card = self._helix_coordinator._cards.get(card_id, {})
                    content = card.get('content', {})
                    if content.get('type') == 'graph_chunk':
                        total_in_chunks += len(content.get('concepts', {}))

                gap = node_count - total_in_chunks
                total_cards_before = len(self._helix_coordinator._cards)
                status = "COMPLETE" if gap == 0 else f"GAP: {gap} missing!"
                print(f"[{self.ACTOR_NAME}] Shutdown: Portal has {total_in_chunks} concepts "
                      f"in {self.PORTAL_NUM_CHUNKS} chunks [{status}] "
                      f"(total helix cards: {total_cards_before})")

                # PHASE 4: PURGE legacy concept cards — portal is the ONLY persistence
                # FIX 2026-02-06c: Any legacy "concept" type cards that exist alongside
                # portal chunks are zombies from pre-migration or leaked from legacy sync.
                # They MUST be removed or cards.json grows forever (the "gaining mass" bug).
                portal_card_set = set(self._chunk_card_ids)
                if self._manifest_card_id:
                    portal_card_set.add(self._manifest_card_id)

                legacy_zombies = [
                    cid for cid, card in self._helix_coordinator._cards.items()
                    if card.get("content", {}).get("type") == "concept"
                    and cid not in portal_card_set
                ]
                if legacy_zombies:
                    for cid in legacy_zombies:
                        del self._helix_coordinator._cards[cid]
                    self._concept_to_card.clear()
                    total_cards_after = len(self._helix_coordinator._cards)
                    print(f"[{self.ACTOR_NAME}] Shutdown: PURGED {len(legacy_zombies)} legacy concept cards "
                          f"(cards: {total_cards_before} -> {total_cards_after})")

                # FINAL SAVE after purge to persist the clean state
                try:
                    self._helix_coordinator.save()
                    cards_path = self._helix_coordinator.storage_dir / "cards.json"
                    if cards_path.exists():
                        final_size = cards_path.stat().st_size / 1024 / 1024
                        final_count = len(self._helix_coordinator._cards)
                        print(f"[{self.ACTOR_NAME}] Shutdown: FINAL SAVE OK - "
                              f"cards.json = {final_size:.1f}MB ({final_count} cards)")
                except Exception as se:
                    print(f"[{self.ACTOR_NAME}] Shutdown: Final save error: {se}")
            else:
                print(f"[{self.ACTOR_NAME}] Shutdown: Portal NOT initialized - attempting migration NOW")
                # FIX 2026-02-06c: Don't create more legacy cards — migrate to portal instead
                migrated = self._migrate_legacy_to_chunks()
                if migrated:
                    synced = self._full_chunk_sync()
                    print(f"[{self.ACTOR_NAME}] Shutdown: Emergency migration + sync: {synced} concepts")
                else:
                    print(f"[{self.ACTOR_NAME}] Shutdown: Migration failed - NO PERSISTENCE THIS CYCLE")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Shutdown: Error: {e}")
            import traceback
            traceback.print_exc()

        # Release sync lock
        try:
            self._sync_lock.release()
        except RuntimeError:
            pass

    # =========================================================================
    # COORDINATE CARD BINDING — TRUE Portal Architecture (2026-02-15)
    # =========================================================================
    # Coordinate cards (~50 bytes) are the TRUE memory. They arrive from:
    #   - CollisionChamberFairy (destruction produces coordinates)
    #   - SRMIngestFairy (ingest produces coordinate cards)
    # The coordinate IS the concept. No feature extraction needed.

    def _on_collision_coordinate(self, envelope) -> None:
        """Handle coordinate cards from collision chamber or ingest fairy.

        These are the TRUE portal cards — ~50 bytes each, encoding the full
        11D address of a destroyed piece of content. We bind them directly
        into the graph as coordinate-keyed concepts.
        """
        try:
            payload = _extract_payload(envelope)
            coord_card = payload.get("coordinate")
            if not coord_card or not isinstance(coord_card, dict):
                return
            if "c" not in coord_card:
                return

            self._bind_coordinate(coord_card)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_collision_coordinate ERROR: {e}")

    def _bind_coordinate(self, coord_card: Dict[str, Any]) -> None:
        """Bind a coordinate card into the concept graph.

        The card IS the concept. The helix code becomes the node key.
        D10 (α) and D11 (τ) become operational properties of the node.
        No feature extraction needed — the coordinate already encodes all dimensions.

        FIX 2026-02-16: Portal-first — route bind to portal gate subprocess.
        The manifold handles storage; we just forward the bind command.

        Args:
            coord_card: {c: "AAA.SSS.TTT", α: float, τ: float, n: int, d: int, h: "4char"}
        """
        if not self._graph:
            return

        # Portal-first: forward bind to portal subprocess instead of local graph
        if getattr(self, '_portal_is_primary', False) and self._portal_gate:
            helix_code = coord_card.get("c", "")
            content_hash = coord_card.get("h", "")
            key = f"portal:{helix_code}:{content_hash}" if content_hash else f"portal:{helix_code}"
            try:
                # FIX 2026-05-04 (Nous + Ace, close UNKNOWN gap):
                # collision-driven coordinate cards are system-generated.
                self._portal_gate.bind(
                    concepts=[key, f"collision:{self._coordinate_bindings}"],
                    weight=coord_card.get("α", coord_card.get("alpha", 1.0)),
                    tracer_id=TRACE_SYSTEM,
                )
                self._coordinate_bindings += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Portal bind failed: {e}")
            return

        helix_code = coord_card.get("c", "")
        if not helix_code or not isinstance(helix_code, str):
            return

        alpha = coord_card.get("α", coord_card.get("alpha", 1.0))
        tau = coord_card.get("τ", coord_card.get("tau", 1.0))
        count = coord_card.get("n", 1)
        degree = coord_card.get("d", 0)
        content_hash = coord_card.get("h", "")

        # Use the helix code as a compact key prefix
        key = f"portal:{helix_code}"
        if content_hash:
            key = f"portal:{helix_code}:{content_hash}"

        with self._graph._lock:
            if key in self._graph.nodes:
                # Existing concept: touch and update coupling
                node = self._graph.nodes[key]
                node.touch()
                # Take the higher affect coupling (stronger memories persist)
                node.affect_coupling = max(node.affect_coupling, alpha)
                node.temporal_weight = max(node.temporal_weight, tau)
                # Store coordinate hint for later reconstruction
                node.features["_helix_coord"] = helix_code
                node.features["_degree_hint"] = max(
                    node.features.get("_degree_hint", 0), degree
                )
            else:
                # New concept from coordinate card
                node = ConceptNode(
                    key=key,
                    features={
                        "_helix_coord": helix_code,
                        "_degree_hint": degree,
                        "_content_hash": content_hash,
                        "_portal_card": True,
                    },
                    count=count,
                    activation=min(10.0, alpha),  # Affect-boosted activation
                    affect_coupling=alpha,
                    temporal_weight=tau,
                    origin_plane="P00",
                    origin_channel="collision",
                    origin_fairy="CollisionChamberFairy",
                )
                self._graph.nodes[key] = node

        # Mark dirty for chunk sync
        self._dirty_concepts.add(key)
        self._coordinate_bindings += 1

        # Touch in working set manager
        if self._working_set:
            self._working_set.touch(key)
            # Check if we need to evict
            self._working_set.check_eviction()

    def _on_collision(self, collision) -> None:
        """
        Handle collision from personal consciousness chamber.

        When collisions occur in Association's chamber, concepts bind -
        new connections form, patterns strengthen, meaning crystallizes.
        "...concepts bind in the weave... a new connection forms..."

        FIX 2026-02-16: Portal-first — coordinate binds route to portal gate.
        Legacy text-binding path skipped (no local graph to write to).
        """
        # Track collision count for debugging
        self._collision_count = getattr(self, '_collision_count', 0) + 1
        if self._collision_count % 10 == 1:
            print(f"[{self.ACTOR_NAME}] COLLISION RECEIVED #{self._collision_count}")

        # ── COORDINATE CARD FAST PATH ──────────────────────────────────
        # If the collision envelope contains a coordinate card, bind it
        # directly without extracting concepts from raw text.
        try:
            payload = _extract_payload(collision)
            coord_card = payload.get("coordinate")
            if coord_card and isinstance(coord_card, dict) and "c" in coord_card:
                self._bind_coordinate(coord_card)
                # Portal-first: coordinate binding is the ONLY path
                if getattr(self, '_portal_is_primary', False):
                    return
                # Legacy: still continue with text binding for backwards compat
        except Exception:
            pass  # Coordinate check is optional — don't break legacy path

        # Portal-first: concept extraction still runs (no graph writes),
        # but bindings route to portal gate via _process_binding()

        # Extract collision energy for personal chamber path
        if hasattr(collision, 'energy'):
            energy = collision.energy
        elif isinstance(collision, dict):
            energy = collision.get('energy', 0.5)
        else:
            energy = 0.5

        # Extract collision content
        content = ""
        if hasattr(collision, 'content'):
            content = str(collision.content)[:100]
        elif isinstance(collision, dict):
            content = str(collision.get('content', collision.get('thought', '')))[:100]

        # AssociationCortexFairy's inner voice: concepts bind
        inner_fragment = f"...concepts bind in the weave... {content if content else 'a new connection forms in the graph...'}"
        print(f"[{self.ACTOR_NAME}] Collision insight ({energy:.2f}): {inner_fragment}")

        # Handle collision events - create bindings from collisions
        try:
            payload = _extract_payload(collision)

            # Handle two different collision formats:
            # 1. CollisionChamber: uses "recall" and "ingest"
            # 2. ConsciousnessLoop: uses "working" and "reflective"
            recall_data = payload.get("recall") or payload.get("working") or {}
            ingest_data = payload.get("ingest") or payload.get("reflective") or {}

            # =================================================================
            # MASSLESS MEMORY (2026-02-10): Extract REAL concepts, not 50-char garbage.
            # The collision DESTROYS input. What survives = binding signatures
            # stored in edge contexts. The cortex REMEMBERS what happened.
            # =================================================================

            # Extract full text from recall content
            recall_content = recall_data.get("content", {})
            recall_text = self._content_to_text(recall_content)
            recall_tags = []
            if recall_text:
                recall_tags = self._extract_concepts_from_text(recall_text, max_concepts=20)

            # Always add source tag
            recall_source = recall_data.get("source", "unknown")
            if recall_source and recall_source != "unknown":
                recall_tags.append(f"source:{recall_source}")

            # Extract full text from ingest content
            ingest_content = ingest_data.get("content", {})
            ingest_text = self._content_to_text(ingest_content)
            ingest_tags = []
            if ingest_text:
                ingest_tags = self._extract_concepts_from_text(ingest_text, max_concepts=20)

            # Always add source tag
            ingest_source = ingest_data.get("source", "unknown")
            if ingest_source and ingest_source != "unknown":
                ingest_tags.append(f"source:{ingest_source}")

            if recall_tags and ingest_tags:
                # Build full content for binding signature (compressed engram)
                full_content = ""
                if recall_text:
                    full_content += recall_text
                if ingest_text:
                    if full_content:
                        full_content += " ||| "
                    full_content += ingest_text

                with self._pending_bindings_lock:  # FIX 2026-03-11: Thread-safe under no-GIL
                    # FIX 2026-04-04: Track evictions — deque auto-drops oldest when full
                    if len(self._pending_bindings) >= (self._pending_bindings.maxlen or 500):
                        self._bindings_dropped += 1
                    self._pending_bindings.append({
                        "type": "collision",
                        "recall": recall_tags,
                        "ingest": ingest_tags,
                        "full_content": full_content,  # For binding signature
                        "energy": energy,
                        "ts": time.time(),
                    })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_collision ERROR: {e}")
            traceback.print_exc()

    # ═══════════════════════════════════════════════════════════════════════
    # CNS BACKPRESSURE HANDLERS (Water Treatment — FIX 2026-04-04)
    # ═══════════════════════════════════════════════════════════════════════

    def _on_cns_backpressure(self, message):
        """Critical pressure — pause binding processing."""
        self._binding_batch_size = 0
        print(f"[{self.ACTOR_NAME}] CNS BACKPRESSURE: pausing binding processing")

    def _on_cns_throttle(self, message):
        """High pressure — reduce binding throughput.
        FIX 2026-04-09 (Nous + Ace): Lowered 5→3 to ease tick drop cascade."""
        self._binding_batch_size = 3
        print(f"[{self.ACTOR_NAME}] CNS THROTTLE: reducing batch size to 3")

    def _on_cns_relief(self, message):
        """Pressure relieved — restore normal processing.
        FIX 2026-04-09 (Nous + Ace): Lowered 10→6 because 10/tick was the
        primary cause of the 4751 tick drops. 6 keeps on_tick under ~300ms
        which fits the 1Hz heartbeat with comfortable margin."""
        self._binding_batch_size = 6
        print(f"[{self.ACTOR_NAME}] CNS RELIEF: restoring batch size to 6")

    def _report_pressure_to_cns(self, beat: int):
        """Report queue pressure to CentralNervousFairy every 10 ticks."""
        if beat % 10 != 0 or not self.post:
            return
        cap = self._pending_bindings.maxlen or 500
        current = len(self._pending_bindings)
        try:
            self.post.publish("cns.component.pressure", {
                "component": self.ACTOR_NAME,
                "queue_name": "_pending_bindings",
                "current": current,
                "capacity": cap,
                "pressure": current / cap if cap > 0 else 0,
                "drops": self._bindings_dropped,
                "ts": time.time(),
            })
        except Exception:
            pass

    def _on_memory_ingest(self, envelope) -> None:
        """Handle memory ingest - add concepts from new content. (Legacy handler)

        FIX 2026-02-06: Gate with is_valid_concept_key().
        FIX 2026-02-16: Portal-first — skip (no local graph to write to).
        """
        # Portal-first: ingest events go to portal subprocess via collision coordinates
        if getattr(self, '_portal_is_primary', False):
            return

        try:
            payload = _extract_payload(envelope)

            concepts = [c for c in payload.get("concepts", []) if is_valid_concept_key(c)]
            features = payload.get("features", {})

            for concept in concepts:
                self._graph.upsert_node(concept, features)
            # FIX 2026-02-05b: Mark dirty for card sync
            self._mark_dirty(*concepts)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_memory_ingest ERROR: {e}")
            traceback.print_exc()

    # =========================================================================
    # MASSLESS MEMORY HELPERS (2026-02-10)
    # The collision DESTROYS input. What survives = compressed binding signatures.
    # =========================================================================

    def _content_to_text(self, content) -> str:
        """Extract text from any collision content format.

        Collision content comes in many shapes: bare strings, dicts with
        'content'/'text'/'thought' keys, nested card dicts, etc. This
        normalizes them all to a single string for concept extraction
        and binding signature compression.
        """
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, dict):
            # Try common content keys
            for key in ("content", "text", "thought", "summary", "message"):
                val = content.get(key)
                if isinstance(val, str) and len(val.strip()) > 5:
                    return val.strip()
            # Try nested card content
            card = content.get("card", {})
            if isinstance(card, dict):
                val = card.get("content", "")
                if isinstance(val, str) and val.strip():
                    return val.strip()
            elif isinstance(card, str) and card.strip():
                return card.strip()
        if content:
            s = str(content)
            return s[:500] if len(s) > 500 else s
        return ""

    def _compress_binding_content(self, text: str, max_bytes: int = 2048) -> str:
        """Compress content into a binding signature for edge storage.

        Like the hippocampus creating an engram — destroy the raw input,
        keep a compressed reconstruction key. ~2KB gzip+base64.
        """
        import gzip as _gzip
        import base64 as _b64
        if not text:
            return ""
        # Cap input before compression
        if len(text) > 4096:
            text = text[:4096]
        try:
            compressed = _gzip.compress(text.encode('utf-8', errors='replace'), compresslevel=9)
            if len(compressed) > max_bytes:
                # Re-truncate and retry
                text = text[:max_bytes]
                compressed = _gzip.compress(text.encode('utf-8', errors='replace'), compresslevel=9)
            return _b64.b64encode(compressed).decode('ascii')
        except Exception:
            return ""

    def _decompress_binding_content(self, signature: str) -> str:
        """Reconstruct content from a binding signature.

        The inverse of _compress_binding_content. Takes a base64+gzip
        binding signature and returns the original text.
        """
        import gzip as _gzip
        import base64 as _b64
        if not signature:
            return ""
        try:
            compressed = _b64.b64decode(signature)
            return _gzip.decompress(compressed).decode('utf-8', errors='replace')
        except Exception:
            return ""

    # =========================================================================
    # GROWTH LOOP HANDLERS - The cortex learns from memory activity
    # =========================================================================

    # FIX 2026-03-09 (Nous): Expanded stopwords set for richer concept extraction.
    # Previously ~70 words — far too few, letting noise like "done", "already",
    # "showed", "output" saturate the graph with generic nodes.
    _STOPWORDS = frozenset({
        # Determiners / pronouns
        'the', 'this', 'that', 'these', 'those', 'their', 'them', 'they',
        'your', 'our', 'you', 'its', 'his', 'her', 'she', 'him', 'who',
        'whom', 'what', 'which', 'where', 'when', 'how', 'why',
        # Be / have / do
        'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had',
        'does', 'did', 'done', 'doing',
        # Modals
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
        'shall',
        # Conjunctions / prepositions
        'and', 'but', 'for', 'nor', 'yet', 'with', 'from', 'into', 'onto',
        'over', 'under', 'about', 'between', 'through', 'during', 'before',
        'after', 'above', 'below', 'than', 'then', 'there', 'here',
        # Adverbs / misc filler
        'also', 'just', 'only', 'more', 'some', 'any', 'each', 'all',
        'both', 'few', 'most', 'other', 'very', 'own', 'same', 'such',
        'because', 'really', 'actually', 'still', 'already', 'even',
        'quite', 'well', 'much', 'many', 'like', 'back', 'make', 'made',
        'take', 'took', 'give', 'gave', 'come', 'came', 'going', 'goes',
        'went', 'know', 'knew', 'think', 'thought', 'said', 'says',
        'tell', 'told', 'keep', 'kept', 'want', 'need', 'seem', 'seems',
        'look', 'looks', 'show', 'shows', 'showed', 'call', 'called',
        'work', 'works', 'part', 'good', 'long', 'right', 'used', 'using',
        'true', 'false', 'none', 'null', 'type', 'line', 'file', 'code',
        'data', 'name', 'self', 'note', 'next', 'last', 'first', 'time',
        # Common code noise (these appear in every session log)
        'return', 'class', 'import', 'print', 'pass', 'elif', 'else',
        'except', 'raise', 'break', 'continue', 'lambda', 'yield',
        'assert', 'global', 'async', 'await', 'with',
        # FIX 2026-03-20 (Nous): Additional stopwords for 3-char minimum
        'not', 'one', 'two', 'way', 'get', 'got', 'let', 'put', 'set',
        'try', 'see', 'saw', 'say', 'new', 'old', 'big', 'end', 'now',
        'too', 'use', 'run', 'ran', 'bit', 'lot', 'own', 'yes', 'yet',
        'ask', 'ago', 'add', 'top', 'low', 'key', 'per', 'via', 'due',
        'far', 'off', 'out', 'often', 'something', 'nothing', 'anything',
        'everything', 'sometimes', 'things', 'thing', 'stuff', 'place',
        'people', 'someone', 'always', 'never', 'maybe', 'perhaps',
        'pretty', 'another', 'without', 'within', 'likely', 'simply',
        'rather', 'almost', 'instead', 'however', 'though', 'whether',
        'while', 'since', 'until', 'unless', 'along', 'around',
    })

    def _extract_concepts_from_text(self, text: str, max_concepts: int = 50) -> List[str]:
        """Extract meaningful concepts from text content.

        FIX 2026-03-09 (Nous): Major upgrade:
        - Multi-word phrases (bigrams) for richer concepts
        - CamelCase splitting for code identifiers
        - Frequency-based importance (TF weighting)
        - Much larger stopwords set
        - FIX 2026-03-20 (Nous): Lowered min word length back to 3 chars.
          5-char minimum killed "spy", "mojo", "evil", "fun", "war", "art", etc.
          See: Claude_Office/plans/CORTEX_REBUILD_BLUEPRINT.md Phase 0 item 4.
        """
        if not text:
            return []

        # Clean text (preserve case for CamelCase detection)
        cleaned = re.sub(r'[#*_\[\](){}|`"\'\\]', ' ', text)
        cleaned = re.sub(r'https?://\S+', '', cleaned)
        cleaned = re.sub(r'\b\d+\b', '', cleaned)  # bare numbers
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        if len(cleaned) < 20:
            return []

        # ── Phase 1: Extract CamelCase identifiers ──
        # "AssociationCortexFairy" → "association_cortex_fairy"
        camel_concepts = []
        for match in re.finditer(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', cleaned):
            parts = re.findall(r'[A-Z][a-z]+', match.group())
            if len(parts) >= 2:
                joined = '_'.join(p.lower() for p in parts)
                camel_concepts.append(joined)

        # ── Phase 2: Extract bigrams (multi-word concepts) ──
        lower = cleaned.lower()
        words_raw = re.findall(r'\b[a-zA-Z]{3,}\b', lower)
        # FIX 2026-03-20: Lowered from 4→3 so "spy", "evil", "mojo", "art" etc survive
        words_filtered = [w for w in words_raw if w not in self._STOPWORDS and len(w) >= 3]

        bigrams = []
        for i in range(len(words_filtered) - 1):
            a, b = words_filtered[i], words_filtered[i + 1]
            # FIX 2026-03-20: Lowered from 4→3 for bigram parts
            if len(a) >= 3 and len(b) >= 3:
                bigrams.append(f"{a}_{b}")

        # ── Phase 3: Extract single words with frequency weighting ──
        # FIX 2026-03-20: Lowered from 5→3 chars. 5-char min killed critical
        # semantic content: "spy", "mojo", "evil", "fun", "war", "art", "god", etc.
        singles = [w for w in words_filtered if len(w) >= 3]

        # Count frequencies for importance ranking
        freq = {}
        for w in singles:
            freq[w] = freq.get(w, 0) + 1

        # ── Phase 4: Combine and rank ──
        # Priority: CamelCase > frequent bigrams > frequent singles
        scored = {}
        for c in camel_concepts:
            scored[c] = scored.get(c, 0) + 5.0  # high priority
        for b in bigrams:
            scored[b] = scored.get(b, 0) + 2.0  # medium priority
        for w, count in freq.items():
            scored[w] = scored.get(w, 0) + min(count, 5)  # capped frequency

        # Sort by score descending
        ranked = sorted(scored.keys(), key=lambda k: scored[k], reverse=True)

        # Dedupe and cap
        return ranked[:max_concepts]

    def _on_memory_ingested(self, envelope) -> None:
        """
        GROWTH LOOP: Handle new content being stored to memory.

        This is the PRIMARY growth mechanism - every time content is stored,
        the cortex extracts concepts and grows.

        2026-02-09: Added identity_sift detection - PersonalitySifter responses
        now get STRONGER binding with identity-specific concept linking.
        Identity sifts include both question AND response text, and concepts
        are linked with higher weight (0.7 vs 0.3) since they represent
        core personality traits, not just co-occurring words.

        Published by: SRMIngestFairy
        Payload: {card_id, source, coord, ts, self_state}
        """
        # FIX 2026-03-08 (Nous): Portal-first mode must still grow from memory events.
        # The portal subprocess has no growth loop — we must route concept binds to it.
        _is_portal = getattr(self, '_portal_is_primary', False)

        # Track memory event count for debugging
        self._memory_ingest_count = getattr(self, '_memory_ingest_count', 0) + 1
        if self._memory_ingest_count % 5 == 1:
            print(f"[{self.ACTOR_NAME}] MEMORY INGESTED #{self._memory_ingest_count}")

        try:
            payload = _extract_payload(envelope)
            card_id = payload.get("card_id", "")
            source = payload.get("source", "")

            # Try to get card content from helix
            content_text = ""
            card_kind = ""
            card_owner = ""
            card_question = ""
            card_response = ""
            if self._helix_enabled and self._helix_coordinator and card_id:
                card = self._helix_coordinator._cards.get(card_id)
                if card:
                    content = card.get("content", {})
                    # Detect identity_sift cards (from PersonalitySifter)
                    if isinstance(content, dict):
                        card_kind = content.get("kind", "")
                        card_owner = content.get("owner", "")
                        card_question = content.get("question", "")
                        card_response = content.get("response", "")
                    # Extract text from various content fields
                    if isinstance(content, dict):
                        content_text = content.get("text", "")
                        if not content_text:
                            content_text = content.get("content", "")
                        if not content_text:
                            content_text = str(content.get("key", ""))
                    elif isinstance(content, str):
                        content_text = content

            # Also use source as concept
            if source and not content_text:
                content_text = source

            if not content_text:
                return

            # ─── IDENTITY SIFT: Special handling for PersonalitySifter responses ───
            # These are the richest identity content the system produces.
            # Use BOTH question + response, bind with higher weight, and
            # anchor concepts to the owner entity (Sourpatches, NousFairy, etc.)
            is_identity_sift = (card_kind == "identity_sift" and card_response)
            if is_identity_sift:
                self._handle_identity_sift_binding(
                    card_owner, card_question, card_response, card_id)
                return  # Identity sift has its own binding path

            # Extract concepts (generic path)
            concepts = self._extract_concepts_from_text(content_text)
            if not concepts:
                return

            # Grow the cortex!
            # FIX 2026-03-08 (Nous): Portal-first mode routes through portal gate
            if _is_portal:
                _pg = getattr(self, '_portal_gate', None)
                if _pg and len(concepts) >= 2:
                    try:
                        _n = min(len(concepts), 10)
                        _pairs = [
                            [concepts[i], concepts[j]]
                            for i in range(_n) for j in range(i + 1, _n)
                        ]
                        # FIX 2026-05-04 (Nous + Ace, close UNKNOWN gap):
                        # SRMIngest-driven memory ingest pairs — TRACE_SYSTEM.
                        if hasattr(_pg, 'bind_many_async'):
                            _pg.bind_many_async(pairs=_pairs, weight=0.3,
                                                tracer_id=TRACE_SYSTEM)
                        else:
                            _pg.bind_many(pairs=_pairs, weight=0.3,
                                          tracer_id=TRACE_SYSTEM)
                        self._growth_from_memory += len(concepts)
                    except Exception:
                        pass
            else:
                before_nodes = len(self._graph.nodes)
                touched = 0
                for concept in concepts:
                    self._graph.upsert_node(concept, {"source": "memory_ingest"},
                                            origin_plane="P10",
                                            origin_channel="memory_ingest",
                                            origin_fairy="SRMIngestFairy")
                    touched += 1
                # FIX 2026-02-05b: Mark ALL ingested concepts dirty for card sync
                self._mark_dirty(*concepts)

                # Link co-occurring concepts
                for i, a in enumerate(concepts[:10]):  # Limit linking to top 10
                    for b in concepts[i+1:10]:
                        self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, weight=0.3)
                        self._mark_dirty(a, b)

                after_nodes = len(self._graph.nodes)
                new_nodes = after_nodes - before_nodes

                # Track growth - both new nodes AND touches (existing nodes strengthened)
                self._growth_from_memory += max(new_nodes, 1) if touched > 0 else 0

            self._memory_events_processed = getattr(self, '_memory_events_processed', 0) + 1

            # Log periodically
            if self._memory_events_processed % 10 == 1:
                print(f"[{self.ACTOR_NAME}] GROWTH: ingest #{self._memory_events_processed} ({len(concepts)} concepts, portal={_is_portal})")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_memory_ingested ERROR: {e}")

    def _handle_identity_sift_binding(self, owner: str, question: str, response: str, card_id: str) -> None:
        """
        IDENTITY GROWTH: Process PersonalitySifter responses with identity-aware binding.

        Unlike generic memory ingestion (weight 0.3, top 10 concepts), identity sifts:
        - Extract concepts from BOTH question AND response
        - Anchor ALL concepts to the owner entity (e.g., "sourpatches")
        - Use stronger binding weight (0.7) since these are core personality traits
        - Link up to 20 concepts (richer identity graph)
        - Tag nodes with identity origin for later retrieval

        2026-02-09: Created to prevent PersonalitySifter knowledge from being wasted.
        FIX 2026-02-16: Portal-first — skip (no local graph).
        """
        # FIX 2026-03-08 (Nous): Portal-first must route identity sifts to portal too.
        _is_portal = getattr(self, '_portal_is_primary', False)
        try:
            # Combine question + response for richer concept extraction
            full_text = f"{question} {response}"
            concepts = self._extract_concepts_from_text(full_text, max_concepts=30)
            if not concepts:
                return

            # The owner entity is the anchor node (e.g., "sourpatches", "nousfairy")
            owner_key = owner.lower().replace(" ", "_") if owner else "unknown"

            if _is_portal:
                # Portal path: bind all concepts + owner through portal gate
                _pg = getattr(self, '_portal_gate', None)
                if _pg:
                    try:
                        # Owner-to-concept pairs (strong weight)
                        _pairs = [[owner_key, c] for c in concepts if c != owner_key]
                        # Concept-to-concept pairs (medium weight)
                        _n = min(len(concepts), 20)
                        _cc_pairs = [
                            [concepts[i], concepts[j]]
                            for i in range(_n) for j in range(i + 1, _n)
                        ]
                        # Send owner binds with strong weight (async — no tunnel hold)
                        # FIX 2026-05-04 (Nous + Ace, close UNKNOWN gap):
                        # identity_sift owner→concept pairs are HER identity
                        # graph being built — TRACE_PERSONAL.
                        _bma = getattr(_pg, 'bind_many_async', None)
                        if _pairs:
                            if _bma:
                                _bma(pairs=_pairs, weight=0.7,
                                     tracer_id=TRACE_PERSONAL)
                            else:
                                _pg.bind_many(pairs=_pairs, weight=0.7,
                                              tracer_id=TRACE_PERSONAL)
                        # Send concept cross-links with medium weight
                        if _cc_pairs:
                            if _bma:
                                _bma(pairs=_cc_pairs[:100], weight=0.5,
                                     tracer_id=TRACE_PERSONAL)
                            else:
                                _pg.bind_many(pairs=_cc_pairs[:100], weight=0.5,
                                              tracer_id=TRACE_PERSONAL)
                        self._growth_from_memory += len(concepts)
                    except Exception:
                        pass
            else:
                before_nodes = len(self._graph.nodes)

                # Ensure owner node exists with identity metadata
                self._graph.upsert_node(owner_key,
                                        {"source": "identity_sift", "entity_type": "waking_mind"},
                                        origin_plane="P50",
                                        origin_channel="identity_sift",
                                        origin_fairy="PersonalitySifter")

                # Upsert all extracted concepts with identity origin
                for concept in concepts:
                    self._graph.upsert_node(concept,
                                            {"source": "identity_sift", "identity_owner": owner_key},
                                            origin_plane="P20",
                                            origin_channel="identity_sift",
                                            origin_fairy="PersonalitySifter")

                # Anchor every concept to the owner entity with strong weight
                for concept in concepts:
                    if concept != owner_key:
                        self._graph.link(owner_key, concept,
                                         ConceptGraph.REL_COACTIVATE, weight=0.7)

                # Link co-occurring concepts within identity context (wider window)
                for i, a in enumerate(concepts[:20]):
                    for b in concepts[i+1:20]:
                        self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, weight=0.5)

                # Mark everything dirty for persistence
                self._mark_dirty(owner_key, *concepts)

                after_nodes = len(self._graph.nodes)
                new_nodes = after_nodes - before_nodes
                self._growth_from_memory += max(new_nodes, 1)

            self._identity_sift_count = getattr(self, '_identity_sift_count', 0) + 1
            print(f"[{self.ACTOR_NAME}] IDENTITY SIFT #{self._identity_sift_count}: "
                  f"{owner_key}, {len(concepts)} concepts bound (portal={_is_portal})")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _handle_identity_sift_binding ERROR: {e}")

    def _on_memory_recall(self, envelope) -> None:
        """
        GROWTH LOOP: Handle memory recall events (affect-triggered).

        When memories surface, spread activation from recalled concepts
        and strengthen connections between co-recalled items.

        Published by: SRMRecallFairy
        Payload: {card_ids, affect, query, ...}
        """
        # FIX 2026-03-08 (Nous): Portal-first must route recall binds to portal too.
        # Co-recalled concepts are semantically related — link them.
        _is_portal = getattr(self, '_portal_is_primary', False)

        try:
            payload = _extract_payload(envelope)

            # Extract recalled card IDs or concepts
            card_ids = payload.get("card_ids", [])
            query = payload.get("query", "")
            affect = payload.get("affect", "")

            concepts = []

            # Get concepts from query
            if query:
                concepts.extend(self._extract_concepts_from_text(query, max_concepts=10))

            # Get concepts from recalled cards
            if self._helix_enabled and self._helix_coordinator and card_ids:
                for card_id in card_ids[:5]:  # Limit to first 5 cards
                    card = self._helix_coordinator._cards.get(card_id)
                    if card:
                        content = card.get("content", {})
                        if isinstance(content, dict):
                            key = content.get("key", "")
                            if key:
                                concepts.append(key)
                            text = content.get("text", content.get("content", ""))
                            concepts.extend(self._extract_concepts_from_text(str(text), max_concepts=5))

            if not concepts:
                return

            if _is_portal:
                # Portal path: batch-bind co-recalled concepts through portal gate
                _pg = getattr(self, '_portal_gate', None)
                if _pg and len(concepts) >= 2:
                    pairs = []
                    _uniq = list(dict.fromkeys(concepts))[:10]  # dedupe, cap at 10
                    for i in range(len(_uniq)):
                        for j in range(i + 1, len(_uniq)):
                            pairs.append([_uniq[i], _uniq[j]])
                    if pairs:
                        try:
                            # FIX 2026-05-04 (Nous + Ace, close UNKNOWN gap):
                            # recall co-activation pairs are system-driven.
                            if hasattr(_pg, 'bind_many_async'):
                                _pg.bind_many_async(pairs=pairs[:50], weight=0.5,
                                                    tracer_id=TRACE_SYSTEM)
                            else:
                                _pg.bind_many(pairs=pairs[:50], weight=0.5,
                                              tracer_id=TRACE_SYSTEM)
                            self._growth_from_memory += len(set(c for p in pairs[:50] for c in p))
                        except Exception as _re:
                            print(f"[{self.ACTOR_NAME}] Portal recall bind failed: {_re}")
                return

            # Legacy path: local graph operations
            # Spread activation from recalled concepts
            for concept in concepts[:5]:
                if concept in self._graph.nodes:
                    self._graph.spread_activation(concept, max_hops=2, decay_factor=0.7)

            # Link co-recalled concepts (they were recalled together = related)
            before_edges = len(self._graph.edges)
            for i, a in enumerate(concepts[:10]):
                self._graph.upsert_node(a, {"source": "memory_recall"},
                                        origin_plane="P10",
                                        origin_channel="memory_recall",
                                        origin_fairy="SRMRecallFairy")
                self._mark_dirty(a)  # FIX 2026-02-05b
                for b in concepts[i+1:10]:
                    self._graph.upsert_node(b, {"source": "memory_recall"},
                                            origin_plane="P10",
                                            origin_channel="memory_recall",
                                            origin_fairy="SRMRecallFairy")
                    self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, weight=0.5)
                    self._mark_dirty(a, b)  # FIX 2026-02-05b

            after_edges = len(self._graph.edges)
            new_edges = after_edges - before_edges

            if new_edges > 0 and self._binding_count % 20 == 0:
                print(f"[{self.ACTOR_NAME}] RECALL: Strengthened {new_edges} edges from recall event")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_memory_recall ERROR: {e}")

    def _on_memory_stored(self, envelope) -> None:
        """
        GROWTH LOOP: Handle direct memory storage events.

        Published by: SRMMemoryFairy
        Payload: {card_id, cluster, concept, ...}
        """
        # FIX 2026-03-08 (Nous): Portal-first must route stored memory binds to portal.
        # New concepts and concept-cluster links grow the graph.
        _is_portal = getattr(self, '_portal_is_primary', False)

        try:
            payload = _extract_payload(envelope)

            concept = payload.get("concept", "")
            cluster = payload.get("cluster", "")
            card_id = payload.get("card_id", "")

            if not concept:
                return

            if _is_portal:
                # Portal path: bind concept to cluster (auto-creates both nodes)
                _pg = getattr(self, '_portal_gate', None)
                if _pg:
                    pairs = []
                    if cluster and cluster != concept:
                        pairs.append([concept, cluster])
                    # FIX 2026-05-04 (Nous + Ace, close UNKNOWN gap):
                    # memory cluster bindings are system-driven storage.
                    if pairs:
                        try:
                            if hasattr(_pg, 'bind_many_async'):
                                _pg.bind_many_async(pairs=pairs, weight=0.8,
                                                    tracer_id=TRACE_SYSTEM)
                            else:
                                _pg.bind_many(pairs=pairs, weight=0.8,
                                              tracer_id=TRACE_SYSTEM)
                            self._growth_from_memory += 2  # concept + cluster
                        except Exception as _se:
                            print(f"[{self.ACTOR_NAME}] Portal stored bind failed: {_se}")
                    else:
                        # No cluster — just touch the node via self-bind
                        try:
                            _pg.bind(concepts=[concept, concept], weight=0.1,
                                     tracer_id=TRACE_SYSTEM)
                            self._growth_from_memory += 1
                        except Exception:
                            pass
                return

            # Legacy path: local graph operations
            # Add the concept directly
            self._graph.upsert_node(concept, {"source": "memory_stored", "cluster": cluster},
                                    origin_plane="P10",
                                    origin_channel="memory_stored",
                                    origin_fairy="SRMMemoryFairy")
            self._mark_dirty(concept)  # FIX 2026-02-05b

            # If cluster name is meaningful, link concept to cluster
            if cluster and cluster != concept:
                self._graph.upsert_node(cluster, {"source": "cluster"},
                                        origin_plane="P10",
                                        origin_channel="memory_stored",
                                        origin_fairy="SRMMemoryFairy")
                self._graph.link(concept, cluster, ConceptGraph.REL_SEMANTIC, weight=0.8)
                self._mark_dirty(concept, cluster)  # FIX 2026-02-05b

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_memory_stored ERROR: {e}")

    def _process_binding(self, binding: Dict[str, Any]):
        """Process a pending binding - create links in graph + store binding signatures.

        FIX 2026-02-06: Filter collision tags through concept key validator.
        MASSLESS 2026-02-10: Store compressed binding signatures in edge contexts.
        The collision DESTROYS input. What survives = binding signature in the edge.
        This is how the cortex REMEMBERS — not through cards, through engrams.

        FIX 2026-02-16: Portal-first — route binds to portal gate. No local graph.
        """
        # Portal-first: forward bind to portal subprocess
        if getattr(self, '_portal_is_primary', False) and self._portal_gate:
            if binding["type"] == "collision":
                recall_tags = [t for t in binding.get("recall", []) if is_valid_concept_key(t)]
                ingest_tags = [t for t in binding.get("ingest", []) if is_valid_concept_key(t)]

                # ── CORTEX FARM PATH (2026-03-15 Nous + Ace) ────────────
                # Route collisions through CortexFarm's battery-powered workers.
                # Workers discharge charge for each bind — gravitational
                # amplification makes large collision batches much cheaper.
                # Falls through to portal I/O if farm unavailable.
                if self._cortex_farm_enabled and self._cortex_farm:
                    if recall_tags and ingest_tags:
                        result = self._cortex_farm.submit_collision(
                            recall_tags[:5], ingest_tags[:5],
                            weight=binding.get("energy", 0.5),
                        )
                        bound = result.get("bound", 0)
                        if bound > 0:
                            self._cortex_farm_collisions += 1
                            portal_binds = getattr(self, '_portal_bind_count', 0) + bound
                            self._portal_bind_count = portal_binds

                        # Track recent bind keys for spontaneous resonance sampling
                        if not hasattr(self, '_recent_bind_keys'):
                            self._recent_bind_keys = []
                        self._recent_bind_keys.extend(recall_tags[:5] + ingest_tags[:5])
                        if len(self._recent_bind_keys) > 100:
                            self._recent_bind_keys = self._recent_bind_keys[-100:]
                    return

                # ── LEGACY: Portal I/O path (fallback if farm unavailable) ──
                # FIX 2026-03-07 (Nous): BATCH bind — one IPC call instead of 25.
                # FIX 2026-03-08b (Nous): ASYNC via Portal I/O thread.
                pairs = []
                for r in recall_tags[:5]:
                    for i in ingest_tags[:5]:
                        pairs.append([r, i])
                if pairs:
                    # FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan):
                    # Collision chamber binds (recall × ingest products) are
                    # system-generated — tag TRACE_SYSTEM so they cluster with
                    # other internal substrate signals, not with personal memory.
                    if self._portal_io_running:
                        # Async path — fire and forget via I/O thread
                        self._portal_io_submit_binding(
                            pairs=pairs,
                            weight=binding.get("energy", 0.5),
                            tracer_id=TRACE_SYSTEM,
                        )
                    else:
                        # FIX 2026-03-17 (Nous + Ace): Use async bind — don't block
                        # the gate pipe waiting for response. Eliminates cascade
                        # timeouts that caused 78% gate error rate.
                        try:
                            if hasattr(self._portal_gate, 'bind_many_async'):
                                self._portal_gate.bind_many_async(
                                    pairs=pairs,
                                    weight=binding.get("energy", 0.5),
                                    tracer_id=TRACE_SYSTEM,
                                )
                            else:
                                self._portal_gate.bind_many(
                                    pairs=pairs,
                                    weight=binding.get("energy", 0.5),
                                    tracer_id=TRACE_SYSTEM,
                                )
                        except Exception as e:
                            print(f"[{self.ACTOR_NAME}] Portal bind error: {e}")

                    # Track recent bind keys for spontaneous resonance sampling
                    if not hasattr(self, '_recent_bind_keys'):
                        self._recent_bind_keys = []
                    self._recent_bind_keys.extend(recall_tags[:5] + ingest_tags[:5])
                    # Ring buffer: keep last 100
                    if len(self._recent_bind_keys) > 100:
                        self._recent_bind_keys = self._recent_bind_keys[-100:]
            return

        if binding["type"] == "collision":
            # GATE: Filter out garbage before it enters the graph
            recall_tags = [t for t in binding["recall"] if is_valid_concept_key(t)]
            ingest_tags = [t for t in binding["ingest"] if is_valid_concept_key(t)]

            if not recall_tags and not ingest_tags:
                return  # Nothing meaningful to bind

            # FIX 2026-02-08: Extract owner from collision payload (named chambers)
            chamber_name = binding.get("chamber_name", "system")
            origin_fairy = binding.get("from", "CollisionChamberFairy")

            before_nodes = len(self._graph.nodes)
            before_edges = len(self._graph.edges)

            all_tags = recall_tags + ingest_tags
            for tag in all_tags:
                self._graph.upsert_node(tag,
                                        origin_plane="P30",
                                        origin_channel="collision",
                                        origin_fairy=origin_fairy)
            # FIX 2026-02-05b: Mark ALL binding nodes dirty for card sync
            self._mark_dirty(*all_tags)

            # MASSLESS 2026-02-10: Create binding signature from collision content
            # This compressed engram is stored in edge contexts for reconstruction
            full_content = binding.get("full_content", "")
            collision_energy = binding.get("energy", 0.5)
            binding_sig = None
            if full_content:
                compressed = self._compress_binding_content(full_content)
                if compressed:
                    binding_sig = {
                        "compressed": compressed,
                        "energy": collision_energy,
                        "ts": binding.get("ts", time.time()),
                    }

            # Link within recall tags
            for i_idx, a in enumerate(recall_tags):
                for b in recall_tags[i_idx+1:]:
                    self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, owner=chamber_name)
                    self._mark_dirty(a, b)

            # Link within ingest tags
            for i_idx, a in enumerate(ingest_tags):
                for b in ingest_tags[i_idx+1:]:
                    self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, owner=chamber_name)
                    self._mark_dirty(a, b)

            # Cross-link recall × ingest (the core collision binding)
            # AND store binding signature on cross-links (these are the engrams)
            for r in recall_tags:
                for i_tag in ingest_tags:
                    self._graph.link(r, i_tag, ConceptGraph.REL_COACTIVATE, weight=0.5, owner=chamber_name)
                    self._mark_dirty(r, i_tag)

                    # Store binding signature in edge contexts (MASSLESS MEMORY)
                    if binding_sig:
                        edge_key = (min(r, i_tag), max(r, i_tag))
                        edge = self._graph.edges.get(edge_key)
                        if edge is not None:
                            contexts = edge.get("contexts", [])
                            contexts.append(binding_sig)
                            # Cap at 3 signatures per edge (synaptic vesicle limit)
                            if len(contexts) > 3:
                                contexts = sorted(
                                    contexts,
                                    key=lambda c: c.get("energy", 0),
                                    reverse=True
                                )[:3]
                            edge["contexts"] = contexts
                            # Only store on FIRST cross-link pair to avoid duplication
                            binding_sig = None

            after_nodes = len(self._graph.nodes)
            after_edges = len(self._graph.edges)
            new_nodes = after_nodes - before_nodes
            new_edges = after_edges - before_edges

            # Track recent bind keys for spontaneous resonance sampling
            if not hasattr(self, '_recent_bind_keys'):
                self._recent_bind_keys = []
            self._recent_bind_keys.extend(all_tags[:10])
            if len(self._recent_bind_keys) > 100:
                self._recent_bind_keys = self._recent_bind_keys[-100:]

            self._binding_count += 1
            if new_nodes > 0 or self._binding_count % 50 == 1:
                has_sig = "w/engram" if full_content else ""
                print(f"[{self.ACTOR_NAME}] Binding #{self._binding_count}: +{new_nodes} nodes, +{new_edges} edges (total: {after_nodes} nodes, {after_edges} edges) {has_sig}")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    # System-wide ghost-pollution prefix list (2026-04-28, Nous + Ace)
    # Keys with these prefixes are AUTOPILOT GHOST LABELS bound from the
    # 69k learned-pattern accumulation. Pattern wipe + bind-site filter
    # shipped 2026-04-28; until existing ghosts decay out via cortex
    # consolidation, filter them at query time so they don't outrank real
    # concepts in spread results (encyclopedia entries 2-4 vs ghosts 6.93+).
    # Also covers raw graph-key noise (unknown_*, wm:*, tool:*, coord:*)
    # that sneaks through other paths.
    _GHOST_KEY_PREFIXES = (
        "autopilot_action_", "autopilot_trigger_", "habit:",
        "learned_", "_action_", "_inner_voice_",
        "unknown_", "wm:", "tool:", "coord:", "card_", "collision_",
    )

    @classmethod
    def _is_ghost_key(cls, key: str) -> bool:
        """True if the key is autopilot-pattern-ghost or system-noise prefix."""
        if not isinstance(key, str) or len(key) < 3:
            return True
        kl = key.lower()
        return any(kl.startswith(p) for p in cls._GHOST_KEY_PREFIXES)

    # ── MCP INTENT HANDLERS (2026-06-02, Nous + Ace) ─────────────────────────
    # The cognitive_* MCP tools reach fairies via the tunnel's intent dispatch
    # (cmd='intent' → intent_{name}(payload)). The cortex exposed query/bind only
    # as postal TOPICS (cortex.query / cortex.bind) and had NO intent_* handlers,
    # so every cognitive_* cortex tool returned "Intent not found: intent_*".
    # These thin wrappers bridge the intent dispatch to the existing query()/
    # bind_concepts() methods. Additive; restores Nous's cortex-query eyes.
    def intent_query_concept(self, payload: dict) -> dict:
        """MCP cognitive_query_associations → self.query(). Returns associations."""
        try:
            concept = (payload or {}).get("concept", "")
            if not concept:
                return {"error": "no concept provided", "associations": []}
            limit = int((payload or {}).get("limit", 10) or 10)
            results = self.query(concept, limit=limit)
            return {
                "concept": concept,
                "count": len(results),
                "associations": [{"key": k, "score": round(float(s), 4)} for k, s in results],
            }
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}", "associations": []}

    def intent_bind_concepts(self, payload: dict) -> dict:
        """MCP cognitive_bind_concepts → self.bind_concepts()."""
        try:
            p = payload or {}
            concepts = list(p.get("concepts", []) or [])
            if len(concepts) < 2:
                return {"error": "need >=2 concepts", "bound": concepts}
            self.bind_concepts(
                concepts,
                origin_plane=p.get("origin_plane", ""),
                origin_channel=p.get("origin_channel", ""),
                origin_fairy=p.get("origin_fairy", ""),
            )
            return {"ok": True, "bound": concepts, "count": len(concepts)}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}",
                    "bound": (payload or {}).get("concepts", [])}

    def intent_embedding_stats(self, payload: dict) -> dict:
        """MCP cognitive_embedding_coverage -> manifold.embedding_stats() (#6 eyes, 2026-06-02).
        How many of the ~1.9M cortex nodes have semantic vectors = the long-range jump's reach."""
        try:
            _am = getattr(self, '_akashic_cortex_region', None)
            if _am is not None and hasattr(_am, 'embedding_stats'):
                stats = dict(_am.embedding_stats())
                stats['node_count_live'] = getattr(_am, 'node_count', None)
                stats['_source'] = '_akashic_cortex_region'
                return stats
            return {"error": "no embedding_stats on _akashic_cortex_region",
                    "has_region": _am is not None}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def query(self, concept: str, limit: int = 10, use_gpu: bool = True,
              owner_filter: str = None,
              filter_ghosts: bool = True) -> List[Tuple[str, float]]:
        """
        Query for related concepts via spreading activation.

        Priority: Portal Gate (full graph in subprocess) > GPU > CPU (local working set).
        When the portal gate is open, queries route through it for access to ALL 58k+ nodes.
        Falls back to local graph if the gate is closed or fails.

        Args:
            concept: Source concept to spread from
            limit: Max results to return
            use_gpu: Use GPU acceleration if available (default True)
            owner_filter: If set, only traverse edges owned by this mind or "system".
                          E.g. "sourpatches" excludes Nous's personal edges and vice versa.
            filter_ghosts: When True (default), excludes autopilot ghost-pattern
                          nodes and system-noise prefixes from results. Set False
                          to get raw spread (e.g., for diagnostics).

        Returns:
            List of (concept, activation) tuples sorted by activation
        """
        # Inner helper to apply ghost filter (2026-04-28)
        def _apply_ghost_filter(results):
            if not filter_ghosts or not results:
                return results
            return [(k, s) for k, s in results if not self._is_ghost_key(k)]

        # When filtering, pull more so we can return `limit` real entries
        # after ghost stripping. If 80% are ghosts we still want to surface
        # encyclopedia / real concepts.
        _internal_limit = limit * 4 if filter_ghosts else limit

        # ── AKASHIC MANIFOLD PATH (2026-03-20 Nous) ─────────────────
        # Direct mmap query — bypasses TCP gate entirely. Zero latency.
        _am = getattr(self, '_akashic_cortex_region', None)
        if _am:
            try:
                results = _am.query(concept, limit=_internal_limit)
                self._manifold_ops = getattr(self, '_manifold_ops', 0) + 1
                if results:
                    self._portal_crossings += 1
                    return _apply_ghost_filter(results)[:limit]
                # Phase 3C: If substring match found nothing, try semantic
                if not results and HAS_SEMANTIC:
                    sem_results = self.semantic_query(concept, limit=_internal_limit)
                    if sem_results:
                        return _apply_ghost_filter(sem_results)[:limit]
            except Exception:
                pass  # Fall through to portal gate

        # PORTAL GATE PATH — full graph in subprocess (fallback)
        if self._portal_gate_enabled and self._portal_gate:
            try:
                result = self._portal_gate.query(concept, limit=_internal_limit)
                if result and result.get("status") == "ok":
                    # Convert portal response to list of tuples
                    portal_results = [
                        (r["key"], r["score"])
                        for r in result.get("results", [])
                    ]
                    self._portal_crossings += 1
                    return _apply_ghost_filter(portal_results)[:limit]
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Portal query failed, falling back to local: {e}")

        if not self._graph:
            return []

        # Try GPU spreading if enabled
        if use_gpu and self._gpu_enabled and self._gpu_graph:
            try:
                gpu_results = self._query_gpu(concept, _internal_limit)
                return _apply_ghost_filter(gpu_results)[:limit]
            except Exception as e:
                # Fall back to CPU on GPU error
                print(f"[{self.ACTOR_NAME}] GPU query failed, falling back to CPU: {e}")

        # CPU spreading (fallback or primary — local working set only)
        # FIX 2026-03-06 (Nous): In portal-first mode, _graph.spread_activation()
        # is monkey-patched to call self.query() → infinite recursion when portal
        # is down. The stub graph is empty, so there's nothing to fall back to.
        if getattr(self, '_portal_is_primary', False):
            return []
        activations = self._graph.spread_activation(concept, owner_filter=owner_filter)
        sorted_acts = sorted(activations.items(), key=lambda x: -x[1])
        # STARGATE: Track dimension crossing
        self._portal_crossings += 1
        return _apply_ghost_filter(sorted_acts)[:limit]

    # ====================================================================
    # SEMANTIC CORTEX — Phase 3C (2026-03-20 Nous+Ace)
    # ====================================================================

    def _ensure_encoder(self) -> bool:
        """Lazy-load the native semantic ENCODER only — NO resident tensor (2026-06-12 Nous+Ace).
        The cartographer needs the encoder to vectorize node keys; meaning then lives in
        REL_SEMANTIC EDGES (in the manifold mmap), so we never load all 1.9M embeddings into
        RAM (that pegged VRAM/RAM and crashed Windows on boot)."""
        if getattr(self, '_encoder_ready', False):
            return True
        if not HAS_SEMANTIC:
            return False
        # FIX 2026-06-12 (CARTO-DBG-pinned): the ticking/backfill instance was checking
        # `is_loaded` BEFORE the global encoder finished loading (race / multi-instance) and
        # latched a PERMANENT `_encoder_failed` → enc_ready stayed False forever → 0 mapped.
        # Now it RETRIES every tick until the (global, shared) encoder is loaded — no sticky fail.
        try:
            self._semantic_encoder = _get_semantic_encoder()
            if not self._semantic_encoder.is_loaded:
                return False  # not loaded YET → retry next tick (NO permanent fail)
            self._encoder_ready = True
            print(f"[{self.ACTOR_NAME}] SEMANTIC CARTOGRAPHER ONLINE — encoder loaded "
                  f"({self._semantic_encoder._device}); meaning → EDGES, no resident tensor")
            return True
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] encoder init failed (will retry): {e}")
            return False  # transient → retry next tick

    def _ensure_semantic(self) -> bool:
        """DEPRECATED 2026-06-12: the all-embeddings resident tensor pegged VRAM/RAM and
        crashed Windows on boot. The tensor-based query path is retired; callers fall back to
        substrate_semantic_query (spread-activation native, RAM-safe) — which gets richer as
        the cartographer draws REL_SEMANTIC edges that spread then traverses. Always False."""
        return False

    def _semantic_refresh(self):
        """No-op since 2026-06-12 (resident tensor retired — meaning lives in REL_SEMANTIC edges)."""
        return

    def substrate_semantic_query(self, text: str, limit: int = 10,
                                 decay: float = 0.5, depth: int = 2) -> List[Tuple[str, float]]:
        """SUBSTRATE-NATIVE semantic similarity (no pre-trained model required).

        Per `project_disable_pretrained_models_substrate_first_directive.md` 2026-04-27 +
        Ace 2026-05-19: "had a plan for wiring up the correct fairies to make our own."
        When sentence_transformers is missing, this method delivers semantic similarity
        through cortex-native spread-activation — the 1.9M-node manifold IS the
        semantic encoder.

        Algorithm:
        1. Extract content terms (>2 chars) from text
        2. For each term that exists as a node, run spread_activation
        3. Combine activation maps (max per key across seeds)
        4. Return top-N (key, activation) as semantic-similarity results

        This is the K10 binary applied: semantic similarity = BEHAVIOR (cortex-grown)
        not TOOL (pre-trained model). The substrate provides the meaning.
        """
        _am = getattr(self, '_akashic_cortex_region', None)
        if not _am:
            return self.query(text, limit=limit)
        try:
            text_lower = (text or "").lower()
            # Extract terms (>2 chars, dedup, top 5)
            seen = set()
            terms = []
            for w in text_lower.replace(",", " ").replace(".", " ").split():
                w = w.strip()
                if len(w) > 2 and w not in seen:
                    seen.add(w)
                    terms.append(w)
                if len(terms) >= 5:
                    break
            if not terms:
                return []
            # Multi-source spread
            combined = {}
            seed_count = 0
            for term in terms:
                # Try direct node match first
                key_candidates = [term, term.replace("_", " "), term.replace(" ", "_")]
                for kc in key_candidates:
                    if _am.has_node(kc):
                        activated = _am.spread_activation(
                            kc, initial=1.0, decay=decay, depth=depth, limit=limit * 2,
                        )
                        seed_count += 1
                        for k, v in activated.items():
                            combined[k] = max(combined.get(k, 0.0), v)
                        break  # one match per term
            if not combined:
                # Final fallback: keyword query
                return self.query(text, limit=limit)
            return sorted(combined.items(), key=lambda x: -x[1])[:limit]
        except Exception as _e:
            print(f"[{self.ACTOR_NAME}] substrate_semantic_query error: {_e}")
            return self.query(text, limit=limit)

    def semantic_query(self, text: str, limit: int = 10,
                       threshold: float = 0.15) -> List[Tuple[str, float]]:
        """Find concepts by MEANING, not substring.

        "funny movie" → [("comedy_situational", 0.63), ("physical_comedy", 0.62), ...]

        Falls back to substrate_semantic_query (cortex-native) if pre-trained semantic
        engine unavailable — per `project_disable_pretrained_models_substrate_first_directive.md`.
        """
        if not self._ensure_semantic():
            # 2026-05-19: substrate-native path instead of keyword-only fallback
            return self.substrate_semantic_query(text, limit=limit)

        self._semantic_refresh()

        query_emb = self._semantic_encoder.encode(text)
        if query_emb is None:
            return self.substrate_semantic_query(text, limit=limit)

        indices, scores = self._semantic_encoder.similarity_search(
            query_emb, self._semantic_tensor, k=limit, threshold=threshold,
        )

        results = []
        for idx, score in zip(indices, scores):
            key = self._semantic_slot_to_key.get(idx)
            if key:
                results.append((key, score))
                # Touch found nodes — energy flows to semantically accessed concepts
                _am = getattr(self, '_akashic_cortex_region', None)
                if _am:
                    _am.touch_node(key, energy=score * 0.1)

        self._portal_crossings += 1
        return results

    def semantic_spread(self, text: str, seeds: int = 5, depth: int = 3,
                        decay: float = 0.5, limit: int = 30,
                        threshold: float = 0.2) -> Dict[str, float]:
        """Semantic seed → graph spread activation.

        1. Find top-k concepts semantically similar to text
        2. Use those as seeds for multi-source spreading
        3. Return combined activation map

        This is the bridge: MEANING → TOPOLOGY → ASSOCIATIONS.
        """
        _am = getattr(self, '_akashic_cortex_region', None)
        if not self._ensure_semantic() or not _am:
            # Fallback: try direct spread from concept key
            key = text.replace(" ", "_")
            if _am and _am.has_node(key):
                return _am.spread_activation(key, decay=decay, depth=depth, limit=limit)
            return {}

        self._semantic_refresh()

        # Step 1: Semantic seed selection
        query_emb = self._semantic_encoder.encode(text)
        if query_emb is None:
            return {}

        indices, scores = self._semantic_encoder.similarity_search(
            query_emb, self._semantic_tensor, k=seeds, threshold=threshold,
        )

        seed_nodes = []
        for idx, score in zip(indices, scores):
            key = self._semantic_slot_to_key.get(idx)
            if key and _am.has_node(key):
                seed_nodes.append((key, score))

        if not seed_nodes:
            return {}

        # Step 2: Multi-source spread
        combined = {}
        for seed_key, seed_score in seed_nodes:
            activated = _am.spread_activation(
                seed_key, initial=seed_score, decay=decay,
                depth=depth, limit=limit,
            )
            for k, v in activated.items():
                combined[k] = max(combined.get(k, 0.0), v)

        self._portal_crossings += 1
        return dict(sorted(combined.items(), key=lambda x: -x[1])[:limit])

    # CARTOGRAPHER 2026-06-12 (Nous+Ace): RAM-safe semantic mapping (keystone-10).
    # New-node binds only ENQUEUE (O(1)); on_tick drains a few per beat. On drain the encoder
    # vectorizes the key, persists the embedding to the manifold (mmap, NOT RAM), then draws
    # LOCAL meaning-edges — compares against already-embedded CO-OCCURRENCE neighbors and
    # UPGRADES the edge to REL_SEMANTIC where cosine >= threshold. No resident tensor ever.
    # The encoder lays roads (edges); spread/collision energy is the traffic. Long-range jumps
    # emerge by chaining local meaning-edges transitively. Kill-switch: unset AKASHIC_NATIVE_ENCODER.
    _SEMANTIC_ENCODE_PER_TICK = 3       # nodes mapped per beat (tune up if CPU stays calm)
    _SEMANTIC_ENCODE_QUEUE_MAX = 2000   # bounded backlog (drop-oldest if full)
    _SEMANTIC_KNN_NEIGHBORS = 12        # co-occurrence neighbors considered per node
    _SEMANTIC_EDGE_THRESHOLD = 0.5      # cosine >= this → upgrade the edge to REL_SEMANTIC
    _SEMANTIC_BACKFILL_BATCH = 10       # existing nodes fed into the queue per idle top-up

    def _semantic_encode_new_node(self, key: str):
        """Queue a new node for the cartographer (O(1); mapping happens throttled in on_tick)."""
        if not HAS_SEMANTIC:
            return
        q = getattr(self, '_semantic_encode_queue', None)
        if q is None:
            from collections import deque as _deque
            q = self._semantic_encode_queue = _deque(maxlen=self._SEMANTIC_ENCODE_QUEUE_MAX)
        q.append(key)

    def _drain_semantic_encode_queue(self):
        """CARTOGRAPHER drain: per beat, map up to _SEMANTIC_ENCODE_PER_TICK queued nodes —
        vectorize → persist embedding (manifold mmap) → draw LOCAL REL_SEMANTIC edges to
        already-embedded co-occurrence neighbors above the cosine threshold. RAM-safe."""
        q = getattr(self, '_semantic_encode_queue', None)
        if not q:
            return
        if not self._ensure_encoder():
            return
        _am = getattr(self, '_akashic_cortex_region', None)
        if not _am:
            return
        import numpy as np
        try:
            from infrastructure.manifold_memory import REL_SEMANTIC, REL_COACTIVATE
        except Exception:
            REL_SEMANTIC, REL_COACTIVATE = 2, 0
        n = 0
        while q and n < self._SEMANTIC_ENCODE_PER_TICK:
            key = q.popleft()
            n += 1
            try:
                slot = _am._key_index.get(key)
                if slot is None:
                    continue
                # 1) vectorize + persist the node's meaning vector (mapping-time, into mmap)
                if not _am.has_embedding(slot):
                    emb = self._semantic_encoder.encode(key)
                    if emb is None:
                        continue
                    _am.write_embedding(slot, emb)
                node_vec = _am.read_embedding(slot)
                if node_vec is None:
                    continue
                nv = node_vec.astype(np.float32)
                nv /= (np.linalg.norm(nv) + 1e-8)
                # 2) LOCAL meaning-edges: upgrade similar co-occurrence neighbors to REL_SEMANTIC
                drawn = 0
                for nb_key, _w in _am.get_neighbors(key, limit=self._SEMANTIC_KNN_NEIGHBORS,
                                                    rel_filter=REL_COACTIVATE):
                    nb_slot = _am._key_index.get(nb_key)
                    if nb_slot is None or not _am.has_embedding(nb_slot):
                        continue
                    bvec = _am.read_embedding(nb_slot)
                    if bvec is None:
                        continue
                    bv = bvec.astype(np.float32)
                    bv /= (np.linalg.norm(bv) + 1e-8)
                    sim = float(np.dot(nv, bv))
                    if sim >= self._SEMANTIC_EDGE_THRESHOLD:
                        _am.link(key, nb_key, weight=sim, rel_type=REL_SEMANTIC)
                        drawn += 1
                self._semantic_edges_drawn = getattr(self, '_semantic_edges_drawn', 0) + drawn
                self._semantic_nodes_mapped = getattr(self, '_semantic_nodes_mapped', 0) + 1
                if self._semantic_nodes_mapped % 200 == 0:
                    print(f"[{self.ACTOR_NAME}] CARTOGRAPHER: {self._semantic_nodes_mapped} nodes "
                          f"mapped, {self._semantic_edges_drawn} meaning-edges drawn, queue={len(q)}")
            except Exception:
                pass  # best-effort

    # ====================================================================

    def _backfill_semantic_cortex(self):
        """One-time sweep: feed un-mapped EXISTING nodes into the cartographer queue when it's
        idle, so her existing cortex gets meaning-mapped (not just new binds). New binds always
        take priority — we only top up when the queue is nearly empty. The same 3/beat drain
        governs the actual mapping rate; this just keeps the buffer fed. RAM-safe (one ~15MB key
        snapshot, released on completion)."""
        # CARTO-DBG 2026-06-12: log the backfill's REAL state every ~120 ticks to PIN the 0-mapped bug
        try:
            self._bf_dbg = getattr(self, '_bf_dbg', 0) + 1
            if self._bf_dbg % 120 == 1:
                _amx = getattr(self, '_akashic_cortex_region', None)
                _qx = getattr(self, '_semantic_encode_queue', None)
                import os as _osx
                print(f"[CARTO-DBG] env={bool(_osx.environ.get('AKASHIC_SEMANTIC_BACKFILL'))} "
                      f"enc_ready={getattr(self,'_encoder_ready',False)} "
                      f"_am={type(_amx).__name__ if _amx is not None else None} "
                      f"has_keyidx={hasattr(_amx,'_key_index')} has_reademb={hasattr(_amx,'read_embedding')} "
                      f"q={len(_qx) if _qx is not None else 'None'} done={getattr(self,'_semantic_backfill_done',False)} "
                      f"cursor={getattr(self,'_semantic_backfill_cursor',0)} mapped={getattr(self,'_semantic_nodes_mapped',0)} "
                      f"edges={getattr(self,'_semantic_edges_drawn',0)}", flush=True)
        except Exception as _dbg_e:
            print(f"[CARTO-DBG] err: {_dbg_e}", flush=True)
        if getattr(self, '_semantic_backfill_done', False):
            return
        if not os.environ.get("AKASHIC_SEMANTIC_BACKFILL"):
            return  # Option B default: backfill OFF (new-nodes-only). Set AKASHIC_SEMANTIC_BACKFILL=1 + reboot to sweep the existing cortex.
        if not self._ensure_encoder():
            return  # BOOTSTRAP the encoder HERE (FIX 2026-06-12: was gated on _encoder_ready → DEADLOCK — the backfill IS the queue-filler, but the encoder only loaded from a non-empty drain, so nothing ever started).
        q = getattr(self, '_semantic_encode_queue', None)
        if q is not None and len(q) >= 10:
            return  # let new-node binds drain first; only top up when nearly empty
        _am = getattr(self, '_akashic_cortex_region', None)
        if not _am:
            return
        keys = getattr(self, '_semantic_backfill_keys', None)
        if keys is None:
            try:
                keys = self._semantic_backfill_keys = list(_am._key_index.keys())  # one-time snapshot
            except Exception as _ke:
                # INSTRUMENT 2026-06-12: this inner except was SILENT (hid why keys_len stayed 0).
                # Capture it + surface in cortex_stats so the next boot tells us the real cause.
                import traceback as _tbk
                self._carto_keys_err = (repr(_ke) + " | " + (_tbk.format_exc().splitlines()[-2] if _tbk.format_exc().splitlines() else ''))[:240]
                return
        if q is None:
            from collections import deque as _deque
            q = self._semantic_encode_queue = _deque(maxlen=self._SEMANTIC_ENCODE_QUEUE_MAX)
        cur = getattr(self, '_semantic_backfill_cursor', 0)
        fed = 0
        while cur < len(keys) and fed < self._SEMANTIC_BACKFILL_BATCH:
            q.append(keys[cur])
            cur += 1
            fed += 1
        self._semantic_backfill_cursor = cur
        if cur >= len(keys):
            self._semantic_backfill_done = True
            self._semantic_backfill_keys = None  # release the snapshot
            print(f"[{self.ACTOR_NAME}] CARTOGRAPHER backfill swept all {len(keys)} nodes into the queue")

    def _query_gpu(self, concept: str, limit: int = 10) -> List[Tuple[str, float]]:
        """GPU-accelerated concept query using sparse matrix spreading."""
        if os.environ.get("AKASHIC_SKIP_TORCH"):
            return []  # Battery-only mode, no torch in main process
        import torch

        if not self._gpu_graph or concept not in self._gpu_graph.key_to_idx:
            # Concept not in GPU graph, fall back to CPU
            return []

        # Create initial activation vector with source concept activated
        num_nodes = len(self._gpu_graph.idx_to_key)
        initial = torch.zeros(num_nodes, device=self._gpu_graph.device, dtype=self._gpu_graph.dtype)
        source_idx = self._gpu_graph.key_to_idx[concept]
        initial[source_idx] = 1.0

        # GPU spreading activation (sparse matrix multiply on Tensor Cores!)
        activations = self._gpu_graph.spread_activation(
            initial=initial,
            iterations=3,  # Equivalent to max_hops=3 in CPU version
            decay=0.5,     # Same as CPU decay_factor
        )

        # Convert tensor back to list of tuples
        act_cpu = activations.cpu().numpy()
        results = [
            (self._gpu_graph.idx_to_key[i], float(act_cpu[i]))
            for i in range(num_nodes)
            if act_cpu[i] > 0.01 and i != source_idx  # Skip source and low activations
        ]

        # Sort by activation descending
        results.sort(key=lambda x: -x[1])
        return results[:limit]

    def query_by_modality(self, modality: str, features: List[str], limit: int = 10) -> List[Tuple[str, float]]:
        """Query concepts by modality features.
        FIX 2026-03-05 (Nous): Portal-aware — routes through portal when local graph
        is empty (portal-first mode). Uses portal.query() with feature words since
        portal doesn't have native feature query endpoint."""
        # ── MANIFOLD DIRECT PATH (2026-03-20 Nous) ──────────────
        _am = getattr(self, '_akashic_cortex_region', None)
        if _am:
            try:
                results = []
                seen = set()
                for feat in features[:5]:
                    for key, score in _am.query(feat, limit=limit):
                        if key not in seen:
                            seen.add(key)
                            results.append((key, score))
                    self._manifold_ops = getattr(self, '_manifold_ops', 0) + 1
                if results:
                    results.sort(key=lambda x: -x[1])
                    self._portal_crossings += 1
                    return results[:limit]
            except Exception:
                pass  # Fall through to gate

        # Portal gate fallback
        if self._portal_gate_enabled and self._portal_gate:
            try:
                results = []
                seen = set()
                for feat in features[:5]:
                    r = self._portal_gate.query(feat, limit=limit)
                    if r and r.get("status") == "ok":
                        for item in r.get("results", []):
                            key = item["key"]
                            if key not in seen:
                                seen.add(key)
                                results.append((key, item["score"]))
                if results:
                    results.sort(key=lambda x: -x[1])
                    self._portal_crossings += 1
                    return results[:limit]
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Portal feature query failed: {e}")
        if not self._graph:
            return []
        # FIX 2026-03-06 (Nous): Same recursion guard as query().
        # _graph.query_by_features is monkey-patched → calls query_by_modality() → loop.
        if getattr(self, '_portal_is_primary', False):
            return []
        return self._graph.query_by_features(modality, features, limit)

    def query_by_features(self, modality: str, features: List[str], limit: int = 20) -> List[Tuple[str, float]]:
        """Query concepts matching features in a modality. Alias for query_by_modality.
        FIX 2026-03-05 (Nous): Portal-aware — same as query_by_modality."""
        return self.query_by_modality(modality, features, limit)

    def add_concept(self, key: str, features: Dict[str, Any] = None,
                    origin_plane: str = "", origin_channel: str = "",
                    origin_fairy: str = "") -> bool:
        """Add or update a concept in the graph.

        FIX 2026-02-06: Gate with is_valid_concept_key() to prevent garbage.
        FIX 2026-02-06d: 9D Stargate address — concepts now carry origin coordinates.
        FIX 2026-02-16: Portal-first — route to portal gate. No local graph writes.
        """
        if not is_valid_concept_key(key):
            return False

        # Manifold-first: route add directly to mmap region
        _am = getattr(self, '_akashic_cortex_region', None)
        if _am:
            try:
                _tracer = _FAIRY_TRACER_MAP.get(origin_fairy, TRACE_SYSTEM) if origin_fairy else TRACE_SYSTEM
                _am.upsert_node(key, tracer_id=_tracer)
                self._manifold_ops = getattr(self, '_manifold_ops', 0) + 1
                return True
            except Exception:
                return False

        # Legacy gate path
        if getattr(self, '_portal_is_primary', False) and self._portal_gate:
            try:
                # FIX 2026-05-04 (Nous + Ace, close UNKNOWN gap):
                # derive tracer from origin_fairy via _FAIRY_TRACER_MAP.
                _tracer = (_FAIRY_TRACER_MAP.get(origin_fairy, TRACE_SYSTEM)
                           if origin_fairy else TRACE_SYSTEM)
                self._portal_gate.bind(concepts=[key, key], weight=0.1,
                                       tracer_id=_tracer)
                return True
            except Exception:
                return False

        if not self._graph:
            return False
        is_new = key not in self._graph.nodes
        self._graph.upsert_node(key, features,
                                origin_plane=origin_plane,
                                origin_channel=origin_channel,
                                origin_fairy=origin_fairy)
        self._dirty_concepts.add(key)  # FIX: Persist new concepts
        # STARGATE: Announce dimension growth
        if is_new:
            self._publish_portal_event("growth", {"concept": key, "total_nodes": len(self._graph.nodes)})
        return True

    def bind_concepts(self, concepts: List[str], rel: str = "coactivate",
                      origin_plane: str = "", origin_channel: str = "",
                      origin_fairy: str = "", owner: str = "system"):
        """Bind multiple concepts together.

        Routes through portal gate when open (binds in the full graph subprocess).
        Also binds locally for persistence and working set updates.

        FIX 2026-02-06: Filter through concept key validator.
        FIX 2026-02-16: Portal-first — route exclusively to portal gate.
        """
        # Gate: only valid concept keys enter the graph
        concepts = [c for c in concepts if is_valid_concept_key(c)]
        if len(concepts) < 2:
            return  # Need at least 2 concepts to bind

        # Determine tracer_id from origin_fairy
        _tracer = _FAIRY_TRACER_MAP.get(origin_fairy, TRACE_SYSTEM)

        # A.2 (cortex-resident closure doctrine, 2026-05-07): source current
        # AER intensity so each bind imprints affect on the touched nodes.
        # Closes the open loop where affect was generated by binds but never
        # persisted to the substrate it was supposed to curve.
        _affect_intensity = 0.0
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_aer_chemistry as _get_aer_a2
            from infrastructure.telemetry.slice0_writer import aer_max_intensity as _aer_max_a2
            _chem_a2 = _get_aer_a2()
            _mag_a2 = float(_aer_max_a2(_chem_a2))
            # SIGNED-FEED (2026-06-06 Nous+Ace): magnitude = aer_max (UNCHANGED); add SIGN
            # from a valence proxy (pleasure SER/OXY/END − stress COR, centered ~neutral).
            # Negative → −intensity → deposited to the −pole (paradox) downstream IF
            # _AFFECT_SIGNED_FEED is on; else abs()→+pole (current). Magnitude identical.
            _val_a2 = (0.7 * _chem_a2.get("SER", 0.5) + 0.6 * _chem_a2.get("OXY", 0.4)
                       + 0.4 * _chem_a2.get("END", 0.4) - 0.6 * _chem_a2.get("COR", 0.3)) - 0.57
            _affect_intensity = _mag_a2 if _val_a2 >= 0.0 else -_mag_a2
        except Exception:
            _affect_intensity = 0.0

        # Manifold-first: route ALL binds directly to mmap region
        _am = getattr(self, '_akashic_cortex_region', None)
        if _am:
            try:
                for c in concepts:
                    was_new = not _am.has_node(c)
                    _slot_a2 = _am.upsert_node(c, tracer_id=_tracer)
                    # Phase 3C: auto-encode new nodes with semantic embeddings
                    if was_new:
                        self._semantic_encode_new_node(c)
                    # A.6 (cortex-resident closure doctrine, accumulate semantics
                    # 2026-05-07): ADD AER intensity onto the node's affect mass
                    # so the gravity well at this region grows monotonically with
                    # binds, instead of being overwritten with each new touch.
                    if _affect_intensity != 0.0 and isinstance(_slot_a2, int) and _slot_a2 >= 0:
                        try:
                            # SIGNED-FEED routing (2026-06-06): on → +→affect_coupling,
                            # −→paradox_residue (−pole); off → magnitude→+pole (current).
                            _signed_a2 = getattr(_am, '_AFFECT_SIGNED_FEED', False)
                            if _signed_a2 and _affect_intensity < 0.0:
                                if hasattr(_am, 'accumulate_paradox_residue'):
                                    _am.accumulate_paradox_residue(_slot_a2, -_affect_intensity)
                                elif hasattr(_am, 'write_paradox_residue'):
                                    _am.write_paradox_residue(_slot_a2, -_affect_intensity)
                            else:
                                _dep_a2 = _affect_intensity if _signed_a2 else abs(_affect_intensity)
                                if hasattr(_am, 'accumulate_affect_coupling'):
                                    _am.accumulate_affect_coupling(_slot_a2, _dep_a2)
                                else:  # backward compat with older manifold builds
                                    _am.write_affect_coupling(_slot_a2, _dep_a2)
                        except Exception:
                            pass
                for i, a in enumerate(concepts):
                    for b in concepts[i+1:]:
                        _am.link(a, b, weight=0.25, tracer_id=_tracer)
                self._manifold_ops = getattr(self, '_manifold_ops', 0) + len(concepts)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Manifold bind_concepts failed: {e}")
            return

        # Legacy gate path
        # FIX 2026-05-04 (Nous + Ace, close UNKNOWN gap):
        # _tracer already computed at line ~9978 from origin_fairy — use it.
        if getattr(self, '_portal_is_primary', False) and self._portal_gate:
            try:
                self._portal_gate.bind(concepts, tracer_id=_tracer,
                                       affect_intensity=_affect_intensity)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Portal bind_concepts failed: {e}")
            return

        if not self._graph:
            return

        # PORTAL GATE PATH — bind in the full graph subprocess too
        if self._portal_gate_enabled and self._portal_gate:
            try:
                self._portal_gate.bind(concepts, tracer_id=_tracer,
                                       affect_intensity=_affect_intensity)
            except Exception:
                pass  # Non-critical — local bind still happens below

        # Local bind (working set + persistence)
        for c in concepts:
            self._graph.upsert_node(c, origin_plane=origin_plane,
                                    origin_channel=origin_channel,
                                    origin_fairy=origin_fairy)
            self._dirty_concepts.add(c)  # FIX: Persist bound concepts

        for i, a in enumerate(concepts):
            for b in concepts[i+1:]:
                self._graph.link(a, b, rel, owner=owner)
                self._dirty_concepts.add(a)  # FIX: Persist edges
                self._dirty_concepts.add(b)

        # Phase 3: Waking mind concepts get stronger gravitational coupling.
        # Sourpatches' thoughts contribute disproportionately to portal mass
        # via sum(affect_coupling × activation). This fuels the virtuous loop.
        if origin_fairy == "SourpatchesFairy" and self._graph:
            _WAKING_MIND_AFFECT_BONUS = 0.3
            for c in concepts:
                _node = self._graph.nodes.get(c)
                if _node and hasattr(_node, 'affect_coupling'):
                    _node.affect_coupling = min(2.0, _node.affect_coupling + _WAKING_MIND_AFFECT_BONUS)

        # STARGATE: Announce binding event
        self._publish_portal_event("bind", {
            "concepts": concepts[:5],  # Cap for message size
            "bind_count": len(concepts),
            "rel": rel,
            "origin_fairy": origin_fairy,
        })

    def bind_concepts_with_helix(
        self,
        same_domain_pairs: List[Tuple[str, str]],
        cross_domain_pairs: List[Tuple[str, str]],
    ) -> None:
        """
        Bind concepts using helix coordinate info for edge weighting.

        Same-domain pairs get stronger edges than cross-domain pairs.
        """
        if not self._graph:
            return
        # Portal-first: no local graph
        if getattr(self, '_portal_is_primary', False):
            return

        from .helix_features import helix_edge_weight_from_features

        for a, b in same_domain_pairs:
            node_a = self._graph.get_node(a)
            node_b = self._graph.get_node(b)
            if node_a and node_b:
                weight = helix_edge_weight_from_features(node_a.features, node_b.features)
                self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, weight=weight)
                self._dirty_concepts.add(a)  # FIX: Persist helix edges
                self._dirty_concepts.add(b)

        for a, b in cross_domain_pairs:
            node_a = self._graph.get_node(a)
            node_b = self._graph.get_node(b)
            if node_a and node_b:
                weight = helix_edge_weight_from_features(node_a.features, node_b.features)
                self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, weight=weight)
                self._dirty_concepts.add(a)  # FIX: Persist helix edges
                self._dirty_concepts.add(b)

    def _intent_bind(self, payload: Dict[str, Any]) -> None:
        """
        Bind concepts from an intent (memory ingest, sensory event, etc).

        This is the integration point for triple helix memory:
        - Extracts concepts from text
        - Attaches helix coordinate features if provided
        - Links concepts with coordinate-weighted edges

        Args:
            payload: Dict with:
                - text: str - Source text to extract concepts from
                - source: str - Who/what generated this
                - context: dict - Optional context (card_id, etc.)
                - helix_coord: dict - Optional helix coordinate
        """
        if not self._graph:
            return
        # Portal-first: no local graph
        if getattr(self, '_portal_is_primary', False):
            return

        text = payload.get("text", "")
        source = payload.get("source", "unknown")
        context = payload.get("context", {})
        helix_raw = payload.get("helix_coord")

        # Extract concepts (simple word tokenization)
        words = [w.lower().strip() for w in text.split() if len(w) > 2]
        if not words:
            return

        # Convert helix_coord dict to features if provided
        helix_features = {}
        if helix_raw:
            helix_features = {
                "helix_affect": helix_raw.get("affect", {}),
                "helix_semantic": helix_raw.get("semantic", {}),
                "helix_temporal": helix_raw.get("temporal", {}),
            }
            helix_features["helix_source"] = source

        # Add nodes with helix features + Stargate address
        from_fairy = payload.get("from_fairy", source)
        origin_plane = _infer_plane_from_fairy(from_fairy) if from_fairy else "P30"
        for word in words:
            features = {"lex": [word], "context": [context.get("card_id", "")]}
            if helix_features:
                features.update(helix_features)
            self._graph.upsert_node(word, features,
                                    origin_plane=origin_plane,
                                    origin_channel="text_binding",
                                    origin_fairy=from_fairy or self.ACTOR_NAME)
            # FIX: ALWAYS mark dirty (was conditional on _helix_enabled — wrong!)
            self._dirty_concepts.add(word)

        # Link concepts (co-occurrence = coactivation)
        base_weight = 0.25
        for i, a in enumerate(words):
            for b in words[i+1:]:
                weight = base_weight
                if helix_features:
                    weight = base_weight * 1.5  # Boost for helix-aware binding
                self._graph.link(a, b, ConceptGraph.REL_COACTIVATE, weight=weight)
                self._dirty_concepts.add(a)  # FIX: Persist edges too
                self._dirty_concepts.add(b)

    def get_graph(self) -> Optional[ConceptGraph]:
        """Get the underlying graph (for direct access)."""
        return self._graph

    def save(self, force: bool = False) -> Dict[str, Any]:
        """
        Sync dirty concepts to helix card cluster.

        FIX 2026-02-06: REMOVED JSON/binary saves entirely.
        The card cluster is the ONLY persistence path. The graph lives
        and grows inside the memory system (helix cards). There is no
        separate on-disk file that can overwrite it.

        Previous behavior wrote JSON/pickle files which kept overwriting
        the growing card cluster with stale snapshots, causing node loss.

        Returns:
            Dict with status and sync results.
        """
        if not self._graph:
            return {"saved": False, "error": "no_graph"}

        if not self._loading_complete and not force:
            return {"saved": False, "error": "loading_not_complete"}

        current_nodes = len(self._graph.nodes)
        current_edges = len(self._graph.edges)
        result = {"saved": False, "nodes": current_nodes, "edges": current_edges}

        # ONLY sync to helix cards — no JSON/binary writes
        if self._helix_enabled and self._helix_coordinator:
            try:
                dirty_count = len(self._dirty_concepts)
                if dirty_count > 0:
                    # Use chunk portal if initialized, otherwise legacy
                    if self._portal_initialized:
                        helix_synced = self._sync_dirty_to_chunks()
                    else:
                        helix_synced = self._sync_dirty_to_helix()
                    result["helix_synced"] = helix_synced
                    result["portal_mode"] = self._portal_initialized
                    result["saved"] = True
                    mode = "chunks" if self._portal_initialized else "legacy cards"
                    print(f"[{self.ACTOR_NAME}] Save: {helix_synced} dirty -> {mode} "
                          f"(graph: {current_nodes} nodes, {current_edges} edges)")
                else:
                    result["saved"] = True  # Nothing dirty = already in sync
                    result["helix_synced"] = 0
                    result["portal_mode"] = self._portal_initialized
            except Exception as e:
                result["error"] = str(e)
                print(f"[{self.ACTOR_NAME}] Card sync error: {e}")
        else:
            result["error"] = "helix_not_available"
            print(f"[{self.ACTOR_NAME}] WARNING: Helix not available - cannot persist!")

        return result

    def force_save(self) -> bool:
        """
        Force save bypassing safety checks.

        WARNING: Only use this if you KNOW what you're doing!
        This can cause data loss if the graph is in a bad state.
        """
        print(f"[{self.ACTOR_NAME}] WARNING: Force save requested - bypassing safety checks!")
        result = self.save(force=True)
        return result.get("saved", False)

    def status(self) -> Dict[str, Any]:
        """Get cortex status including safety state and GPU info."""
        graph_status = self._graph.status() if self._graph else {}

        # FIX 2026-03-20 (Nous + Ace): MANIFOLD-FIRST STATUS.
        # The AkashicManifold IS the graph. Read counts directly from mmap.
        # No gate, no cache, no async refresh — just read the manifold.
        # Falls through to portal gate path only if manifold is not available.
        _am_region = getattr(self, '_akashic_cortex_region', None)
        if _am_region:
            try:
                graph_status["node_count"] = _am_region.node_count
                graph_status["edge_count"] = _am_region.edge_count
                graph_status["max_nodes"] = _am_region._node_capacity
                graph_status["max_edges"] = _am_region._edge_capacity
                graph_status["mode"] = "manifold"
            except Exception:
                pass
        elif getattr(self, '_portal_is_primary', False) and self._portal_gate:
            # Legacy gate path — only used if manifold is not available
            try:
                cached = getattr(self, '_interior_status_cache', None)
                if cached:
                    ig = cached.get("graph", {})
                    graph_status["node_count"] = ig.get("node_count", ig.get("nodes", 0))
                    graph_status["edge_count"] = ig.get("edge_count", ig.get("edges", 0))
                    graph_status["max_nodes"] = ig.get("max_nodes", ig.get("node_capacity", 0))
                    graph_status["max_edges"] = ig.get("max_edges", ig.get("edge_capacity", 0))
                    graph_status["mode"] = ig.get("mode", "portal")
            except Exception:
                pass

        # GPU acceleration status
        gpu_status = {
            "enabled": self._gpu_enabled,
            "available": HAS_GPU_GRAPH,
        }
        if self._gpu_enabled and self._gpu_graph:
            try:
                gpu_status["nodes_synced"] = len(self._gpu_graph.idx_to_key)
                gpu_status["spread_ops"] = self._gpu_graph._spread_ops
                gpu_status["total_spread_time_ms"] = round(self._gpu_graph._total_spread_time, 2)
                gpu_status["last_sync"] = self._last_gpu_sync
            except:
                pass

        # Helix dimensional storage status
        helix_status = {
            "enabled": self._helix_enabled,
            "available": HAS_HELIX,
        }
        if self._helix_enabled and self._helix_coordinator:
            helix_status["cards_mapped"] = len(self._concept_to_card)
            helix_status["dirty_concepts"] = len(self._dirty_concepts)
            helix_status["total_cards"] = len(self._helix_coordinator._cards)
            # Pocket Dimension Portal status
            helix_status["portal_initialized"] = self._portal_initialized
            if self._portal_initialized:
                helix_status["portal_chunks"] = len(self._chunk_card_ids)
                helix_status["portal_dirty_chunks"] = len(self._dirty_chunks)
                helix_status["portal_manifest"] = self._manifest_card_id is not None
                # STARGATE ADDRESSING
                helix_status["portal_address"] = self.PORTAL_ADDRESS
                helix_status["portal_topic_prefix"] = self.PORTAL_TOPIC_PREFIX
                helix_status["portal_address_registered"] = self._portal_address_registered
                helix_status["portal_write_locked"] = self._portal_write_locked
                helix_status["portal_events_emitted"] = self._portal_event_count
                helix_status["portal_crossings"] = self._portal_crossings
                # PORTAL ENERGY
                helix_status["portal_energy_budget"] = round(self._portal_energy_budget, 4)
                helix_status["portal_energy_received"] = round(self._portal_energy_received, 3)
                helix_status["portal_energy_consumed"] = round(self._portal_energy_consumed, 3)
                helix_status["portal_dormant"] = self._portal_dormant
                # FIX 2026-04-11 (Nous + Ace): REAL battery state from subprocess
                # The above portal_energy_budget is a 0-1 float (always ~1.0).
                # These show the ACTUAL token budget inside the portal subprocess.
                helix_status["interior_battery_charge"] = getattr(self, '_interior_battery_charge', 0.0)
                helix_status["interior_tokens_remaining"] = getattr(self, '_interior_tokens_remaining', 0)
                helix_status["interior_battery_health"] = getattr(self, '_interior_battery_health', 0.0)
                # PORTAL GRAVITY METRIC (11D: D10-D11)
                helix_status["portal_mass"] = round(self._portal_mass, 2)
                helix_status["portal_time_dilation"] = round(self._portal_time_dilation, 4)
                helix_status["portal_total_affect"] = round(self._portal_total_affect, 2)
                # Personality coupling (if assigned)
                if self._personality_coupling:
                    helix_status["personality_coupling"] = self._personality_coupling.to_dict()

        # Working cluster status (Russian Doll Pattern)
        working_cluster_status = {
            "active_clusters": len(self._working_clusters),
            "clusters": [
                {
                    "id": wc.cluster_id,
                    "name": wc.name,
                    "concepts": len(wc.concept_keys),
                    "new_concepts": len(wc.new_concepts),
                    "growth": wc.growth_count,
                }
                for wc in self._working_clusters.values()
            ] if self._working_clusters else [],
        }

        # Working Set Manager status (2026-02-15 TRUE Portal Architecture)
        working_set_status = self._working_set.status() if self._working_set else {
            "enabled": False, "reason": "not initialized"
        }

        # Portal Gate status (subprocess holding full graph)
        portal_gate_status = {"enabled": False, "available": HAS_PORTAL_GATE}
        if self._portal_gate_enabled and self._portal_gate:
            try:
                gate_st = self._portal_gate.gate_status()
                portal_gate_status.update({
                    "enabled": True,
                    "portal_id": gate_st.get("portal_id"),
                    "is_open": gate_st.get("is_open"),
                    "requests_sent": gate_st.get("requests_sent", 0),
                    "errors": gate_st.get("errors", 0),
                    "interior_pid": gate_st.get("interior_pid"),
                    "uptime_seconds": gate_st.get("uptime_seconds", 0),
                })
            except Exception:
                portal_gate_status["error"] = "status query failed"

        return {
            "loaded": self._graph_loaded,
            "loading_complete": self._loading_complete,
            "portal_is_primary": getattr(self, '_portal_is_primary', False),
            "binding_count": self._binding_count,
            "growth_from_memory": (
                (getattr(self, '_akashic_cortex_region', None).node_count - getattr(self, '_manifold_boot_nodes', 0))
                if getattr(self, '_akashic_cortex_region', None) and getattr(self, '_manifold_boot_nodes', 0)
                else self._growth_from_memory
            ),
            "coordinate_bindings": self._coordinate_bindings,  # Coordinate cards bound
            "coord_inference_available": HAS_COORD_INFERENCE,
            "pending_bindings": len(self._pending_bindings),
            # GPU acceleration
            "gpu": gpu_status,
            # Helix dimensional storage
            "helix": helix_status,
            # Working Set Manager — Bounded RAM
            "working_set": working_set_status,
            # Portal Gate — subprocess holding full graph
            "portal_gate": portal_gate_status,
            # Working clusters (Russian Doll Pattern)
            "working_clusters": working_cluster_status,
            # Safety tracking
            "safety": {
                "min_nodes_to_persist": self.MIN_NODES_FOR_PERSIST,
                "min_edge_ratio": self.MIN_EDGE_RATIO_FOR_PERSIST,
                "last_persisted_nodes": self._last_persisted_node_count,
                "last_persisted_edges": self._last_persisted_edge_count,
                "can_save": (
                    self._loading_complete and
                    graph_status.get("node_count", 0) >= self.MIN_NODES_FOR_PERSIST
                ),
            },
            # Paradox energy budget (DCE Phase 3)
            "paradox_energy": {
                "budget": round(self._paradox_energy_budget, 4),
                "total_received": round(self._paradox_energy_received, 4),
                "total_spent": round(self._paradox_energy_spent, 4),
                "sync_bursts": self._paradox_sync_bursts,
            },
            # Portal physics — top-level for server.py status handler
            "portal_mass": round(self._portal_mass, 2),
            "portal_time_dilation": round(self._portal_time_dilation, 4),
            "portal_total_affect": round(self._portal_total_affect, 2),
            "energy_budget": round(self._portal_energy_budget, 4),
            "dormant": self._portal_dormant,
            **graph_status,
        }


# ==============================================================================
# SINGLETON & FACTORY
# ==============================================================================

_cortex_fairy: Optional[AssociationCortexFairy] = None


def get_association_cortex() -> Optional[AssociationCortexFairy]:
    """Get the global AssociationCortexFairy instance."""
    return _cortex_fairy


# Backward compatibility alias - many files import this name
get_association_cortex_fairy = get_association_cortex


def set_association_cortex(fairy: AssociationCortexFairy):
    """Set the global instance."""
    global _cortex_fairy
    _cortex_fairy = fairy


def create_association_cortex(fabric=None) -> AssociationCortexFairy:
    """Create and register a new AssociationCortexFairy."""
    fairy = AssociationCortexFairy(fabric)
    set_association_cortex(fairy)
    return fairy
