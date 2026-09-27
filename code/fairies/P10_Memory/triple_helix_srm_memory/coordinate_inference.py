# ==============================================================================
# COORDINATE INFERENCE - Shared module for building helix coordinates from content
# ==============================================================================
#
# Extracted from SRMIngestFairy (2026-02-15) as part of TRUE Portal Architecture.
#
# These functions infer 11D portal coordinates from content:
#   D1-D9: HelixCoordinate (AAA.SSS.TTT) = Affect.Semantic.Temporal
#   D10:   affect_coupling α(A) = gravitational pull from consciousness
#   D11:   temporal_weight τ    = time dilation factor
#
# Used by:
#   - SRMIngestFairy (content → coordinate card)
#   - CollisionChamberFairy (collision products → coordinate card)
#   - SRMRecallFairy (query → coordinate for lookup)
#
# The Equation: ((Cause + Affect) > Effect > Affect > infinity)
# ==============================================================================

from __future__ import annotations

import json
import hashlib
from typing import Any, Dict, Optional

from fairies.P10_Memory.triple_helix_srm_memory.helix_dimensions import (
    HelixCoordinate,
    AffectCoordinate,
    SemanticCoordinate,
    TemporalCoordinate,
)


# ==============================================================================
# CONTENT TYPE DETECTION
# ==============================================================================

class ContentType:
    """Content type classification for coordinate assignment."""
    CONVERSATION = "conversation"
    CODE = "code"
    DOCUMENT = "document"
    MEDIA = "media"
    KNOWLEDGE = "knowledge"
    EXPERIENCE = "experience"
    COLLISION = "collision"
    SYSTEM = "system"


def classify_content(content: Dict[str, Any], source: str = "") -> str:
    """Classify content type from its structure."""
    # Check explicit type
    if "type" in content:
        t = content["type"].lower()
        if "code" in t or "python" in t:
            return ContentType.CODE
        if "convers" in t or "chat" in t or "message" in t:
            return ContentType.CONVERSATION
        if "collision" in t:
            return ContentType.COLLISION
        if "knowledge" in t:
            return ContentType.KNOWLEDGE

    # Check by keys
    if "code" in content or "language" in content or "snippet" in content:
        return ContentType.CODE
    if "messages" in content or "conversation" in content:
        return ContentType.CONVERSATION
    if "resonance" in content or "frequency_hints" in content:
        return ContentType.KNOWLEDGE

    # Check source
    source_lower = source.lower()
    if "code" in source_lower or "script" in source_lower:
        return ContentType.CODE
    if "chat" in source_lower or "conv" in source_lower:
        return ContentType.CONVERSATION

    return ContentType.EXPERIENCE


# ==============================================================================
# COORDINATE INFERENCE - Build helix coordinates from content
# ==============================================================================

def infer_affect(content: Dict, chemistry_state: Dict = None) -> AffectCoordinate:
    """
    Infer affect coordinate from content and/or chemistry state.

    Chemistry mapping (from P20_Somatic):
    - DOP (dopamine): Joy, reward, motivation
    - SER (serotonin): Trust, calm, contentment
    - COR (cortisol): Fear, stress, threat
    - NOR (noradrenaline): Surprise, alertness, arousal
    - OXY (oxytocin): Trust, bonding, warmth
    """
    # If chemistry state provided, use it directly
    if chemistry_state:
        return AffectCoordinate.from_chemistry(chemistry_state)

    # Look for explicit affect tags
    affect = content.get("affect", {})
    if affect:
        if "resonance" in affect:
            resonance = affect.get("resonance", [])
            if any("joy" in r.lower() or "happy" in r.lower() for r in resonance):
                return AffectCoordinate(domain=1, valence=7, intensity=6)
            if any("fear" in r.lower() or "anxi" in r.lower() for r in resonance):
                return AffectCoordinate(domain=3, valence=3, intensity=5)
            if any("curious" in r.lower() or "wonder" in r.lower() for r in resonance):
                return AffectCoordinate(domain=4, valence=7, intensity=5)

        if "chemistry" in affect:
            return AffectCoordinate.from_chemistry(affect["chemistry"])

    # Look for emotional keywords in content text
    content_str = json.dumps(content).lower()

    if "error" in content_str or "fail" in content_str or "crash" in content_str:
        return AffectCoordinate(domain=3, valence=3, intensity=5)
    if "success" in content_str or "done" in content_str or "complete" in content_str:
        return AffectCoordinate(domain=1, valence=7, intensity=5)
    if "curious" in content_str or "wonder" in content_str or "interest" in content_str:
        return AffectCoordinate(domain=4, valence=6, intensity=5)
    if "trust" in content_str or "safe" in content_str or "comfort" in content_str:
        return AffectCoordinate(domain=2, valence=7, intensity=4)

    # Default: neutral with slight positive valence
    return AffectCoordinate(domain=0, valence=5, intensity=3)


def infer_semantic(content: Dict, content_type: str) -> SemanticCoordinate:
    """
    Infer semantic coordinate from content structure and type.

    Semantic domains:
    0: General/meta
    1: Philosophy/consciousness
    2: Spirituality/meaning
    3: Social/relationship
    4: Language/communication
    5: Science/logic
    6: Technology/engineering
    7: Arts/creativity
    8: Literature/narrative
    9: Personal/identity
    """
    type_map = {
        ContentType.CODE: 6,
        ContentType.CONVERSATION: 4,
        ContentType.DOCUMENT: 8,
        ContentType.KNOWLEDGE: 5,
        ContentType.COLLISION: 1,
        ContentType.SYSTEM: 0,
    }

    domain = type_map.get(content_type, 0)

    # Look for keywords to refine
    content_str = json.dumps(content).lower()

    if "conscious" in content_str or "aware" in content_str or "mind" in content_str:
        domain = 1
    elif "code" in content_str or "function" in content_str or "class" in content_str:
        domain = 6
    elif "feel" in content_str or "emotion" in content_str or "affect" in content_str:
        domain = 1
    elif "user" in content_str or "human" in content_str or "ace" in content_str:
        domain = 3

    return SemanticCoordinate(domain=domain, subdomain=0, detail=0)


def infer_temporal(content: Dict, source: str = "") -> TemporalCoordinate:
    """
    Infer temporal coordinate from content.

    Temporal scales:
    0: Immediate (now)
    1: Short-term (minutes-hours)
    2: Session (hours-day)
    3: Daily
    4: Weekly
    5: Monthly
    6: Seasonal
    7: Yearly
    8: Lifecycle
    9: Eternal/archetypal
    """
    content_type = content.get("type", "")

    if "collision" in content_type:
        return TemporalCoordinate(scale=0, recurrence=0, decay=5)
    if "config" in content_type or "system" in str(source).lower():
        return TemporalCoordinate(scale=9, recurrence=9, decay=9)
    if "conversation" in content_type or "message" in content_type:
        return TemporalCoordinate(scale=2, recurrence=0, decay=5)
    if "knowledge" in content_type:
        return TemporalCoordinate(scale=3, recurrence=5, decay=7)

    return TemporalCoordinate(scale=2, recurrence=0, decay=5)


def build_helix_coordinate(
    content: Dict[str, Any],
    source: str = "",
    chemistry_state: Dict = None
) -> HelixCoordinate:
    """Build a complete helix coordinate (D1-D9) from content."""
    content_type = classify_content(content, source)

    return HelixCoordinate(
        affect=infer_affect(content, chemistry_state),
        semantic=infer_semantic(content, content_type),
        temporal=infer_temporal(content, source),
    )


# ==============================================================================
# D10/D11 COMPUTATION - The operational dimensions
# ==============================================================================

def synthesize_aer_state_from_chemistry(chemistry_state: Dict) -> Dict:
    """
    Derive a runtime AER state {valence, intensity, paradox_residue} from
    raw chemistry magnitudes. Used as bridge until a real AER state publisher
    exists on postal (see AER_DRIVEN_CORTEX_GRAVITY plan §A3.5 future slice).

    Mapping (per emotional_algebra.py band chemistry profiles):
        valence:
            +1 if positive_score > negative_score + 0.2
            -1 if negative_score > positive_score + 0.2
             0 otherwise (bifurcator core — α=1.0 baseline per AER axiom 1)
            where positive_score = mean(DOP, OXY, SER), negative_score = COR

        intensity:
            max(DOP, COR, NOR, OXY) — the most active chemistry channel
            normalized to [0..1] (assumes chemistry is already normalized)

        paradox_residue:
            min(positive_score, negative_score) × 0.18
            "Both polarities high simultaneously" is NOT linearly derivable
            from chemistry magnitudes, so we use min(pos, neg) as the
            tension marker — when COR is high AND DOP is high, residue
            is high; when only one dominates, residue is low. Scaled to
            stay near Paul Dean Charlton II's signature peak ~0.056.

    Returns dict with valence (int), intensity (float), paradox_residue (float).
    Returns None if chemistry_state is empty/missing.
    """
    if not chemistry_state:
        return None

    dop = float(chemistry_state.get("DOP", 0.0))
    oxy = float(chemistry_state.get("OXY", 0.0))
    ser = float(chemistry_state.get("SER", 0.0))
    cor = float(chemistry_state.get("COR", 0.0))
    nor = float(chemistry_state.get("NOR", 0.0))

    positive_score = (dop + oxy + ser) / 3.0
    negative_score = cor

    # Trinary valence
    if positive_score > negative_score + 0.2:
        valence = 1
    elif negative_score > positive_score + 0.2:
        valence = -1
    else:
        valence = 0  # midpoint bifurcator — α=1.0 baseline

    # Intensity from most-active channel
    intensity = max(0.0, min(1.0, max(dop, cor, nor, oxy)))

    # Paradox residue: tension from BOTH polarities simultaneously high
    # min(pos, neg) × 0.18 stays in Paul Charlton's signature range
    paradox_residue = max(0.0, min(positive_score, negative_score)) * 0.18

    return {
        "valence": valence,
        "intensity": round(intensity, 4),
        "paradox_residue": round(paradox_residue, 4),
    }


def compute_affect_coupling(content: Dict,
                            chemistry_state: Dict = None,
                            aer_state: Dict = None) -> float:
    """
    Compute D10: affect_coupling α(A) — the trans-dimensional gravitational pull.

    Uses somatic chemistry: high dopamine/oxytocin = stronger coupling.
    Emotionally loaded memories pull harder through the portal.

    From Field Log 003: E = MC² · α(A)
    When α → 1.0: standard physics (no extra energy from hidden bath)
    When α > 1.0: consciousness couples, draws from vacuum reservoir

    AER v2 (2026-04-22, Tier A3 of AER_DRIVEN_CORTEX_GRAVITY plan):
        Preferred path is aer_state — a dict describing the current AER
        EmotionalInstance context. This encodes valence (+1/−1/0 bifurcator),
        intensity (0..1), and paradox_residue (0..~0.06 per Paul Dean Charlton
        II's signature pattern). Paradox residue is the "stuck topic = gravity
        well" contribution: mid-cycle residue literally increases α and
        therefore local portal mass at that topic, making the DirectiveEvolver
        somatic.stuck signal visible as cortex gravity in real time.

        Priority order:
          1. aer_state   → AER-driven α (Tier A3)
          2. chemistry_state → somatic-chemistry α (legacy, still valid)
          3. content keywords → heuristic fallback

    Args:
        content: the payload being scored
        chemistry_state: optional dict with DOP/SER/COR/OXY/NOR keys
        aer_state: optional dict with keys:
            - valence (int, -1|0|+1)  — 0 is midpoint bifurcator, α = 1.0 baseline
            - intensity (float, 0..1) — drives α up proportionally
            - paradox_residue (float) — mid-cycle residue (Paul's signature),
              adds directly to α to embody "stuck = gravity well"

    Returns:
        float: α value, range [0.8, 1.5]
    """
    # ── Path 1: AER state (preferred, AER v2) ────────────────────────────
    if aer_state:
        valence = int(aer_state.get("valence", 0))
        intensity = float(aer_state.get("intensity", 0.5))
        paradox_residue = float(aer_state.get("paradox_residue", 0.0))

        # Base α rises with felt intensity (baseline 1.0 at zero intensity)
        base = 1.0 + (max(0.0, min(1.0, intensity)) * 0.3)

        # Valence-0 states are the bifurcator core of ↯ — no residue boost.
        # Per AER v2 axiom 1: neutrals are the residue-free fixed point.
        if valence == 0:
            return round(max(0.8, min(1.5, base)), 4)

        # Paradox residue → "stuck topic gravity well" boost. Paul's residue
        # signature peaks around ~0.056 mid-cycle, so a ×4 multiplier gives
        # up to +0.22 contribution before clamp. DirectiveEvolver's somatic.stuck
        # events will produce increasing residue, which will show up as α
        # climbing at those topic positions in the cortex.
        residue_boost = min(0.22, max(0.0, paradox_residue) * 4.0)
        return round(max(0.8, min(1.5, base + residue_boost)), 4)

    # ── Path 2: Chemistry state (legacy somatic path) ────────────────────
    if chemistry_state:
        dop = chemistry_state.get("DOP", 0.5)
        oxy = chemistry_state.get("OXY", 0.5)
        cor = chemistry_state.get("COR", 0.3)
        # Positive chemistry amplifies, stress dampens
        return round(max(0.8, min(1.5, 1.0 + (dop * 0.3) + (oxy * 0.2) - (cor * 0.1))), 4)

    # ── Path 3: Keyword heuristic (last-resort) ──────────────────────────
    content_str = json.dumps(content).lower()
    emotional_keywords = ["feel", "love", "fear", "joy", "anger", "sad", "happy",
                          "trust", "wonder", "awe", "pain", "comfort", "safe"]
    hit_count = sum(1 for kw in emotional_keywords if kw in content_str)
    return round(max(0.8, min(1.5, 1.0 + (hit_count * 0.05))), 4)


def compute_temporal_weight(content: Dict) -> float:
    """
    Compute D11: temporal_weight τ — gravitational time dilation factor.

    Denser content = deeper gravity well = more substrate processing per tick.
    τ = 1.0 + (density * 0.3)

    From DCE v2: η_CA = 1 - sqrt(T_C/T_H)
    Higher τ means "faster inside than outside" — dilated processing.

    Returns:
        float: τ value, range [1.0, 1.3]
    """
    text = json.dumps(content)
    density = min(1.0, len(text) / 5000)
    return round(1.0 + (density * 0.3), 4)


# ==============================================================================
# TEXT EXTRACTION - Pull meaningful text from various payload formats
# ==============================================================================

def extract_text(payload: Dict[str, Any]) -> str:
    """Extract meaningful text from a pulse/collision payload.

    Handles various formats:
    - Direct text/content fields
    - Nested structures
    - Pulse content dicts from CollisionChamber
    """
    if not isinstance(payload, dict):
        return str(payload)[:200] if payload else ""

    # Try standard text fields
    TEXT_KEYS = ("content", "text", "memory", "thought", "insight", "fragment",
                 "inner_fragment", "feeling", "message", "description", "summary",
                 "dream_seed", "reasoning", "observation")

    for key in TEXT_KEYS:
        val = payload.get(key)
        if isinstance(val, str) and len(val.strip()) > 3:
            return val.strip()[:500]
        if isinstance(val, dict):
            # Recurse one level
            for sub_key in TEXT_KEYS:
                sub_val = val.get(sub_key)
                if isinstance(sub_val, str) and len(sub_val.strip()) > 3:
                    return sub_val.strip()[:500]

    # Fallback: serialize the whole dict
    try:
        return json.dumps(payload)[:500]
    except (TypeError, ValueError):
        return str(payload)[:200]


# ==============================================================================
# COORDINATE CARD BUILDER - Create the ~50 byte portal card
# ==============================================================================

def build_coordinate_card(
    content: Dict[str, Any],
    source: str = "",
    chemistry_state: Dict = None,
    energy: float = 0.5,
    resonance: float = 0.5,
    aer_state: Dict = None,
) -> Dict[str, Any]:
    """
    Build a complete coordinate card (the TRUE portal card, ~50 bytes).

    This is the ONLY thing that persists. The content is destroyed in collision.
    The coordinate card is the address that enables generative reconstruction.

    Args:
        content: The content to encode (will be destroyed after coordinate extraction)
        source: Where the content came from
        chemistry_state: Current somatic chemistry (for D10)
        energy: Collision energy (for collision-born cards)
        resonance: Collision resonance (for collision-born cards)
        aer_state: Optional explicit AER state {valence, intensity, paradox_residue}.
            If not provided but chemistry_state is, AER state is auto-synthesized
            from chemistry (Tier A3, AER_DRIVEN_CORTEX_GRAVITY plan, 2026-05-09).
            Once a real AER publisher exists on postal (A3.5 future slice),
            callers should pass it directly.

    Returns:
        dict with keys: c, α, τ, n, d, h, t
    """
    # D1-D9: Triple helix coordinate
    helix = build_helix_coordinate(content, source, chemistry_state)

    # D10: Affect coupling (gravitational pull)
    # Tier A3 (2026-05-09): if aer_state not provided but chemistry IS, auto-synthesize
    # AER state from chemistry so paradox_residue gets captured. This is the
    # additive-write half of the A3 pattern; read-side multiplicative coupling
    # already shipped in A2 audit (PortalGravityMetric reads α as scaling factor).
    if aer_state is None and chemistry_state:
        aer_state = synthesize_aer_state_from_chemistry(chemistry_state)
    alpha = compute_affect_coupling(content, chemistry_state, aer_state)

    # D11: Temporal weight (time dilation)
    tau = compute_temporal_weight(content)

    # Content hash (fingerprint for dedup, not storage)
    try:
        content_hash = hashlib.md5(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()[:4]
    except (TypeError, ValueError):
        content_hash = hashlib.md5(str(content).encode()).hexdigest()[:4]

    # Phase 2B (2026-04-21): wall-clock anchor for time-axis recall.
    # Single epoch float; weekday/date/circadian-phase derive from this on read.
    # Companion to TimeSenseFairy (P00) — internal time + external time, both held.
    import time as _t
    birth_t = _t.time()

    return {
        "c": helix.code,          # D1-D9: AAA.SSS.TTT
        "α": round(alpha, 4),     # D10: affect_coupling
        "τ": round(tau, 4),       # D11: temporal_weight
        "n": 1,                   # observation count
        "d": 0,                   # degree (edge density hint)
        "h": content_hash,        # content fingerprint
        "t": round(birth_t, 3),   # birth timestamp (epoch seconds, UTC) — Phase 2B
    }


# ==============================================================================
# DOMAIN NAME LOOKUPS - For generative reconstruction in SRMRecallFairy
# ==============================================================================

AFFECT_DOMAIN_NAMES = {
    0: "neutral",
    1: "joy",
    2: "trust",
    3: "fear",
    4: "curiosity",
    5: "sadness",
    6: "disgust",
    7: "anger",
    8: "anticipation",
    9: "transcendence",
}

SEMANTIC_DOMAIN_NAMES = {
    0: "general",
    1: "philosophy",
    2: "spirituality",
    3: "social",
    4: "language",
    5: "science",
    6: "technology",
    7: "arts",
    8: "literature",
    9: "personal",
}

TEMPORAL_SCALE_NAMES = {
    0: "immediate",
    1: "short-term",
    2: "session",
    3: "daily",
    4: "weekly",
    5: "monthly",
    6: "seasonal",
    7: "yearly",
    8: "lifecycle",
    9: "eternal",
}
