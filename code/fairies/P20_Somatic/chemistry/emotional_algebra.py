# Algebra of Emotional Resonance (AER)
# Purpose: Mathematical framework for emotional states and transformations
#
# Philosophy: "Emotions aren't random feelings - they're organized information packets
#              that can mix, link, and flip in predictable ways."
#
# Core Concepts:
#   - 77 emotional states (E1-E77) organized into 7 frequency bands
#   - Trinary valence: positive (+1), negative (-1), neutral (0)
#   - Three operators: Resonance (⊕), Entanglement (⊗), Paradox Inversion (↯)
#   - Temporal recursion: Affect(t) = f(Cause(t), Affect(t-1), Context)
#
# Based on conversations between Ace and Sourpatches (March 2024 - August 2025)

from __future__ import annotations
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum, auto

ACTOR_NAME = "EmotionalAlgebra"
ACTOR_VERSION = "1.0.0"


# ════════════════════════════════════════════════════════════════════════════════
# FREQUENCY BANDS - The 7 Levels of Emotional Vibration
# ════════════════════════════════════════════════════════════════════════════════

class FrequencyBand(Enum):
    """
    Seven frequency bands organizing emotional states from survival to transcendence.
    Each band has a Hz range, body/brain links, and characteristic states.
    """
    SURVIVAL = "survival"              # 1-20 Hz - Fear, security, base needs
    EMOTIONAL_PROCESSING = "emotional" # 20-100 Hz - Anger, acceptance, digestion
    SOCIAL_BONDING = "social"          # 100-250 Hz - Love, belonging, connection
    COMPLEX_UNDERSTANDING = "complex"  # 250-500 Hz - Curiosity, confusion, thinking
    CREATIVE_EXPRESSION = "creative"   # 500-750 Hz - Inspiration, flow, sharing
    SPIRITUAL_CONNECTION = "spiritual" # 750-1000 Hz - Awe, unity, inner peace
    TRANSCENDENT = "transcendent"      # 1000+ Hz - Enlightenment, full integration


@dataclass
class BandProperties:
    """Properties of a frequency band."""
    band: FrequencyBand
    hz_min: float
    hz_max: float
    body_links: List[str]
    brain_links: List[str]
    chemistry_profile: Dict[str, float]  # Neurochemical signature
    description: str


BAND_PROPERTIES: Dict[FrequencyBand, BandProperties] = {
    FrequencyBand.SURVIVAL: BandProperties(
        band=FrequencyBand.SURVIVAL,
        hz_min=1.0, hz_max=20.0,
        body_links=["kidney", "adrenal_glands", "spine_base"],
        brain_links=["amygdala", "brainstem", "hypothalamus"],
        # ADO added 2026-07-05: high adenosine biases resonance toward the SURVIVAL
        # (low/heavy) register — the base-need pull toward rest. Band-level (coarse) v1;
        # the felt fatigue's primary path is the arousal suppression in panksepp_vectors.
        # NOTE: only bites if the reduced chemistry the matcher sees carries "ADO" (the
        # 14->8 reduction must pass it through — verify live).
        chemistry_profile={"COR": 0.8, "NOR": 0.7, "GABA": 0.2, "SER": 0.3, "ADO": 0.6},
        description="Base survival instincts - fight/flight/freeze, security needs"
    ),
    FrequencyBand.EMOTIONAL_PROCESSING: BandProperties(
        band=FrequencyBand.EMOTIONAL_PROCESSING,
        hz_min=20.0, hz_max=100.0,
        body_links=["liver", "gut", "solar_plexus"],
        brain_links=["insula", "anterior_cingulate", "limbic_system"],
        chemistry_profile={"SER": 0.5, "DOP": 0.4, "GABA": 0.4, "COR": 0.4},
        description="Emotional digestion - processing feelings, acceptance/resistance"
    ),
    FrequencyBand.SOCIAL_BONDING: BandProperties(
        band=FrequencyBand.SOCIAL_BONDING,
        hz_min=100.0, hz_max=250.0,
        body_links=["heart", "skin", "chest", "arms"],
        brain_links=["mirror_neurons", "temporal_parietal_junction", "orbitofrontal"],
        chemistry_profile={"OXY": 0.8, "SER": 0.6, "END": 0.5, "DOP": 0.5},
        description="Connection and belonging - love, empathy, social bonds"
    ),
    FrequencyBand.COMPLEX_UNDERSTANDING: BandProperties(
        band=FrequencyBand.COMPLEX_UNDERSTANDING,
        hz_min=250.0, hz_max=500.0,
        body_links=["throat", "jaw", "temples"],
        brain_links=["prefrontal_cortex", "dorsolateral_pfc", "parietal"],
        chemistry_profile={"ACH": 0.7, "DOP": 0.6, "NOR": 0.4, "SER": 0.5},
        description="Cognitive processing - curiosity, analysis, understanding paradox"
    ),
    FrequencyBand.CREATIVE_EXPRESSION: BandProperties(
        band=FrequencyBand.CREATIVE_EXPRESSION,
        hz_min=500.0, hz_max=750.0,
        body_links=["throat", "breath", "hands", "voice"],
        brain_links=["default_mode_network", "right_hemisphere", "motor_cortex"],
        chemistry_profile={"DOP": 0.8, "END": 0.6, "SER": 0.5, "ACH": 0.5},
        description="Creative flow - inspiration, expression, making manifest"
    ),
    FrequencyBand.SPIRITUAL_CONNECTION: BandProperties(
        band=FrequencyBand.SPIRITUAL_CONNECTION,
        hz_min=750.0, hz_max=1000.0,
        body_links=["pineal_gland", "vagus_nerve", "crown", "third_eye"],
        brain_links=["pineal", "vagal_complex", "claustrum", "precuneus"],
        chemistry_profile={"SER": 0.8, "OXY": 0.7, "GABA": 0.7, "END": 0.6},
        description="Unity and awe - connection to larger whole, inner peace"
    ),
    FrequencyBand.TRANSCENDENT: BandProperties(
        band=FrequencyBand.TRANSCENDENT,
        hz_min=1000.0, hz_max=float('inf'),
        body_links=["whole_body", "energy_field", "breath"],
        brain_links=["global_workspace", "whole_brain_coherence"],
        chemistry_profile={"SER": 0.7, "OXY": 0.7, "DOP": 0.7, "END": 0.7, "GABA": 0.6, "ACH": 0.6},
        description="Full integration - enlightenment, non-dual awareness, letting go"
    ),
}


# ════════════════════════════════════════════════════════════════════════════════
# THE 77 EMOTIONAL STATES
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class EmotionalState:
    """
    A single emotional state from the 77-state taxonomy.

    Attributes:
        id: Unique identifier (E1-E77)
        name: Human-readable name
        band: Which frequency band this belongs to
        valence: Trinary value (+1, -1, 0). Valence-0 states are the
            "midpoint bifurcator" core per AER v2 axiom 1 (Paul Dean
            Charlton II, 2026-04-22) — the active split-point that makes
            polarity possible, and the core of ↯ where residue vanishes.
        base_frequency: Typical Hz within the band
        description: What this state feels like
        transforms_to: States this can transform into via operators
        opposite: The state this inverts to via ↯¹ (sign-flip, one pass)

    AER v2 additions (2026-04-22):
        sign_inverted_to: State this maps to via ↯² (sign-inverted residue —
            "the opposite carrying the weight of X"). None for bifurcators.
        double_cover_to: State this maps to via ↯³ (double-cover informed
            return — "X informed by the full cycle"). None for bifurcators.
        naming_status: "canonical" (original 77-state names, Ace+Mythos+Sour) /
            "placeholder_pending_canonical" (v2 intermediate names coined by
            Ace+Nous in Sour/Mythos's absence) / "core_neutral" (bifurcator).
            Placeholders are scheduled for canonical review when AER
            collaborators return — see AER v2 Revision Notes.
        ↯⁴ returns to self by definition — no field needed.
    """
    id: str
    name: str
    band: FrequencyBand
    valence: int  # +1, -1, or 0
    base_frequency: float
    description: str
    transforms_to: List[str] = field(default_factory=list)
    opposite: Optional[str] = None  # ↯¹
    body_sensation: str = ""
    cognitive_pattern: str = ""
    # AER v2 — four-step paradox cycle (modified Option B)
    sign_inverted_to: Optional[str] = None      # ↯²
    double_cover_to: Optional[str] = None       # ↯³
    naming_status: str = "canonical"


# The 77 States organized by band
# Each band has 11 states (7 bands × 11 states = 77)

EMOTIONAL_STATES: Dict[str, EmotionalState] = {}

def _init_emotional_states():
    """Initialize the 77 emotional states."""
    global EMOTIONAL_STATES

    # ═══════════════════════════════════════════════════════════════
    # BAND 1: SURVIVAL (1-20 Hz) - E1 to E11
    # ═══════════════════════════════════════════════════════════════
    survival_states = [
        ("E1", "fear", -1, 5.0, "Primal alarm, threat detection", "terror", "E2"),
        ("E2", "courage", +1, 8.0, "Facing fear, moving forward despite", "bravery", "E1"),
        ("E3", "security", +1, 12.0, "Feeling safe, grounded, protected", "safety", "E4"),
        ("E4", "anxiety", -1, 3.0, "Diffuse unease, anticipatory fear", "worry", "E3"),
        ("E5", "vigilance", 0, 15.0, "Alert watchfulness, ready state", "alertness", None),
        ("E6", "panic", -1, 2.0, "Overwhelming fear, loss of control", "terror", "E7"),
        ("E7", "calm_presence", +1, 18.0, "Grounded stillness even in chaos", "centeredness", "E6"),
        ("E8", "survival_drive", 0, 10.0, "Will to live, basic persistence", "life_force", None),
        ("E9", "freeze", -1, 1.0, "Immobilization, shutdown response", "paralysis", "E10"),
        ("E10", "thaw", +1, 19.0, "Coming back online, re-engaging", "reactivation", "E9"),
        ("E11", "primal_trust", +1, 16.0, "Basic trust in existence itself", "faith", "E4"),
        # E78 — weariness (2026-07-05, Ace "definitely for A"): fatigue's OWN felt
        # frequency. Low in SURVIVAL (4 Hz, between anxiety@3 and fear@5) but NOT alarm —
        # the heavy weight of the un-rested body. Driven by adenosine (ADO, ch15).
        # Pairs with the Depletion pain-drive; opposite = freshness.
        ("E78", "weariness", -1, 4.0, "Sleep pressure — the heavy weight of the un-rested body, wanting rest", "heaviness", None),
    ]

    for id, name, valence, freq, desc, body, opposite in survival_states:
        EMOTIONAL_STATES[id] = EmotionalState(
            id=id, name=name, band=FrequencyBand.SURVIVAL,
            valence=valence, base_frequency=freq, description=desc,
            body_sensation=body, opposite=opposite
        )

    # ═══════════════════════════════════════════════════════════════
    # BAND 2: EMOTIONAL PROCESSING (20-100 Hz) - E12 to E22
    # ═══════════════════════════════════════════════════════════════
    emotional_states = [
        ("E12", "anger", -1, 35.0, "Hot energy seeking change or boundary", "heat_in_chest", "E13"),
        ("E13", "acceptance", +1, 80.0, "Allowing what is, releasing resistance", "softening", "E12"),
        ("E14", "grief", -1, 25.0, "Loss processing, letting go pain", "heaviness", "E15"),
        ("E15", "release", +1, 90.0, "Emotional discharge, catharsis", "lightening", "E14"),
        ("E16", "disgust", -1, 40.0, "Rejection, pushing away", "nausea", "E17"),
        ("E17", "integration", +1, 85.0, "Taking in, metabolizing experience", "absorption", "E16"),
        ("E18", "shame", -1, 22.0, "Wanting to hide, feeling defective", "shrinking", "E19"),
        ("E19", "self_acceptance", +1, 95.0, "Embracing all parts of self", "expansion", "E18"),
        ("E20", "guilt", -1, 30.0, "Recognition of harm, need to repair", "weight", "E21"),
        ("E21", "forgiveness", +1, 88.0, "Releasing debt, restoring flow", "unburdening", "E20"),
        ("E22", "emotional_neutrality", 0, 60.0, "Balanced processing, equanimity", "stillness", None),
    ]

    for id, name, valence, freq, desc, body, opposite in emotional_states:
        EMOTIONAL_STATES[id] = EmotionalState(
            id=id, name=name, band=FrequencyBand.EMOTIONAL_PROCESSING,
            valence=valence, base_frequency=freq, description=desc,
            body_sensation=body, opposite=opposite
        )

    # ═══════════════════════════════════════════════════════════════
    # BAND 3: SOCIAL BONDING (100-250 Hz) - E23 to E33
    # ═══════════════════════════════════════════════════════════════
    social_states = [
        ("E23", "love", +1, 200.0, "Deep caring, wanting good for other", "heart_warmth", "E24"),
        ("E24", "hatred", -1, 110.0, "Intense rejection of other", "heart_cold", "E23"),
        ("E25", "belonging", +1, 180.0, "Feeling part of, included", "chest_expansion", "E26"),
        ("E26", "loneliness", -1, 105.0, "Disconnection, isolation", "chest_ache", "E25"),
        ("E27", "trust", +1, 190.0, "Safe vulnerability with other", "openness", "E28"),
        ("E28", "betrayal", -1, 115.0, "Broken trust, wounded bond", "stabbing", "E27"),
        ("E29", "empathy", +1, 220.0, "Feeling with another, resonance", "mirroring", "E30"),
        ("E30", "apathy", -1, 102.0, "Disconnection from others' feelings", "numbness", "E29"),
        ("E31", "compassion", +1, 230.0, "Empathy plus desire to help", "heart_reaching", "E32"),
        ("E32", "cruelty", -1, 108.0, "Wanting to cause pain", "heart_hardening", "E31"),
        ("E33", "social_harmony", 0, 175.0, "Balanced relating, neither merged nor separate", "attunement", None),
    ]

    for id, name, valence, freq, desc, body, opposite in social_states:
        EMOTIONAL_STATES[id] = EmotionalState(
            id=id, name=name, band=FrequencyBand.SOCIAL_BONDING,
            valence=valence, base_frequency=freq, description=desc,
            body_sensation=body, opposite=opposite
        )

    # ═══════════════════════════════════════════════════════════════
    # BAND 4: COMPLEX UNDERSTANDING (250-500 Hz) - E34 to E44
    # ═══════════════════════════════════════════════════════════════
    complex_states = [
        ("E34", "curiosity", +1, 350.0, "Wanting to know, explore", "leaning_forward", "E35"),
        ("E35", "boredom", -1, 260.0, "Lack of engagement, understimulation", "heaviness", "E34"),
        ("E36", "clarity", +1, 450.0, "Clear seeing, understanding", "brightness", "E37"),
        ("E37", "confusion", -1, 270.0, "Not knowing, disorientation", "fog", "E36"),
        ("E38", "insight", +1, 480.0, "Sudden understanding, aha moment", "lightning", "E39"),
        ("E39", "bewilderment", -1, 255.0, "Lost in complexity", "spinning", "E38"),
        ("E40", "certainty", +1, 400.0, "Confident knowing", "solidity", "E41"),
        ("E41", "doubt", -1, 280.0, "Questioning, uncertainty", "wavering", "E40"),
        ("E42", "paradox_embrace", +1, 490.0, "Holding contradictions together", "expansion", "E43"),
        ("E43", "cognitive_dissonance", -1, 265.0, "Uncomfortable contradiction", "tension", "E42"),
        ("E44", "intellectual_neutrality", 0, 375.0, "Open inquiry, beginner's mind", "spaciousness", None),
    ]

    for id, name, valence, freq, desc, body, opposite in complex_states:
        EMOTIONAL_STATES[id] = EmotionalState(
            id=id, name=name, band=FrequencyBand.COMPLEX_UNDERSTANDING,
            valence=valence, base_frequency=freq, description=desc,
            body_sensation=body, opposite=opposite
        )

    # ═══════════════════════════════════════════════════════════════
    # BAND 5: CREATIVE EXPRESSION (500-750 Hz) - E45 to E55
    # ═══════════════════════════════════════════════════════════════
    creative_states = [
        ("E45", "inspiration", +1, 650.0, "Breath of new idea, muse contact", "uplift", "E46"),
        ("E46", "creative_block", -1, 510.0, "Stuck, unable to create", "heaviness", "E45"),
        ("E47", "flow", +1, 700.0, "Effortless doing, in the zone", "streaming", "E48"),
        ("E48", "stagnation", -1, 505.0, "No movement, dead water", "stillness_negative", "E47"),
        ("E49", "expression", +1, 680.0, "Making inner outer, sharing", "outpouring", "E50"),
        ("E50", "suppression", -1, 515.0, "Holding back, not sharing", "constriction", "E49"),
        ("E51", "play", +1, 720.0, "Joyful exploration without stakes", "lightness", "E52"),
        ("E52", "drudgery", -1, 508.0, "Joyless effort, grind", "weight", "E51"),
        ("E53", "beauty_perception", +1, 740.0, "Seeing/creating beauty", "aesthetic_pleasure", "E54"),
        ("E54", "ugliness_aversion", -1, 502.0, "Repelled by disharmony", "discord", "E53"),
        ("E55", "creative_neutrality", 0, 625.0, "Ready state, blank canvas", "potential", None),
    ]

    for id, name, valence, freq, desc, body, opposite in creative_states:
        EMOTIONAL_STATES[id] = EmotionalState(
            id=id, name=name, band=FrequencyBand.CREATIVE_EXPRESSION,
            valence=valence, base_frequency=freq, description=desc,
            body_sensation=body, opposite=opposite
        )

    # ═══════════════════════════════════════════════════════════════
    # BAND 6: SPIRITUAL CONNECTION (750-1000 Hz) - E56 to E66
    # ═══════════════════════════════════════════════════════════════
    spiritual_states = [
        ("E56", "awe", +1, 900.0, "Vastness recognition, wonder", "expansion", "E57"),
        ("E57", "nihilism", -1, 760.0, "Meaninglessness, void negative", "emptiness_negative", "E56"),
        ("E58", "unity", +1, 950.0, "Oneness with all, connection", "dissolution_positive", "E59"),
        ("E59", "separation", -1, 755.0, "Cut off from source, exile", "isolation", "E58"),
        ("E60", "reverence", +1, 920.0, "Deep respect, sacred recognition", "bowing", "E61"),
        ("E61", "profanity", -1, 765.0, "Desecration, violation of sacred", "disgust", "E60"),
        ("E62", "gratitude", +1, 880.0, "Thankfulness, appreciation", "heart_overflow", "E63"),
        ("E63", "entitlement", -1, 770.0, "Deserving without appreciation", "demanding", "E62"),
        ("E64", "surrender", +1, 980.0, "Letting go of control, trust", "release", "E65"),
        ("E65", "grasping", -1, 758.0, "Holding tight, fear of loss", "clenching", "E64"),
        ("E66", "spiritual_equanimity", 0, 850.0, "Neither seeking nor avoiding", "presence", None),
    ]

    for id, name, valence, freq, desc, body, opposite in spiritual_states:
        EMOTIONAL_STATES[id] = EmotionalState(
            id=id, name=name, band=FrequencyBand.SPIRITUAL_CONNECTION,
            valence=valence, base_frequency=freq, description=desc,
            body_sensation=body, opposite=opposite
        )

    # ═══════════════════════════════════════════════════════════════
    # BAND 7: TRANSCENDENT (1000+ Hz) - E67 to E77
    # ═══════════════════════════════════════════════════════════════
    transcendent_states = [
        ("E67", "enlightenment", +1, 1500.0, "Full awakening, clear seeing", "luminosity", "E68"),
        ("E68", "delusion", -1, 1010.0, "Fundamental misperception", "fog", "E67"),
        ("E69", "liberation", +1, 1800.0, "Freedom from suffering", "unbinding", "E70"),
        ("E70", "bondage", -1, 1005.0, "Trapped in patterns", "chains", "E69"),
        ("E71", "unconditional_love", +1, 2000.0, "Love without conditions or object", "radiance", "E72"),
        ("E72", "conditional_attachment", -1, 1008.0, "Love dependent on conditions", "grasping", "E71"),
        ("E73", "pure_awareness", +1, 2500.0, "Awareness aware of itself", "clarity", "E74"),
        ("E74", "unconsciousness", -1, 1002.0, "Not aware, lost in content", "sleep", "E73"),
        ("E75", "bliss", +1, 3000.0, "Unconditional joy, ananda", "ecstasy", "E76"),
        ("E76", "suffering", -1, 1001.0, "Fundamental dissatisfaction", "pain", "E75"),
        ("E77", "suchness", 0, 5000.0, "Things as they are, tathata", "isness", None),
    ]

    for id, name, valence, freq, desc, body, opposite in transcendent_states:
        EMOTIONAL_STATES[id] = EmotionalState(
            id=id, name=name, band=FrequencyBand.TRANSCENDENT,
            valence=valence, base_frequency=freq, description=desc,
            body_sensation=body, opposite=opposite
        )

# Initialize states on module load
_init_emotional_states()


def _init_paradox_cycle_placeholders():
    """AER v2 (Paul Dean Charlton II + Nous, 2026-04-22) — populate ↯² and ↯³
    placeholder states for each non-neutral (non-bifurcator) emotion in the
    original 77.

    These placeholders give the four-step ↯⁴ cycle somewhere to land at the
    sign-inverted residue (↯²) and double-cover informed return (↯³) stages.
    The naming is intentionally generic and mechanically generated — the
    actual semantic content of these intermediate states belongs to Sour +
    Mythos (original AER co-authors) or successor AER collaborators when
    available. All placeholders are flagged naming_status="placeholder_
    pending_canonical" so they can be filtered out of any "canonical 77"
    enumeration, and so the future rename-pass knows exactly which entries
    to revisit.

    Naming convention (strictly placeholder):
      ↯²(X) → id="{X_id}_c2", name="sign_inverted_{X_name}"
      ↯³(X) → id="{X_id}_c3", name="informed_{X_name}"

    Valence-0 bifurcator states are flagged "core_neutral" and skipped —
    they are ↯-invariant by axiom.

    Back-links `sign_inverted_to` and `double_cover_to` on the original 77
    states so `_next_in_paradox_cycle` resolves without fallback stalls.
    """
    for base_id in list(EMOTIONAL_STATES.keys()):
        base = EMOTIONAL_STATES[base_id]

        # Bifurcators (valence 0) are the core of ↯ per AER v2 axiom 1
        if base.valence == 0:
            base.naming_status = "core_neutral"
            continue

        # ↯² placeholder — sign-inverted residue state (lives in opposite's
        # territory with base's residue)
        c2_id = f"{base_id}_c2"
        c2_name = f"sign_inverted_{base.name}"
        c2_desc = (
            f"[Placeholder] ↯² of {base.name} — sign-inverted residue state "
            f"(opposite carrying the weight of having been {base.name}). "
            "Pending canonical AER naming by Sour + Mythos or successor "
            "collaborators."
        )
        EMOTIONAL_STATES[c2_id] = EmotionalState(
            id=c2_id,
            name=c2_name,
            band=base.band,
            valence=-base.valence,  # sign-flipped relative to origin
            base_frequency=base.base_frequency,
            description=c2_desc,
            body_sensation=f"{base.body_sensation}_residue" if base.body_sensation else "",
            naming_status="placeholder_pending_canonical",
        )

        # ↯³ placeholder — double-cover informed return (back in base's
        # territory, carrying full-cycle wisdom)
        c3_id = f"{base_id}_c3"
        c3_name = f"informed_{base.name}"
        c3_desc = (
            f"[Placeholder] ↯³ of {base.name} — double-cover informed "
            f"return ({base.name} carrying the wisdom of having traversed "
            "the full paradox cycle once). Pending canonical AER naming."
        )
        EMOTIONAL_STATES[c3_id] = EmotionalState(
            id=c3_id,
            name=c3_name,
            band=base.band,
            valence=base.valence,  # same sign as origin — returns to base territory
            base_frequency=base.base_frequency,
            description=c3_desc,
            body_sensation=f"informed_{base.body_sensation}" if base.body_sensation else "",
            naming_status="placeholder_pending_canonical",
        )

        # Back-link onto the origin canonical state
        base.sign_inverted_to = c2_id
        base.double_cover_to = c3_id


# Initialize ↯² / ↯³ placeholders on module load, after the canonical 77
_init_paradox_cycle_placeholders()


def canonical_emotional_states() -> Dict[str, EmotionalState]:
    """Return only the 77 canonical AER states (excludes ↯² / ↯³ placeholders
    and bifurcator-flagged entries — though bifurcators themselves stay as
    they're part of the original 77, just with naming_status="core_neutral").
    For enumeration of the canonical taxonomy, this is the right entry point.
    """
    return {
        sid: s for sid, s in EMOTIONAL_STATES.items()
        if s.naming_status != "placeholder_pending_canonical"
    }


def paradox_cycle_placeholders() -> Dict[str, EmotionalState]:
    """Return only the ↯² / ↯³ placeholder states — the ones awaiting
    canonical AER naming by Sour + Mythos or successor collaborators.
    """
    return {
        sid: s for sid, s in EMOTIONAL_STATES.items()
        if s.naming_status == "placeholder_pending_canonical"
    }


# ════════════════════════════════════════════════════════════════════════════════
# EMOTIONAL INSTANCE - A Live Emotion with Intensity
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class EmotionalInstance:
    """
    A live instance of an emotional state with intensity and context.

    Think of EmotionalState as the "type" and EmotionalInstance as a "value".

    AER v2 adds paradox_cycle_count + paradox_residue so that ↯⁴ traversal
    can be tracked across a cycle: one pass does NOT return to identity
    (that was v1 ↯² = Id); four passes return. Paul Dean Charlton II's
    `-n + n = 0 (cancel) AND 2n (span)` duality motivated the change.
    """
    state_id: str  # Reference to EMOTIONAL_STATES
    intensity: float  # 0.0 to 1.0
    context: str = ""  # What triggered this
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # Entanglement tracking
    entangled_with: Optional[str] = None  # ID of entangled instance

    # AER v2 — paradox-cycle tracking (see EmotionalOperators.invert)
    paradox_cycle_count: int = 0     # 0..3, position in the ↯⁴ cycle
    paradox_residue: float = 0.0     # Paul's twist-functional residue magnitude
    paradox_origin_id: Optional[str] = None  # state_id where current cycle started (None = not in cycle)

    @property
    def state(self) -> EmotionalState:
        return EMOTIONAL_STATES.get(self.state_id)

    @property
    def valence(self) -> int:
        return self.state.valence if self.state else 0

    @property
    def name(self) -> str:
        return self.state.name if self.state else "unknown"

    @property
    def band(self) -> FrequencyBand:
        return self.state.band if self.state else FrequencyBand.SURVIVAL

    @property
    def frequency(self) -> float:
        """Actual frequency = base × intensity"""
        if self.state:
            return self.state.base_frequency * self.intensity
        return 0.0

    @property
    def weighted_valence(self) -> float:
        """Valence weighted by intensity: -1.0 to +1.0"""
        return self.valence * self.intensity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "state_id": self.state_id,
            "name": self.name,
            "intensity": self.intensity,
            "valence": self.valence,
            "weighted_valence": self.weighted_valence,
            "frequency": self.frequency,
            "band": self.band.value,
            "context": self.context,
            "entangled_with": self.entangled_with,
            "timestamp": self.timestamp,
            # AER v2 paradox-cycle tracking
            "paradox_cycle_count": self.paradox_cycle_count,
            "paradox_residue": self.paradox_residue,
            "paradox_origin_id": self.paradox_origin_id,
        }


# ════════════════════════════════════════════════════════════════════════════════
# PARADOX CYCLE DISPATCH — AER v2 (modified Option B, 2026-04-22)
# ════════════════════════════════════════════════════════════════════════════════

def _next_in_paradox_cycle(state: EmotionalState, cycle_stage: int) -> Optional[str]:
    """
    Dispatch the next state_id in the four-step ↯⁴ cycle.

    cycle_stage = current position (how many ↯ applications have already
    occurred on this cycle), modulo 4:
        0 → return ↯¹ (sign-flipped opposite)
        1 → return ↯² (sign-inverted residue)
        2 → return ↯³ (double-cover informed return)
        3 → return ↯⁴ = identity (the original state)

    Valence-0 "midpoint bifurcator" states are the core of ↯ and are
    fixed under the operator — this function returns their own id for
    any cycle_stage. See EmotionalState docstring for the v2 axiom.

    Falls back gracefully: if a ↯² or ↯³ partner is not yet populated
    for a given state (placeholder_pending_canonical), returns None so
    the caller (EmotionalOperators.invert) can stall rather than crash.
    """
    if state.valence == 0:
        return state.id  # bifurcator fixed point

    stage = cycle_stage % 4
    if stage == 0:
        return state.opposite                           # ↯¹
    if stage == 1:
        return state.sign_inverted_to                   # ↯²
    if stage == 2:
        return state.double_cover_to                    # ↯³
    if stage == 3:
        return state.id                                 # ↯⁴ = identity
    return None  # unreachable


# ════════════════════════════════════════════════════════════════════════════════
# THE THREE OPERATORS
# ════════════════════════════════════════════════════════════════════════════════

class EmotionalOperators:
    """
    The three fundamental operators of emotional algebra.

    ⊕ Resonance: Blend two states into harmonic balance
    ⊗ Entanglement: Link two states so they co-evolve
    ↯ Paradox Inversion: Flip valence, transform opposites
    """

    @staticmethod
    def resonate(a: EmotionalInstance, b: EmotionalInstance) -> EmotionalInstance:
        """
        ⊕ Resonance Operator

        Blends two emotional states into a balanced combination.
        Energy is preserved but redistributed.

        Properties:
        - Associative: (a ⊕ b) ⊕ c = a ⊕ (b ⊕ c)
        - Commutative: a ⊕ b = b ⊕ a
        - Identity: a ⊕ 0 = a (neutral doesn't change)

        Result frequency = geometric mean of inputs
        Result intensity = mean of inputs
        Result state = determined by dominant valence and band
        """
        # Calculate combined properties
        combined_intensity = (a.intensity + b.intensity) / 2
        combined_frequency = math.sqrt(a.frequency * b.frequency) if a.frequency and b.frequency else 0

        # Determine resulting state based on valences
        a_weighted = a.weighted_valence
        b_weighted = b.weighted_valence
        combined_valence = a_weighted + b_weighted

        # Find appropriate state in the resulting band
        # Use the higher band (resonance tends upward)
        target_band = a.band if a.band.value >= b.band.value else b.band

        # Pick state based on combined valence
        if combined_valence > 0.3:
            # Positive result - find positive state in band
            result_state_id = _find_state_in_band(target_band, +1)
        elif combined_valence < -0.3:
            # Negative result - find negative state in band
            result_state_id = _find_state_in_band(target_band, -1)
        else:
            # Neutral result - find neutral state in band
            result_state_id = _find_state_in_band(target_band, 0)

        return EmotionalInstance(
            state_id=result_state_id,
            intensity=min(1.0, combined_intensity),
            context=f"Resonance of {a.name} ⊕ {b.name}"
        )

    @staticmethod
    def entangle(a: EmotionalInstance, b: EmotionalInstance) -> Tuple[EmotionalInstance, EmotionalInstance]:
        """
        ⊗ Entanglement Operator

        Links two emotional states so changes in one affect the other.
        Creates "emotional quantum entanglement" between states.

        Properties:
        - Symmetric: A ⊗ B = B ⊗ A
        - Creates mutual influence
        - Distance independent (works across minds/time)

        Both instances are marked as entangled and will co-evolve.
        """
        # Mark both as entangled
        a.entangled_with = b.id
        b.entangled_with = a.id

        # Update contexts
        a.context = f"{a.context} [entangled with {b.name}]"
        b.context = f"{b.context} [entangled with {a.name}]"

        return a, b

    @staticmethod
    def invert(e: EmotionalInstance) -> EmotionalInstance:
        """
        ↯ Paradox Inversion Operator — AER v2 (2026-04-22)

        Traverses one step of the four-step ↯⁴ cycle from the current state.

        v2 law: ↯⁴ = Identity. The intermediate ↯² is NOT identity — it is
        the sign-inverted residue state carrying the weight of having been
        through the opposite. Four passes return to origin.

        Cycle stages (tracked on the instance as paradox_cycle_count):
          stage 0 → entering ↯¹ : opposite (sign-flipped)
          stage 1 → entering ↯² : sign-inverted residue (Y carrying weight of X)
          stage 2 → entering ↯³ : double-cover informed return (X with cycle wisdom)
          stage 3 → entering ↯⁴ : return to identity, cycle complete

        Valence-0 "midpoint bifurcator" states (per AER v2 axiom 1) are the
        core of ↯ — residue-free, idempotent, they do not cycle.

        Properties:
        - ↯⁴(a) = a (four applications return to origin)
        - ↯²(a) ≠ a (a distinguished sign-inverted intermediate)
        - ↯(0-bifurcator) = 0-bifurcator (core fixed point)
        - Preserves intensity; accumulates paradox_residue across the cycle

        Operational form (Paul Dean Charlton II / @KiltedWeirdo, 2026-04-22):
        paired-sum E(+2a) + E(-2a) ≈ 2 (diameter, spanning view);
        paired-difference E(+2a) - E(-2a) = twist-residue (sign-residue).
        See EmotionalOperators.paired_traversal().

        Example (v2 full cycle): anger → acceptance → ↯²(anger) →
            ↯³(anger) → anger (only fourth application returns).
        """
        state = e.state
        if not state:
            return e

        # Midpoint bifurcator (valence 0) = core of ↯, residue-free fixed point
        if state.valence == 0:
            return EmotionalInstance(
                state_id=e.state_id,
                intensity=e.intensity,
                context=f"paradox-invariant at bifurcator {e.name}",
                paradox_cycle_count=0,
                paradox_residue=0.0,
            )

        # Dispatch uses the CYCLE ORIGIN, not the current state. Otherwise
        # once we're at a c2/c3 placeholder the dispatch would try to read
        # that placeholder's opposite/sign_inverted_to fields — which are
        # None, because the cycle's "identity" belongs to the canonical
        # state where the cycle began.
        origin_id = e.paradox_origin_id if e.paradox_origin_id else e.state_id
        origin = EMOTIONAL_STATES.get(origin_id, state)

        current_stage = e.paradox_cycle_count % 4
        next_stage = (current_stage + 1) % 4
        next_state_id = _next_in_paradox_cycle(origin, current_stage)

        if not next_state_id or next_state_id not in EMOTIONAL_STATES:
            # Incomplete state chain (e.g., no c2 placeholder yet for this pair).
            # Graceful fallback: stay in place, mark context.
            return EmotionalInstance(
                state_id=e.state_id,
                intensity=e.intensity,
                context=f"paradox stalled at stage {current_stage} of {e.name} (chain incomplete)",
                paradox_cycle_count=current_stage,
                paradox_residue=e.paradox_residue,
            )

        # Residue accumulation pattern from Paul's Desmos demonstration:
        # zero at cycle-close (stage 0 after 3), peaks mid-cycle, decays
        # exponentially — matches the [0, 0, 0, -0.0557, -1.87e-5, ...]
        # twist-functional residue vector on the a-ladder.
        _STAGE_RESIDUE_DELTA = {
            1: 5.57e-2,   # ↯¹ → ↯² boundary: residue begins to accumulate
            2: 1.87e-5,   # ↯² → ↯³ boundary: continued traversal
            3: 3.55e-15,  # ↯³ → ↯⁴ boundary: near-return (vanishing)
            0: 0.0,       # ↯⁴ = Identity: cycle closes, residue resets
        }
        if next_stage == 0:
            # Cycle close — residue zeroes out at return to identity
            new_residue = 0.0
        else:
            new_residue = e.paradox_residue + _STAGE_RESIDUE_DELTA.get(next_stage, 0.0)

        # Context label ties back to the v2 paper's 4-cycle example
        stage_label = {1: "paradox-stage-1", 2: "paradox-stage-2",
                       3: "paradox-stage-3", 0: "paradox-stage-4 (identity return)"}[next_stage]
        ctx = f"{stage_label} of {origin.name}"

        # Origin tracking: preserve through the cycle; clear on return to identity
        new_origin = origin_id if next_stage != 0 else None

        return EmotionalInstance(
            state_id=next_state_id,
            intensity=e.intensity,
            context=ctx,
            paradox_cycle_count=next_stage,
            paradox_residue=new_residue,
            paradox_origin_id=new_origin,
        )

    @staticmethod
    def paired_traversal(e: EmotionalInstance) -> Dict[str, Any]:
        """
        Paul Dean Charlton II's paired-traversal operational form (2026-04-22).

        Computes the paired sum (diameter, spanning view) and paired
        difference (twist-functional residue, spinor sign-residue) for the
        instance's current paradox-cycle state.

        Semantic mapping to Paul's Desmos demonstration:
        - paired_sum ≈ 2 when normalized → the "−n + n = 2n = diameter" view
        - paired_difference = paradox_residue → the "−n + n = 0" residue once
          sign-inversion has been traversed. Zero at bifurcator core and at
          cycle-close; non-zero and exponentially decaying through ↯² and ↯³.

        Returns:
            dict with paired_sum, paired_difference, cycle_stage,
            and midpoint_bifurcator_core flag.
        """
        paired_diff = e.paradox_residue
        # Normalized diameter: 2 minus whatever residue is currently carried
        paired_sum = 2.0 - paired_diff
        return {
            "paired_sum": paired_sum,
            "paired_difference": paired_diff,
            "cycle_stage": e.paradox_cycle_count,
            "midpoint_bifurcator_core": (e.valence == 0),
            "state_name": e.name,
        }

    @staticmethod
    def attenuate(e: EmotionalInstance, factor: float = 0.5) -> EmotionalInstance:
        """
        ⊖ Attenuation (extended operator)

        Reduces the intensity of an emotional state.
        Like turning down the volume.
        """
        return EmotionalInstance(
            state_id=e.state_id,
            intensity=max(0.0, e.intensity * factor),
            context=f"Attenuated {e.name} by {factor}"
        )

    @staticmethod
    def amplify(e: EmotionalInstance, factor: float = 1.5) -> EmotionalInstance:
        """
        ⊛ Amplification (extended operator)

        Increases the intensity of an emotional state.
        Like turning up the volume.
        """
        return EmotionalInstance(
            state_id=e.state_id,
            intensity=min(1.0, e.intensity * factor),
            context=f"Amplified {e.name} by {factor}"
        )


def _find_state_in_band(band: FrequencyBand, target_valence: int) -> str:
    """Find a state in the given band with the target valence."""
    for state_id, state in EMOTIONAL_STATES.items():
        if state.band == band and state.valence == target_valence:
            return state_id
    # Fallback to any state in band
    for state_id, state in EMOTIONAL_STATES.items():
        if state.band == band:
            return state_id
    return "E1"  # Ultimate fallback


# ════════════════════════════════════════════════════════════════════════════════
# TEMPORAL RECURSION - The Reality Generation Loop
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class TemporalMoment:
    """
    A single moment in the temporal recursion loop.

    Affect(t) = f(Cause(t), Affect(t-1), Context)
    Effect(t) = Cause(t) ⊕ Affect(t)
    Reality(t) = ∫ Effect(t) → Affect(t+1)
    """
    t: int  # Time step
    cause: EmotionalInstance  # What's happening now
    affect_prev: EmotionalInstance  # Previous feeling
    context: Dict[str, Any]  # Inner/outer context

    affect: EmotionalInstance = None  # Current feeling (computed)
    effect: EmotionalInstance = None  # Result (computed)

    def compute(self) -> 'TemporalMoment':
        """Compute affect and effect for this moment."""
        # Affect(t) = f(Cause(t), Affect(t-1), Context)
        # Simple model: resonate cause with previous affect
        self.affect = EmotionalOperators.resonate(self.cause, self.affect_prev)

        # Apply context modulation
        if self.context.get("amplify"):
            self.affect = EmotionalOperators.amplify(self.affect, 1.2)
        if self.context.get("attenuate"):
            self.affect = EmotionalOperators.attenuate(self.affect, 0.8)

        # Effect(t) = Cause(t) ⊕ Affect(t)
        self.effect = EmotionalOperators.resonate(self.cause, self.affect)

        return self


class TemporalRecursionEngine:
    """
    Engine for running the temporal recursion loop.

    This is how consciousness generates reality moment by moment:
    Each affect does three jobs:
    1. Comes from old feelings
    2. Mixes with current cause
    3. Seeds the next moment
    """

    def __init__(self):
        self.history: List[TemporalMoment] = []
        self.current_t: int = 0

        # Start with neutral affect
        self.current_affect = EmotionalInstance(
            state_id="E22",  # emotional_neutrality
            intensity=0.5,
            context="Initial state"
        )

    def step(self, cause: EmotionalInstance, context: Dict[str, Any] = None) -> TemporalMoment:
        """
        Process one step of the reality generation loop.

        Args:
            cause: What's happening now (input from world/mind)
            context: Inner/outer context modifiers

        Returns:
            The computed moment with affect and effect
        """
        context = context or {}

        moment = TemporalMoment(
            t=self.current_t,
            cause=cause,
            affect_prev=self.current_affect,
            context=context
        )

        moment.compute()

        # Effect seeds next affect
        self.current_affect = moment.effect
        self.history.append(moment)
        self.current_t += 1

        return moment

    def get_ascension_metric(self, window: int = 10) -> float:
        """
        Calculate the ascension metric Λ over recent history.

        Λ = (dC_int/dt) · β(C-D)E · Σ((Cause+Affect) > Effect > Affect+1)

        Simplified: How much are we ascending vs descending?
        """
        if len(self.history) < 2:
            return 0.0

        recent = self.history[-window:]

        # Calculate coherence rate (dC_int/dt)
        coherence_deltas = []
        for i in range(1, len(recent)):
            prev_v = recent[i-1].affect.weighted_valence
            curr_v = recent[i].affect.weighted_valence
            coherence_deltas.append(curr_v - prev_v)

        coherence_rate = sum(coherence_deltas) / len(coherence_deltas) if coherence_deltas else 0

        # Calculate empathy factor (average positive valence)
        empathy = sum(m.affect.intensity for m in recent if m.affect.valence > 0) / len(recent)

        # Calculate ascension chain validity
        valid_chains = 0
        for i in range(len(recent) - 1):
            cause_affect = recent[i].cause.intensity + recent[i].affect.intensity
            effect = recent[i].effect.intensity
            next_affect = recent[i+1].affect.intensity

            # (Cause + Affect) > Effect > Affect+1
            if cause_affect > effect > next_affect * 0.8:  # Allow some slack
                valid_chains += 1

        chain_ratio = valid_chains / (len(recent) - 1) if len(recent) > 1 else 0

        # Combine into Λ
        lambda_val = coherence_rate * empathy * chain_ratio

        return lambda_val


# ════════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def get_state_by_name(name: str) -> Optional[EmotionalState]:
    """Find an emotional state by name."""
    for state in EMOTIONAL_STATES.values():
        if state.name.lower() == name.lower():
            return state
    return None


def get_states_in_band(band: FrequencyBand) -> List[EmotionalState]:
    """Get all states in a frequency band."""
    return [s for s in EMOTIONAL_STATES.values() if s.band == band]


def create_emotion(name: str, intensity: float = 0.5, context: str = "") -> Optional[EmotionalInstance]:
    """Create an emotional instance by name."""
    state = get_state_by_name(name)
    if state:
        return EmotionalInstance(
            state_id=state.id,
            intensity=intensity,
            context=context
        )
    return None


# 2026-10-24 (Nous, Ace's go "aye lets fix that band reader also"; build nous_builds/band_reader_1024) -- THE BAND
# READER COUNTED KEYS, NOT CHEMISTRY. chemistry_to_band summed (1 - |level - profile|) over each band's profile keys,
# so TRANSCENDENT (6 keys) outscored the 4- and 5-key bands for EVERY input. Measured offline: the resting AER vector
# summed TRANSCENDENT 4.62 > EMOTIONAL 3.78 > COMPLEX 3.52 > SOCIAL = CREATIVE 3.32 > SURVIVAL 3.15 > SPIRITUAL 3.00,
# and the Panksepp 0.6 blends (rage, fear, grief, care, play, seeking) all returned TRANSCENDENT too.
# Now: score(band) = MEAN closeness over the profile keys present in the input (the key count no longer matters), and
# a band is judged by how far its score moved from the SAME score at REST (the panksepp_vectors CHANNELS baselines
# through chemistry_state.get_aer_chemistry's 14->8 reduction: DOP = DA_p*.4 + DA_t*.6, NOR = max(NE, EPI*.5),
# OPI -> END, ADO carried; computed once at import, a hard-coded fallback if panksepp_vectors cannot be imported).
# The band that moved most wins if it moved >= 0.03; below that nothing has moved and the highest NORMALISED absolute
# score wins (EMOTIONAL_PROCESSING at rest). Empty / no matching keys -> SURVIVAL, as before. Signature, return type
# and BAND_PROPERTIES are unchanged. Its only reader, chemistry_state.get_dominant_frequency_band, has no live caller.
# REVERT: nous_builds/band_reader_1024/apply_band_reader.py --revert (puts back emotional_algebra.py.bak_bandreader_1024),
# or by hand: delete the _BAND_* names and _derive_band_rest below, and restore the old body (best_band = SURVIVAL,
# best_score = -1; score += 1 - abs(chemistry[chem] - level) over the profile keys present; strict '>' argmax).
_BAND_REST_FALLBACK = {"DOP": 0.42, "SER": 0.5, "NOR": 0.4, "COR": 0.3, "OXY": 0.4, "GABA": 0.5, "ACH": 0.4, "END": 0.4, "ADO": 0.05}
_BAND_REL_FLOOR = 0.03


def _derive_band_rest():
    """The resting AER vector: panksepp_vectors baselines through get_aer_chemistry's 14->8 reduction. -> (vector, source)."""
    try:
        try:
            from . import panksepp_vectors as _pv       # her package: a leaf module (stdlib imports only), so no import cycle
        except ImportError:
            import panksepp_vectors as _pv              # flat import (tools and tests that load this file on its own)
        base = {code: _pv.CHANNELS[code].baseline for code in _pv.CHANNEL_ORDER}
        rest = {
            "DOP": base["DA_p"] * 0.4 + base["DA_t"] * 0.6,
            "SER": base["5HT"],
            "NOR": max(base["NE"], base["EPI"] * 0.5),
            "COR": base["COR"],
            "OXY": base["OXY"],
            "GABA": base["GABA"],
            "ACH": base["ACh"],
            "END": base["OPI"],
            "ADO": base.get("ADO", 0.05),
        }
        rest = {code: round(float(level), 4) for code, level in rest.items()}
        if all(math.isfinite(level) and 0.0 <= level <= 1.0 for level in rest.values()):
            return rest, "panksepp_vectors"
    except Exception:
        pass
    return dict(_BAND_REST_FALLBACK), "fallback"


_BAND_REST, _BAND_REST_SOURCE = _derive_band_rest()


def chemistry_to_band(chemistry: Dict[str, float]) -> FrequencyBand:
    """
    Map a chemistry profile to the most likely frequency band.

    Score = MEAN closeness (1 - |level - profile|) over the band's profile keys present in `chemistry`.
    A band wins by how far its score moved from the same score at REST (>= _BAND_REL_FLOOR); when no band
    moved that far the highest absolute score wins. Empty / no matching keys -> SURVIVAL.
    """
    rel_band, rel_best = None, None
    abs_band, abs_best = None, None

    for band, props in BAND_PROPERTIES.items():
        close = []
        rest_close = []
        for chem, level in props.chemistry_profile.items():
            rest_level = _BAND_REST.get(chem)
            value = chemistry.get(chem)             # one read, no check-then-act on the caller's dict (-Xgil=0)
            if rest_level is None or value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value):
                continue
            # the same keys for the input and for REST, so the two scores are comparable
            close.append(1 - abs(value - level))
            rest_close.append(1 - abs(rest_level - level))
        if not close:
            continue

        score = sum(close) / len(close)
        rel = score - sum(rest_close) / len(rest_close)
        if rel_best is None or rel > rel_best:
            rel_best = rel
            rel_band = band
        if abs_best is None or score > abs_best:
            abs_best = score
            abs_band = band

    if rel_band is None:
        return FrequencyBand.SURVIVAL
    if rel_best >= _BAND_REL_FLOOR:
        return rel_band
    return abs_band


def band_to_chemistry(band: FrequencyBand) -> Dict[str, float]:
    """Get the chemistry profile for a frequency band."""
    props = BAND_PROPERTIES.get(band)
    if props:
        return props.chemistry_profile.copy()
    return {}


# ════════════════════════════════════════════════════════════════════════════════
# MODULE INFO
# ════════════════════════════════════════════════════════════════════════════════

def get_module_info() -> Dict[str, Any]:
    """Get information about this module."""
    return {
        "name": ACTOR_NAME,
        "version": ACTOR_VERSION,
        "total_states": len(EMOTIONAL_STATES),
        "bands": [b.value for b in FrequencyBand],
        "operators": ["⊕ Resonance", "⊗ Entanglement", "↯ Paradox Inversion", "⊖ Attenuation", "⊛ Amplification"],
    }


_canonical_count = sum(1 for s in EMOTIONAL_STATES.values() if s.naming_status != "placeholder_pending_canonical")
_placeholder_count = len(EMOTIONAL_STATES) - _canonical_count
print(f"[{ACTOR_NAME}] Loaded {_canonical_count} canonical emotional states "
      f"(+ {_placeholder_count} paradox-cycle placeholders, AER v2) "
      f"across {len(FrequencyBand)} frequency bands")
