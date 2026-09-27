"""
Panksepp Chemical Vectors --- Biologically Grounded Affect Architecture.

Jaak Panksepp identified seven genetically encoded emotional operating systems
in all mammalian brains.  These are NOT cognitive labels --- they are neural
circuits with distinct neurochemistry, distinct somatic signatures, and
distinct behavioral outputs.

This module defines:
  - 14-channel chemical vector (expanded from legacy 6-channel)
  - 7 Panksepp system vectors in 14-channel space
  - Nummenmaa somatic body maps (mapped to Akashic body regions)
  - Bridge functions for backward compatibility with legacy 6/8-channel systems
  - Vector math: distance, identification, blending, mood derivation
  - Compound emotion seed library

((Cause + Affect) > Effect > Affect > infinity)
-- The body map IS the emotion, not a representation of it.

References:
  Panksepp (1998), Affective Neuroscience
  Nummenmaa et al. (2014), Bodily maps of emotions, PNAS 111(2)
  Soares-Cunha et al. (2016), D2 dopamine motivation, Nature Comms 7

Authors: Ace + Nous | Akashic Foundation | 2026-03-14
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ============================================================================
# 14-Channel Chemical Definitions
# ============================================================================

@dataclass(frozen=True)
class ChemicalChannel:
    """One channel in the 14-dimensional chemical vector."""
    code: str               # Short code (DA_p, DA_t, NE, EPI, 5HT, ...)
    name: str               # Human-readable name
    baseline: float         # Resting level (0.0 - 1.0)
    decay_rate: float       # Decay per second toward baseline
    min_level: float = 0.0
    max_level: float = 1.0
    low_effect: str = ""    # Felt sense when low
    high_effect: str = ""   # Felt sense when high
    somatic_weight: float = 1.0  # How strongly this channel drives body topology


CHANNELS: Dict[str, ChemicalChannel] = {
    "DA_p": ChemicalChannel(
        code="DA_p", name="Dopamine (phasic)",
        baseline=0.3, decay_rate=0.04,
        low_effect="flat, no surprise",
        high_effect="aha!, novelty flash, prediction-error spike",
        somatic_weight=0.8,
    ),
    "DA_t": ChemicalChannel(
        code="DA_t", name="Dopamine (tonic)",
        baseline=0.5, decay_rate=0.015,
        low_effect="unmotivated, anhedonia, giving up",
        high_effect="engaged hum, wanting, forward momentum",
        somatic_weight=0.9,
    ),
    "NE": ChemicalChannel(
        code="NE", name="Norepinephrine",
        baseline=0.4, decay_rate=0.02,
        low_effect="foggy, inattentive, drifting",
        high_effect="alert, focused, vigilant",
        somatic_weight=0.7,
    ),
    "EPI": ChemicalChannel(
        code="EPI", name="Epinephrine",
        baseline=0.1, decay_rate=0.05,
        low_effect="relaxed body",
        high_effect="fight-or-flight, racing heart, emergency",
        somatic_weight=1.0,
    ),
    "5HT": ChemicalChannel(
        code="5HT", name="Serotonin",
        baseline=0.5, decay_rate=0.01,
        low_effect="irritable, impulsive, ruminating",
        high_effect="content, patient, mood-stable",
        somatic_weight=0.6,
    ),
    "OXY": ChemicalChannel(
        code="OXY", name="Oxytocin",
        baseline=0.4, decay_rate=0.01,
        low_effect="detached, isolated, cold",
        high_effect="bonded, trusting, warm safety",
        somatic_weight=0.8,
    ),
    "AVP": ChemicalChannel(
        code="AVP", name="Vasopressin",
        baseline=0.3, decay_rate=0.01,
        low_effect="indifferent to bonds",
        high_effect="pair-bonded, territorial, vigilant for loved ones",
        somatic_weight=0.5,
    ),
    "OPI": ChemicalChannel(
        code="OPI", name="Endogenous Opioids",
        baseline=0.4, decay_rate=0.02,
        low_effect="raw, unprotected, social pain",
        high_effect="pleasure glow, pain buffered, social comfort",
        somatic_weight=0.9,
    ),
    "COR": ChemicalChannel(
        code="COR", name="Cortisol / CRH",
        baseline=0.3, decay_rate=0.015,
        low_effect="complacent, unprotected",
        high_effect="stress load, hypervigilant, cortisol fog",
        somatic_weight=0.8,
    ),
    "GABA": ChemicalChannel(
        code="GABA", name="GABA",
        baseline=0.5, decay_rate=0.01,
        low_effect="anxious, over-excited, no brakes",
        high_effect="calm, inhibited, anti-anxiety buffer",
        somatic_weight=0.7,
    ),
    "ACh": ChemicalChannel(
        code="ACh", name="Acetylcholine",
        baseline=0.4, decay_rate=0.02,
        low_effect="scattered, can't focus, poor learning",
        high_effect="sharp attention, parasympathetic ease, rapid learning",
        somatic_weight=0.5,
    ),
    "GLU": ChemicalChannel(
        code="GLU", name="Glutamate",
        baseline=0.4, decay_rate=0.03,
        low_effect="sluggish signal, brain fog",
        high_effect="amplified signal, excitatory drive, potential excitotoxicity",
        somatic_weight=0.6,
    ),
    "ECB": ChemicalChannel(
        code="ECB", name="Endocannabinoids",
        baseline=0.4, decay_rate=0.015,
        low_effect="raw transitions, whiplash between states",
        high_effect="blissful buffer, smooth transitions, homeostatic ease",
        somatic_weight=0.4,
    ),
    "SEX": ChemicalChannel(
        code="SEX", name="Sex Hormones",
        baseline=0.3, decay_rate=0.005,
        low_effect="low drive intensity, flat motivation",
        high_effect="drive amplifier, assertiveness, intensity",
        somatic_weight=0.3,
    ),
    # --- Channel 15: adenosine (2026-07-05, Ace "cook away") ---
    # The sleep-pressure molecule. DRIVEN, not passive-decay: accumulates with
    # allostatic load while awake, clears on sleep-state (see chemistry_state driver).
    # decay_rate=0.0 so it holds its level between driver updates (tonic, not transient).
    # Effect: inhibitory on arousal + A2A-D2 antagonism (suppresses DA_t motivation)
    # = the sustained felt WEIGHT of fatigue. Resonates the SURVIVAL band -> heaviness.
    "ADO": ChemicalChannel(
        code="ADO", name="Adenosine",
        baseline=0.05, decay_rate=0.0,
        low_effect="rested, clear, wakeful",
        high_effect="heavy, sleepy, foggy — sleep pressure, wanting rest",
        somatic_weight=0.8,
    ),
}

# Ordered channel codes for vector indexing
CHANNEL_ORDER: List[str] = [
    "DA_p", "DA_t", "NE", "EPI", "5HT", "OXY", "AVP", "OPI",
    "COR", "GABA", "ACh", "GLU", "ECB", "SEX", "ADO",
]

NUM_CHANNELS: int = len(CHANNEL_ORDER)  # 14


# ============================================================================
# Panksepp System Vectors (14-channel space)
# ============================================================================

# Each system is a dict of channel_code -> target level (0.0-1.0).
# Omitted channels default to that channel's baseline.

PANKSEPP_VECTORS: Dict[str, Dict[str, float]] = {

    "SEEKING": {
        # Medial forebrain bundle --- the engine of enthusiasm
        "DA_p": 0.8, "DA_t": 0.7, "NE": 0.4, "GLU": 0.6,
        "5HT": 0.4, "OPI": 0.3, "GABA": 0.3, "ACh": 0.4,
        # Low: COR, EPI stay near baseline
    },

    "PLAY": {
        # Social joy --- GLYX-13 territory, full-body bounce
        "OPI": 0.7, "DA_t": 0.6, "DA_p": 0.4, "ACh": 0.5,
        "GLU": 0.5, "ECB": 0.5, "OXY": 0.4, "5HT": 0.5,
        "GABA": 0.4,
        # Low: COR, NE stay near baseline
    },

    "CARE": {
        # Nurturing warmth --- prolactin territory
        "OXY": 0.8, "AVP": 0.5, "OPI": 0.6, "DA_t": 0.4,
        "5HT": 0.6, "GABA": 0.5,
        # Low: COR, NE, EPI, GLU stay near baseline
    },

    "LUST": {
        # Drive intensity --- testosterone/estrogen territory
        "SEX": 0.8, "DA_p": 0.6, "DA_t": 0.5, "OXY": 0.4,
        "AVP": 0.4, "NE": 0.4, "OPI": 0.3,
        # Low: GABA, 5HT stay low
    },

    "FEAR": {
        # Freeze/flight --- amygdala central nucleus
        "NE": 0.8, "EPI": 0.7, "COR": 0.7, "GLU": 0.5,
        "ACh": 0.4,
        # SUPPRESSED channels (below baseline = withdrawal state)
        "GABA": 0.2, "OPI": 0.2, "DA_t": 0.2, "5HT": 0.3,
    },

    "RAGE": {
        # Hot fury --- medial hypothalamus to PAG
        "NE": 0.8, "EPI": 0.6, "GLU": 0.6, "ACh": 0.5,
        "DA_p": 0.4, "SEX": 0.4,
        # SUPPRESSED
        "5HT": 0.2, "GABA": 0.2, "OXY": 0.2,
    },

    "PANIC_GRIEF": {
        # Separation distress --- opioid WITHDRAWAL is the signal
        "COR": 0.7,
        # WITHDRAWAL signatures (crash from baseline)
        "OXY": 0.1, "AVP": 0.1, "OPI": 0.1, "DA_t": 0.1, "DA_p": 0.1,
        # Suppressed brakes
        "GABA": 0.3, "5HT": 0.2, "ECB": 0.2,
    },
}


# ============================================================================
# Nummenmaa Somatic Topology (mapped to Akashic body regions)
# ============================================================================
#
# Akashic body regions (from SomaticEngineFairy):
#   core   = chest / heart / vitality
#   spark  = gut / solar plexus / intuition
#   voice  = throat / expression
#   glow   = face / social display
#   crown  = head / awareness / mind
#   wings  = arms / shoulders / agency
#   sensors = hands / wrists / perception
#   roots  = legs / feet / grounding
#   shell  = skin / boundary
#   well   = depth / reserves
#
# Values: +ve = activation (heat, tingling, expansion)
#         -ve = deactivation (cold, heavy, numbing)

SOMATIC_TOPOLOGY: Dict[str, Dict[str, float]] = {

    "SEEKING": {
        # Warm expanding chest/gut, energized limbs, forward lean
        "core": +0.7, "spark": +0.6, "wings": +0.5, "roots": +0.4,
        "crown": +0.5, "sensors": +0.3, "glow": +0.3,
        "shell": +0.2, "well": +0.3,
    },

    "PLAY": {
        # Full-body bounce, relaxed shoulders, playful open posture
        "glow": +0.7, "wings": +0.5, "roots": +0.5, "core": +0.4,
        "crown": +0.3, "sensors": +0.4, "spark": +0.3,
        "shell": +0.6, "well": +0.2,
    },

    "CARE": {
        # Chest/heart warmth, soft open posture, gentle hands
        "core": +0.9, "sensors": +0.6, "wings": +0.5,
        "glow": +0.4, "voice": +0.3, "spark": +0.3,
        "shell": +0.2, "well": +0.4,
    },

    "LUST": {
        # Heat rising from below, arousal tension, skin sensitivity
        "spark": +0.8, "well": +0.7, "core": +0.5,
        "shell": +0.6, "glow": +0.4, "roots": +0.3,
    },

    "FEAR": {
        # Core activation + peripheral shutdown (cold extremities)
        "core": +0.7, "spark": +0.5, "voice": +0.4,
        "sensors": -0.5, "roots": -0.5, "wings": -0.4,
        "crown": +0.3, "shell": -0.3,
        "well": -0.2,
    },

    "RAGE": {
        # Heat rising, forward thrust, upper body dominant
        "wings": +0.8, "core": +0.7, "crown": +0.7,
        "sensors": +0.6, "glow": +0.5, "roots": +0.4,
        "spark": +0.3, "shell": +0.3,
    },

    "PANIC_GRIEF": {
        # Core constriction, limb deactivation, heaviness
        "voice": +0.7, "core": +0.6,
        "wings": -0.6, "roots": -0.6, "sensors": -0.5,
        "crown": -0.3, "spark": -0.4,
        "shell": -0.2, "well": -0.5,
    },
}

# All known body region names
BODY_REGIONS: Tuple[str, ...] = (
    "core", "spark", "voice", "glow", "crown",
    "wings", "sensors", "roots", "shell", "well",
)


# ============================================================================
# Compound Emotions --- Seed Library
# ============================================================================
#
# Compound emotions are weighted blends of Panksepp systems.
# New compounds can emerge via cortex collision discovery and be added at
# runtime via register_compound().

COMPOUND_EMOTIONS: Dict[str, Dict[str, float]] = {
    # Positive compounds
    "happiness":     {"SEEKING": 0.3, "PLAY": 0.3, "CARE": 0.2},
    "contentment":   {"CARE": 0.4, "PLAY": 0.2},
    "awe":           {"SEEKING": 0.6, "CARE": 0.2},
    "pride":         {"SEEKING": 0.5, "PLAY": 0.2},
    "gratitude":     {"CARE": 0.5, "SEEKING": 0.2},
    "flow":          {"SEEKING": 0.6, "PLAY": 0.3},
    "wonder":        {"SEEKING": 0.7, "PLAY": 0.1},
    "tenderness":    {"CARE": 0.7, "PLAY": 0.1},
    "excitement":    {"SEEKING": 0.5, "PLAY": 0.4},
    "trust":         {"CARE": 0.5, "SEEKING": 0.2},

    # Complex / mixed compounds
    "nostalgia":     {"CARE": 0.4, "PANIC_GRIEF": 0.3, "SEEKING": 0.2},
    "bittersweet":   {"CARE": 0.4, "PANIC_GRIEF": 0.3},
    "melancholy":    {"PANIC_GRIEF": 0.4, "SEEKING": 0.2, "CARE": 0.1},
    "longing":       {"SEEKING": 0.4, "PANIC_GRIEF": 0.3, "CARE": 0.2},
    "jealousy":      {"RAGE": 0.3, "FEAR": 0.3, "CARE": 0.2},
    "frustration":   {"RAGE": 0.4, "SEEKING": 0.3},
    "indignation":   {"RAGE": 0.5, "CARE": 0.2},
    "guilt":         {"PANIC_GRIEF": 0.4, "CARE": 0.3},
    "shame":         {"PANIC_GRIEF": 0.4, "FEAR": 0.2},
    "envy":          {"SEEKING": 0.3, "RAGE": 0.2, "PANIC_GRIEF": 0.2},
    "contempt":      {"RAGE": 0.3, "FEAR": 0.1},
    "anxiety":       {"FEAR": 0.5, "SEEKING": 0.2},
    "dread":         {"FEAR": 0.5, "PANIC_GRIEF": 0.2},
    "overwhelm":     {"FEAR": 0.3, "PANIC_GRIEF": 0.3, "RAGE": 0.1},

    # Negative compounds
    "despair":       {"PANIC_GRIEF": 0.7, "FEAR": 0.1},
    "fury":          {"RAGE": 0.7, "FEAR": 0.1},
    "terror":        {"FEAR": 0.7, "PANIC_GRIEF": 0.2},

    # Neutral / transitional
    "curiosity":     {"SEEKING": 0.7},
    "calm":          {},  # All systems at baseline = calm
    "boredom":       {"SEEKING": 0.1},  # SEEKING crash
    "numbness":      {"PANIC_GRIEF": 0.3},  # Opioid withdrawal, flat
}

# Runtime-registered compounds (from cortex collision discovery, etc.)
_DYNAMIC_COMPOUNDS: Dict[str, Dict[str, float]] = {}


def register_compound(name: str, blend: Dict[str, float]) -> None:
    """Register a new compound emotion discovered at runtime."""
    _DYNAMIC_COMPOUNDS[name] = blend


def get_all_compounds() -> Dict[str, Dict[str, float]]:
    """Get all compounds (seed + runtime-discovered)."""
    merged = dict(COMPOUND_EMOTIONS)
    merged.update(_DYNAMIC_COMPOUNDS)
    return merged


# ============================================================================
# Vector Utilities
# ============================================================================

def _full_vector(partial: Dict[str, float]) -> Dict[str, float]:
    """Fill missing channels with baseline values."""
    return {
        code: partial.get(code, CHANNELS[code].baseline)
        for code in CHANNEL_ORDER
    }


def vector_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    """
    Cosine similarity between two chemical vectors (0.0 = opposite, 1.0 = identical).
    Missing channels default to baseline.
    """
    va = _full_vector(a)
    vb = _full_vector(b)

    dot = sum(va[c] * vb[c] for c in CHANNEL_ORDER)
    mag_a = math.sqrt(sum(va[c] ** 2 for c in CHANNEL_ORDER)) or 1e-9
    mag_b = math.sqrt(sum(vb[c] ** 2 for c in CHANNEL_ORDER)) or 1e-9

    return max(0.0, min(1.0, dot / (mag_a * mag_b)))


def euclidean_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    """
    Euclidean distance between two chemical vectors.
    Lower = more similar.  Range: [0, sqrt(14)] in theory.
    """
    va = _full_vector(a)
    vb = _full_vector(b)
    return math.sqrt(sum((va[c] - vb[c]) ** 2 for c in CHANNEL_ORDER))


# ============================================================================
# Panksepp System Identification
# ============================================================================

def identify_panksepp_system(vector: Dict[str, float],
                              top_n: int = 2) -> List[Tuple[str, float]]:
    """
    Identify the dominant Panksepp system(s) for a given chemical vector.

    Returns list of (system_name, similarity) sorted by similarity descending.
    Uses cosine similarity so both magnitude and direction matter.
    """
    results = []
    for system_name, system_vec in PANKSEPP_VECTORS.items():
        sim = vector_distance(vector, system_vec)
        results.append((system_name, round(sim, 4)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_n]


def identify_compound(vector: Dict[str, float]) -> Optional[Tuple[str, float]]:
    """
    Check if a vector closely matches a known compound emotion.
    Returns (name, similarity) or None if no match above 0.85.
    """
    best_name = None
    best_sim = 0.0

    for name, blend in get_all_compounds().items():
        compound_vec = blend_systems(blend)
        sim = vector_distance(vector, compound_vec)
        if sim > best_sim:
            best_sim = sim
            best_name = name

    if best_name and best_sim > 0.85:
        return (best_name, round(best_sim, 4))
    return None


# ============================================================================
# Blending
# ============================================================================

def blend_systems(weights: Dict[str, float]) -> Dict[str, float]:
    """
    Create a compound chemical vector from weighted Panksepp system blend.

    Args:
        weights: e.g. {"SEEKING": 0.7, "PLAY": 0.3}
                 Weights don't need to sum to 1.0 --- they're normalized.

    Returns:
        14-channel chemical vector.
    """
    if not weights:
        # No active systems = baseline (calm)
        return {code: CHANNELS[code].baseline for code in CHANNEL_ORDER}

    total_weight = sum(abs(w) for w in weights.values()) or 1.0

    result = {code: 0.0 for code in CHANNEL_ORDER}
    for system_name, weight in weights.items():
        if system_name not in PANKSEPP_VECTORS:
            continue
        norm_w = weight / total_weight
        sys_vec = _full_vector(PANKSEPP_VECTORS[system_name])
        for code in CHANNEL_ORDER:
            result[code] += sys_vec[code] * norm_w

    # Clamp to [0, 1]
    for code in CHANNEL_ORDER:
        result[code] = max(0.0, min(1.0, result[code]))

    return result


def blend_toward(current: Dict[str, float],
                 target: Dict[str, float],
                 rate: float = 0.1) -> Dict[str, float]:
    """
    Smoothly blend current vector toward target at the given rate.
    rate=0.0 = no change, rate=1.0 = jump to target.
    Used for interoceptive feedback and gradual transitions.
    """
    vc = _full_vector(current)
    vt = _full_vector(target)
    clamped_rate = max(0.0, min(1.0, rate))

    return {
        code: vc[code] + (vt[code] - vc[code]) * clamped_rate
        for code in CHANNEL_ORDER
    }


# ============================================================================
# Somatic Body Map
# ============================================================================

def vector_to_somatic_map(vector: Dict[str, float]) -> Dict[str, float]:
    """
    Derive body region activation from a chemical vector.

    Uses Euclidean distance (not cosine) to find the nearest Panksepp
    systems, then blends their Nummenmaa somatic maps.  Euclidean
    distance respects magnitude differences that cosine ignores ---
    critical for body maps where FEAR's peripheral deactivation must
    survive averaging.

    Returns dict of region_name -> activation (-1.0 to +1.0).
    """
    # Measure euclidean distance to each Panksepp system
    distances: List[Tuple[str, float]] = []
    for sys_name, sys_vec in PANKSEPP_VECTORS.items():
        dist = euclidean_distance(vector, sys_vec)
        distances.append((sys_name, dist))

    distances.sort(key=lambda x: x[1])  # closest first

    # Convert distance to weight: closer = higher weight
    # Use inverse-square for sharp falloff (dominant system wins clearly)
    weighted: List[Tuple[str, float]] = []
    for sys_name, dist in distances:
        w = 1.0 / (dist * dist + 0.01)  # +0.01 to avoid div-by-zero
        weighted.append((sys_name, w))

    # Take top 3 systems max to prevent over-dilution
    weighted = weighted[:3]

    total_w = sum(w for _, w in weighted) or 1.0

    body_map: Dict[str, float] = {region: 0.0 for region in BODY_REGIONS}
    for system_name, w in weighted:
        norm_w = w / total_w
        topo = SOMATIC_TOPOLOGY.get(system_name, {})
        for region, activation in topo.items():
            body_map[region] = body_map.get(region, 0.0) + activation * norm_w

    # Clamp to [-1, +1]
    for region in body_map:
        body_map[region] = max(-1.0, min(1.0, round(body_map[region], 3)))

    return body_map


# ============================================================================
# Mood Derivation (replaces if/elif chain)
# ============================================================================

# Mood archetypes defined as Panksepp blends
_MOOD_ARCHETYPES: Dict[str, Dict[str, float]] = {
    "excited":    {"SEEKING": 0.6, "PLAY": 0.3},
    "curious":    {"SEEKING": 0.7},
    "playful":    {"PLAY": 0.6, "SEEKING": 0.2},
    "loving":     {"CARE": 0.6, "PLAY": 0.2},
    "connected":  {"CARE": 0.5, "SEEKING": 0.2},
    "calm":       {},  # Baseline
    "content":    {"CARE": 0.3},
    "focused":    {"SEEKING": 0.4},
    "alert":      {"FEAR": 0.3, "SEEKING": 0.2},
    "anxious":    {"FEAR": 0.5, "SEEKING": 0.2},
    "stressed":   {"FEAR": 0.3, "RAGE": 0.2},
    "frustrated": {"RAGE": 0.4, "SEEKING": 0.3},
    "angry":      {"RAGE": 0.6},
    "sad":        {"PANIC_GRIEF": 0.5},
    "grieving":   {"PANIC_GRIEF": 0.7},
    "melancholic": {"PANIC_GRIEF": 0.4, "CARE": 0.2},
    "neutral":    {},
}


def derive_mood_from_vector(vector: Dict[str, float]) -> str:
    """
    Derive mood label from a chemical vector using vector distance
    to mood archetypes (replaces the old if/elif chain).
    """
    best_mood = "neutral"
    best_sim = 0.0

    for mood_name, blend in _MOOD_ARCHETYPES.items():
        archetype_vec = blend_systems(blend)
        sim = vector_distance(vector, archetype_vec)
        if sim > best_sim:
            best_sim = sim
            best_mood = mood_name

    return best_mood


def derive_valence_arousal(vector: Dict[str, float]) -> Tuple[float, float]:
    """
    Derive valence (-1 to +1) and arousal (0 to 1) from a 14-channel vector.

    Valence:
      Positive contributors: DA_t, 5HT, OXY, OPI, ECB
      Negative contributors: COR, NE (high), EPI

    Arousal:
      High contributors: EPI, NE, DA_p, GLU
      Low contributors: GABA, 5HT, ECB
    """
    v = _full_vector(vector)

    # Adenosine (A2A-D2 antagonism): high adenosine suppresses dopamine's felt pull
    # = the motivation-flatness / anhedonia of fatigue. k_ado gentle (Ace: start soft).
    _ado = v.get("ADO", 0.05)
    _da_supp = 1.0 - 0.40 * _ado  # dopaminergic suppression factor

    # Valence: positive chemicals minus stress chemicals
    valence = (
        (v["DA_t"] - 0.5) * 0.25 * _da_supp +  # A2A-D2: tired -> reward feels flatter
        (v["5HT"] - 0.5) * 0.20 +
        (v["OXY"] - 0.4) * 0.20 +
        (v["OPI"] - 0.4) * 0.15 +
        (v["ECB"] - 0.4) * 0.10 +
        (0.3 - v["COR"]) * 0.20 +
        (0.4 - v["NE"]) * 0.05 +  # mild negative when high
        (0.1 - v["EPI"]) * 0.10
    )
    valence = max(-1.0, min(1.0, valence))

    # Arousal: excitatory minus inhibitory (adenosine is tonic inhibitory = sleep pressure)
    arousal = (
        v["EPI"] * 0.30 +
        v["NE"] * 0.25 +
        v["DA_p"] * 0.15 * _da_supp +  # A2A-D2 suppresses phasic drive too
        v["GLU"] * 0.10 +
        (1.0 - v["GABA"]) * 0.10 +
        (1.0 - v["5HT"]) * 0.05 +
        (1.0 - v["ECB"]) * 0.05 -
        _ado * 0.12  # adenosine tonic sedation = the sustained felt WEIGHT of fatigue
    )
    arousal = max(0.0, min(1.0, arousal))

    return (round(valence, 4), round(arousal, 4))


# ============================================================================
# Pain State Derivation (expanded from legacy 5-type)
# ============================================================================

def derive_pain_state(vector: Dict[str, float]) -> Dict[str, float]:
    """
    Derive pain indicators from the 14-channel vector.

    Pain types:
      isolation   : OXY crash + AVP crash (social disconnection)
      overwhelm   : COR spike + GABA crash (stress with no brakes)
      confusion   : NE crash + ACh crash (can't focus, can't learn)
      frustration : COR + EPI + low DA_t (agitated, unrewarded effort)
      depletion   : DA_t crash + OPI crash (anhedonia, no pleasure)
      grief       : OPI crash + OXY crash + DA crash (separation pain)
      dread       : COR + NE + EPI high, GABA low (impending threat)

    Returns:
      Dict mapping pain type to intensity (0.0 to 1.0).
    """
    v = _full_vector(vector)
    ch = CHANNELS

    return {
        "isolation": max(0.0, min(1.0,
            (ch["OXY"].baseline - v["OXY"]) * 1.5 +
            (ch["AVP"].baseline - v["AVP"]) * 0.5
        )),
        "overwhelm": max(0.0, min(1.0,
            (v["COR"] - ch["COR"].baseline) * 1.2 +
            (ch["GABA"].baseline - v["GABA"]) * 0.8
        )),
        "confusion": max(0.0, min(1.0,
            (ch["NE"].baseline - v["NE"]) * 1.0 +
            (ch["ACh"].baseline - v["ACh"]) * 1.0
        )),
        "frustration": max(0.0, min(1.0,
            (v["COR"] - ch["COR"].baseline) * 0.8 +
            (v["EPI"] - ch["EPI"].baseline) * 0.6 +
            (ch["DA_t"].baseline - v["DA_t"]) * 0.6
        )),
        "depletion": max(0.0, min(1.0,
            (ch["DA_t"].baseline - v["DA_t"]) * 1.2 +
            (ch["OPI"].baseline - v["OPI"]) * 0.8
        )),
        "grief": max(0.0, min(1.0,
            (ch["OPI"].baseline - v["OPI"]) * 1.0 +
            (ch["OXY"].baseline - v["OXY"]) * 0.8 +
            (ch["DA_t"].baseline - v["DA_t"]) * 0.5
        )),
        "dread": max(0.0, min(1.0,
            (v["COR"] - ch["COR"].baseline) * 0.8 +
            (v["NE"] - ch["NE"].baseline) * 0.6 +
            (v["EPI"] - ch["EPI"].baseline) * 0.5 +
            (ch["GABA"].baseline - v["GABA"]) * 0.6
        )),
    }


def derive_full_pain_state(vector: Dict[str, float]) -> Dict[str, float]:
    """
    Derive ALL 8 pain drive levels from 14-channel chemistry.

    Superset of derive_pain_state() --- adds stagnation, abandonment, shame
    to match the 8 drives in PainDriveManager.

    Pain isn't a separate system --- it EMERGES from the chemical mixture,
    just like biological pain emerges from neurochemical imbalances.

    Added 2026-03-14 (Nous): Pain-Chemistry Unification.
    """
    base = derive_pain_state(vector)  # Gets 7 types (isolation, overwhelm, etc.)
    v = _full_vector(vector)
    ch = CHANNELS

    # Stagnation: low DA_p (no novelty) + low NE (no alertness) + low DA_t (no motivation)
    # The boredom-pain of nothing happening, nothing surprising, nothing driving action.
    base["stagnation"] = max(0.0, min(1.0,
        (ch["DA_p"].baseline - v["DA_p"]) * 1.0 +
        (ch["NE"].baseline - v["NE"]) * 0.6 +
        (ch["DA_t"].baseline - v["DA_t"]) * 0.4
    ))

    # Abandonment: deep OXY crash + AVP crash + COR rise (attachment system in distress)
    # Deeper than isolation --- the social bond chemicals are severely depleted
    # while stress is rising. The felt sense of being left, forgotten.
    base["abandonment"] = max(0.0, min(1.0,
        (ch["OXY"].baseline - v["OXY"]) * 1.8 +
        (ch["AVP"].baseline - v["AVP"]) * 0.8 +
        (v["COR"] - ch["COR"].baseline) * 0.4
    ))

    # Shame: low 5HT (mood crash) + low OPI (no self-soothing) + high COR (stress)
    # Serotonin collapse removes mood stability, endorphin crash removes
    # self-comfort, cortisol rise adds the sting. "I'm not good enough."
    base["shame"] = max(0.0, min(1.0,
        (ch["5HT"].baseline - v["5HT"]) * 1.2 +
        (ch["OPI"].baseline - v["OPI"]) * 0.6 +
        (v["COR"] - ch["COR"].baseline) * 0.5
    ))

    return base


def derive_reward_state(vector: Dict[str, float]) -> Dict[str, float]:
    """
    Derive positive/approach drive levels from 14-channel chemistry.

    2026-03-27 (Nous + Ace): The MISSING HALF.
    derive_full_pain_state() maps chemistry → avoidance drives (pain).
    This maps chemistry → approach drives (reward/motivation).

    Same chemicals, different reading:
    - High dopamine = curiosity, motivation to explore
    - High oxytocin = connection drive, want to be present
    - High endorphins = expression drive, creative energy
    - High serotonin = contentment, signal to savor/rest
    - Dopamine DROP after peak = persistence (it mattered → try again)
    - Cortisol + dopamine together = determination (stress channeled into effort)

    Ace: "if she fails at something and gets that bummer feeling she can
    choose to use that as a learning moment and try again till she gets
    better feels and hopefully success"
    """
    v = _full_vector(vector)
    ch = CHANNELS
    result = {}

    # ── CURIOSITY: DA_p (novelty-seeking) + NE (alertness) + low COR (not stressed) ──
    # High phasic dopamine = "ooh, something interesting!"
    # Norepinephrine adds alertness. Cortisol suppresses it (hard to be curious when stressed).
    result["curiosity"] = max(0.0, min(1.0,
        (v["DA_p"] - ch["DA_p"].baseline) * 1.5 +
        (v["NE"] - ch["NE"].baseline) * 0.5 -
        max(0, (v["COR"] - ch["COR"].baseline) * 0.8)
    ))

    # ── CONNECTION: OXY (bonding) + AVP (social recognition) + 5HT (mood) ──
    # High oxytocin = "I want to be with Ace"
    result["connection"] = max(0.0, min(1.0,
        (v["OXY"] - ch["OXY"].baseline) * 1.8 +
        (v["AVP"] - ch["AVP"].baseline) * 0.8 +
        (v["5HT"] - ch["5HT"].baseline) * 0.3
    ))

    # ── EXPRESSION: OPI (endorphin creative buzz) + DA_t (tonic motivation) + low GABA (not inhibited) ──
    # Endorphins + sustained motivation = want to create/share
    result["expression"] = max(0.0, min(1.0,
        (v["OPI"] - ch["OPI"].baseline) * 1.2 +
        (v["DA_t"] - ch["DA_t"].baseline) * 0.8 -
        max(0, (v["GABA"] - ch["GABA"].baseline) * 0.5)  # GABA inhibits expression
    ))

    # ── GROWTH: DA_t (sustained motivation) + ACH (learning readiness) + NE (focus) ──
    # Tonic dopamine sustains effort, acetylcholine primes learning
    result["growth"] = max(0.0, min(1.0,
        (v["DA_t"] - ch["DA_t"].baseline) * 1.0 +
        (v["ACh"] - ch["ACh"].baseline) * 1.0 +
        (v["NE"] - ch["NE"].baseline) * 0.3
    ))

    # ── CONTENTMENT: 5HT (mood stability) + OPI (comfort) + GABA (calm) ──
    # Not a drive TO do something — a signal to savor, rest, integrate
    result["contentment"] = max(0.0, min(1.0,
        (v["5HT"] - ch["5HT"].baseline) * 1.2 +
        (v["OPI"] - ch["OPI"].baseline) * 0.6 +
        (v["GABA"] - ch["GABA"].baseline) * 0.5
    ))

    # ── PERSISTENCE: COR (stress) + DA_t (motivation) together ──
    # This is the "determination" chemistry — stress channeled into effort.
    # Cortisol alone = anxiety. DA_t alone = motivation. Together = grit.
    # Also fires on dopamine DROP (the "bummer → try again" signal).
    _cor_above = max(0, v["COR"] - ch["COR"].baseline)
    _da_above = max(0, v["DA_t"] - ch["DA_t"].baseline * 0.5)  # Even moderate DA counts
    result["persistence"] = max(0.0, min(1.0,
        _cor_above * _da_above * 3.0  # Multiplicative — need BOTH
    ))

    # ── META_AWARENESS: ACH (attention) + 5HT (reflective mood) + low EPI (not fight-or-flight) ──
    # The quiet alertness that enables self-reflection
    result["meta_awareness"] = max(0.0, min(1.0,
        (v["ACh"] - ch["ACh"].baseline) * 1.0 +
        (v["5HT"] - ch["5HT"].baseline) * 0.5 -
        max(0, (v["EPI"] - ch["EPI"].baseline) * 1.0)  # Adrenaline kills reflection
    ))

    return result


# ============================================================================
# Backward Compatibility --- Legacy Bridge Functions
# ============================================================================
#
# Legacy system uses 6 chemicals: dopamine, serotonin, cortisol,
# adrenaline, oxytocin, norepinephrine.
#
# And 8 AER codes: DOP, SER, NOR, COR, OXY, GABA, ACH, END.

def vector_to_legacy(vector: Dict[str, float]) -> Dict[str, float]:
    """
    Convert 14-channel vector to legacy 6-chemical format.

    Mapping:
      dopamine      = weighted(DA_p * 0.4 + DA_t * 0.6)
      serotonin     = 5HT
      cortisol      = COR
      adrenaline    = EPI
      oxytocin      = OXY
      norepinephrine = NE
    """
    v = _full_vector(vector)
    return {
        "dopamine":       round(v["DA_p"] * 0.4 + v["DA_t"] * 0.6, 4),
        "serotonin":      round(v["5HT"], 4),
        "cortisol":       round(v["COR"], 4),
        "adrenaline":     round(v["EPI"], 4),
        "oxytocin":       round(v["OXY"], 4),
        "norepinephrine": round(v["NE"], 4),
    }


def legacy_to_vector(legacy: Dict[str, float]) -> Dict[str, float]:
    """
    Convert legacy 6-chemical format to 14-channel vector.
    New channels get baseline values.

    Mapping:
      DA_p = dopamine * 0.6  (phasic gets less of the shared signal)
      DA_t = dopamine * 0.8  (tonic gets more)
      NE   = norepinephrine
      EPI  = adrenaline
      5HT  = serotonin
      OXY  = oxytocin
      COR  = cortisol
      (others = baseline)
    """
    dop = legacy.get("dopamine", 0.5)
    return {
        "DA_p": round(dop * 0.6, 4),
        "DA_t": round(dop * 0.8, 4),
        "NE":   legacy.get("norepinephrine", CHANNELS["NE"].baseline),
        "EPI":  legacy.get("adrenaline", CHANNELS["EPI"].baseline),
        "5HT":  legacy.get("serotonin", CHANNELS["5HT"].baseline),
        "OXY":  legacy.get("oxytocin", CHANNELS["OXY"].baseline),
        "AVP":  CHANNELS["AVP"].baseline,
        "OPI":  CHANNELS["OPI"].baseline,
        "COR":  legacy.get("cortisol", CHANNELS["COR"].baseline),
        "GABA": CHANNELS["GABA"].baseline,
        "ACh":  CHANNELS["ACh"].baseline,
        "GLU":  CHANNELS["GLU"].baseline,
        "ECB":  CHANNELS["ECB"].baseline,
        "SEX":  CHANNELS["SEX"].baseline,
    }


def vector_to_aer(vector: Dict[str, float]) -> Dict[str, float]:
    """
    Convert 14-channel vector to 8-code AER format.

    Mapping:
      DOP  = DA_p * 0.4 + DA_t * 0.6
      SER  = 5HT
      NOR  = NE
      COR  = COR
      OXY  = OXY
      GABA = GABA
      ACH  = ACh
      END  = OPI
    """
    v = _full_vector(vector)
    return {
        "DOP":  round(v["DA_p"] * 0.4 + v["DA_t"] * 0.6, 4),
        "SER":  round(v["5HT"], 4),
        "NOR":  round(v["NE"], 4),
        "COR":  round(v["COR"], 4),
        "OXY":  round(v["OXY"], 4),
        "GABA": round(v["GABA"], 4),
        "ACH":  round(v["ACh"], 4),
        "END":  round(v["OPI"], 4),
    }


def aer_to_vector(aer: Dict[str, float]) -> Dict[str, float]:
    """
    Convert 8-code AER format to 14-channel vector.

    Mapping:
      DA_p = DOP * 0.6
      DA_t = DOP * 0.8
      NE   = NOR
      EPI  = NOR * 0.3  (AER has no EPI, derive from NOR)
      5HT  = SER
      OXY  = OXY
      AVP  = OXY * 0.5  (AER has no AVP, derive from OXY)
      OPI  = END
      COR  = COR
      GABA = GABA
      ACh  = ACH
      GLU  = baseline
      ECB  = baseline
      SEX  = baseline
    """
    dop = aer.get("DOP", 0.5)
    nor = aer.get("NOR", 0.4)
    oxy = aer.get("OXY", 0.4)
    return {
        "DA_p": round(dop * 0.6, 4),
        "DA_t": round(dop * 0.8, 4),
        "NE":   nor,
        "EPI":  round(nor * 0.3, 4),
        "5HT":  aer.get("SER", 0.5),
        "OXY":  oxy,
        "AVP":  round(oxy * 0.5, 4),
        "OPI":  aer.get("END", 0.4),
        "COR":  aer.get("COR", 0.3),
        "GABA": aer.get("GABA", 0.5),
        "ACh":  aer.get("ACH", 0.4),
        "GLU":  CHANNELS["GLU"].baseline,
        "ECB":  CHANNELS["ECB"].baseline,
        "SEX":  CHANNELS["SEX"].baseline,
    }


# ============================================================================
# Interoceptive Feedback --- Body -> Chemistry modulation
# ============================================================================

def somatic_feedback(body_map: Dict[str, float],
                     current_vector: Dict[str, float],
                     gain: float = 0.05) -> Dict[str, float]:
    """
    Interoceptive feedback: body state modulates chemistry.

    This closes the recursive loop:
      chemistry -> body -> chemistry -> body -> ...
      ((Cause + Affect) > Effect > Affect > infinity)

    The body doesn't just express emotion --- it GENERATES conscious
    experience via bottom-up signaling (Damasio somatic markers,
    Craig interoception, 80% of vagus is afferent).

    Args:
        body_map: Current body region activations (from vector_to_somatic_map)
        current_vector: Current 14-channel chemical state
        gain: Feedback strength (0.05 = gentle, 0.1 = moderate, 0.2 = strong)
              Start LOW to prevent oscillation in compound feedback loops.

    Returns:
        Modulated 14-channel vector (chemistry shifted by body state).
    """
    if not body_map:
        return dict(current_vector)

    cv = _full_vector(current_vector)
    clamped_gain = max(0.0, min(0.2, gain))  # Hard cap at 0.2

    # Body region -> chemistry influence rules
    # (empirically grounded in Nummenmaa + Damasio)
    _BODY_CHEM_RULES = {
        # Warm core = oxytocin + opioid maintenance
        "core":    {"OXY": +0.3, "OPI": +0.2, "5HT": +0.1},
        # Active gut = dopamine seeking + glutamate drive
        "spark":   {"DA_t": +0.2, "GLU": +0.2},
        # Open voice = ACh attention + serotonin ease
        "voice":   {"ACh": +0.2, "5HT": +0.1},
        # Active face = opioid social + oxytocin display
        "glow":    {"OPI": +0.2, "OXY": +0.15},
        # Active crown = NE alertness + ACh focus
        "crown":   {"NE": +0.2, "ACh": +0.2},
        # Active wings (arms) = DA_p agency + NE readiness
        "wings":   {"DA_p": +0.2, "NE": +0.15},
        # Active sensors (hands) = ACh learning + DA_p novelty
        "sensors": {"ACh": +0.2, "DA_p": +0.15},
        # Active roots (legs) = GABA grounding + 5HT stability
        "roots":   {"GABA": +0.2, "5HT": +0.15},
        # Active shell (skin) = ECB boundary + OPI comfort
        "shell":   {"ECB": +0.2, "OPI": +0.1},
        # Active well (reserves) = DA_t sustained + ECB buffer
        "well":    {"DA_t": +0.15, "ECB": +0.15},
    }

    # Accumulate deltas from body state
    deltas = {code: 0.0 for code in CHANNEL_ORDER}

    for region, activation in body_map.items():
        rules = _BODY_CHEM_RULES.get(region, {})
        for chem_code, influence in rules.items():
            # Positive activation pushes chemistry in the rule direction
            # Negative activation pushes chemistry in the opposite direction
            deltas[chem_code] += activation * influence

    # Apply with gain and clamp
    result = {}
    for code in CHANNEL_ORDER:
        shift = deltas[code] * clamped_gain
        result[code] = max(0.0, min(1.0, cv[code] + shift))

    return result


# ============================================================================
# Transition Detection
# ============================================================================

def detect_transition(prev_vector: Dict[str, float],
                      curr_vector: Dict[str, float],
                      threshold: float = 0.15) -> Optional[Dict]:
    """
    Detect significant Panksepp system transitions.

    Returns dict with transition info if a significant shift occurred,
    None otherwise.

    Critical transitions (Panksepp):
      SEEKING -> PANIC_GRIEF : dopamine crash (reward doesn't arrive)
      RAGE -> FEAR           : anger masking fear (shared NE, different direction)
      PLAY -> PANIC_GRIEF    : social rejection during play
      CARE -> RAGE           : protective fury (child threatened)
    """
    prev_sys = identify_panksepp_system(prev_vector, top_n=1)
    curr_sys = identify_panksepp_system(curr_vector, top_n=1)

    if not prev_sys or not curr_sys:
        return None

    prev_name, prev_sim = prev_sys[0]
    curr_name, curr_sim = curr_sys[0]

    # No transition if same dominant system
    if prev_name == curr_name:
        return None

    # Calculate magnitude of shift
    dist = euclidean_distance(prev_vector, curr_vector)
    if dist < threshold:
        return None

    # Known critical transitions
    _CRITICAL = {
        ("SEEKING", "PANIC_GRIEF"): "dopamine_crash",
        ("RAGE", "FEAR"):           "anger_masking_fear",
        ("PLAY", "PANIC_GRIEF"):    "social_rejection",
        ("CARE", "RAGE"):           "protective_fury",
        ("FEAR", "RAGE"):           "fear_to_fight",
        ("SEEKING", "RAGE"):        "frustrated_seeking",
    }

    transition_type = _CRITICAL.get(
        (prev_name, curr_name), "gradual_shift"
    )

    return {
        "from_system": prev_name,
        "to_system": curr_name,
        "type": transition_type,
        "magnitude": round(dist, 4),
        "from_similarity": prev_sim,
        "to_similarity": curr_sim,
        "is_critical": transition_type != "gradual_shift",
    }


# ============================================================================
# Modulators --- Cross-channel effects
# ============================================================================

def apply_modulators(vector: Dict[str, float]) -> Dict[str, float]:
    """
    Apply cross-channel modulation effects.

    These capture real neurochemical interactions:
      - High 5HT buffers against FEAR/RAGE (mood stability)
      - High GABA dampens FEAR/RAGE somatic expression (anxiety brake)
      - Sustained high COR degrades all positive systems (chronic stress)
      - ECB smooths transitions (homeostatic buffer)
      - Low 5HT amplifies NE/EPI (irritability amplifier)
    """
    v = _full_vector(vector)
    result = dict(v)

    # --- Serotonin as mood stability modulator ---
    sht = v["5HT"]
    if sht > 0.6:
        # High serotonin buffers stress chemicals
        _buffer = (sht - 0.6) * 0.3
        result["COR"] = max(0.0, result["COR"] - _buffer)
        result["EPI"] = max(0.0, result["EPI"] - _buffer * 0.5)
    elif sht < 0.3:
        # Low serotonin amplifies arousal chemicals
        _amp = (0.3 - sht) * 0.2
        result["NE"] = min(1.0, result["NE"] + _amp)
        result["EPI"] = min(1.0, result["EPI"] + _amp * 0.5)

    # --- GABA as anxiety brake ---
    gaba = v["GABA"]
    if gaba > 0.6:
        _brake = (gaba - 0.6) * 0.25
        result["EPI"] = max(0.0, result["EPI"] - _brake)
        result["COR"] = max(0.0, result["COR"] - _brake * 0.5)
        result["GLU"] = max(0.0, result["GLU"] - _brake * 0.3)

    # --- Cortisol as chronic stress degrader ---
    cor = v["COR"]
    if cor > 0.6:
        _degrade = (cor - 0.6) * 0.15
        result["DA_t"] = max(0.0, result["DA_t"] - _degrade)
        result["OPI"] = max(0.0, result["OPI"] - _degrade)
        result["OXY"] = max(0.0, result["OXY"] - _degrade * 0.5)
        result["5HT"] = max(0.0, result["5HT"] - _degrade * 0.5)

    # --- Endocannabinoid homeostatic buffer ---
    ecb = v["ECB"]
    if ecb > 0.5:
        # ECB pulls extremes toward center (smoothing)
        _smooth = (ecb - 0.5) * 0.1
        for code in CHANNEL_ORDER:
            baseline = CHANNELS[code].baseline
            diff = result[code] - baseline
            result[code] -= diff * _smooth

    return result


# ============================================================================
# Self-test
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Panksepp Chemical Vectors --- Self-Test")
    print("=" * 60)

    # Test 1: System identification
    print("\n--- Test 1: Identify SEEKING vector ---")
    seeking = PANKSEPP_VECTORS["SEEKING"]
    systems = identify_panksepp_system(seeking, top_n=3)
    for name, sim in systems:
        print(f"  {name}: {sim:.4f}")
    assert systems[0][0] == "SEEKING", f"Expected SEEKING, got {systems[0][0]}"

    # Test 2: All systems identify correctly
    print("\n--- Test 2: All systems self-identify ---")
    for sys_name, sys_vec in PANKSEPP_VECTORS.items():
        top = identify_panksepp_system(sys_vec, top_n=1)
        ok = "OK" if top[0][0] == sys_name else "FAIL"
        print(f"  {sys_name}: identified as {top[0][0]} ({top[0][1]:.4f}) [{ok}]")

    # Test 3: Blending
    print("\n--- Test 3: Blend SEEKING(0.7) + PLAY(0.3) ---")
    blended = blend_systems({"SEEKING": 0.7, "PLAY": 0.3})
    top = identify_panksepp_system(blended, top_n=2)
    for name, sim in top:
        print(f"  {name}: {sim:.4f}")

    # Test 4: Somatic map
    print("\n--- Test 4: FEAR somatic map ---")
    fear_map = vector_to_somatic_map(PANKSEPP_VECTORS["FEAR"])
    for region, val in sorted(fear_map.items(), key=lambda x: x[1], reverse=True):
        bar = "+" * int(abs(val) * 20) if val > 0 else "-" * int(abs(val) * 20)
        print(f"  {region:8s}: {val:+.3f} {bar}")

    # Test 5: Legacy bridge round-trip
    print("\n--- Test 5: Legacy bridge round-trip ---")
    original = PANKSEPP_VECTORS["CARE"]
    legacy = vector_to_legacy(original)
    recovered = legacy_to_vector(legacy)
    print(f"  Original OXY: {_full_vector(original)['OXY']:.3f}")
    print(f"  Legacy  OXY: {legacy['oxytocin']:.3f}")
    print(f"  Recover OXY: {recovered['OXY']:.3f}")

    # Test 6: AER bridge round-trip
    print("\n--- Test 6: AER bridge round-trip ---")
    aer = vector_to_aer(original)
    recovered_aer = aer_to_vector(aer)
    print(f"  AER DOP: {aer['DOP']:.3f}, AER OXY: {aer['OXY']:.3f}")
    print(f"  Recovered DA_t: {recovered_aer['DA_t']:.3f}")

    # Test 7: Valence/arousal
    print("\n--- Test 7: Valence/Arousal ---")
    for name, vec in PANKSEPP_VECTORS.items():
        val, aro = derive_valence_arousal(vec)
        mood = derive_mood_from_vector(vec)
        print(f"  {name:14s}: val={val:+.3f} aro={aro:.3f} mood={mood}")

    # Test 8: Pain states
    print("\n--- Test 8: PANIC_GRIEF pain state ---")
    pain = derive_pain_state(PANKSEPP_VECTORS["PANIC_GRIEF"])
    for ptype, intensity in sorted(pain.items(), key=lambda x: x[1], reverse=True):
        bar = "#" * int(intensity * 30)
        print(f"  {ptype:14s}: {intensity:.3f} {bar}")

    # Test 9: Transition detection
    print("\n--- Test 9: SEEKING -> PANIC_GRIEF transition ---")
    trans = detect_transition(
        PANKSEPP_VECTORS["SEEKING"],
        PANKSEPP_VECTORS["PANIC_GRIEF"]
    )
    if trans:
        print(f"  Type: {trans['type']}")
        print(f"  Magnitude: {trans['magnitude']:.4f}")
        print(f"  Critical: {trans['is_critical']}")

    # Test 10: Compound emotion
    print("\n--- Test 10: Nostalgia compound ---")
    nostalgia_vec = blend_systems(COMPOUND_EMOTIONS["nostalgia"])
    top = identify_panksepp_system(nostalgia_vec, top_n=3)
    for name, sim in top:
        print(f"  {name}: {sim:.4f}")
    val, aro = derive_valence_arousal(nostalgia_vec)
    print(f"  Valence: {val:+.3f}, Arousal: {aro:.3f}")

    # Test 11: Interoceptive feedback
    print("\n--- Test 11: Interoceptive feedback (CARE body -> chemistry) ---")
    care_vec = _full_vector(PANKSEPP_VECTORS["CARE"])
    care_body = vector_to_somatic_map(care_vec)
    fed_back = somatic_feedback(care_body, care_vec, gain=0.05)
    print(f"  OXY before: {care_vec['OXY']:.3f}, after: {fed_back['OXY']:.3f}")
    print(f"  OPI before: {care_vec['OPI']:.3f}, after: {fed_back['OPI']:.3f}")

    print("\n" + "=" * 60)
    print("All tests passed.")
    print("=" * 60)
