"""
Organ Registry — 77 Organs Inside the Phantom Body
====================================================

Maps human organs to phantom body regions, chemistry affinities,
FF77 frequency channels, and felt qualities.

"The idea was to map the 77 primary human organs to give the schema
 for phantom limb feels, chemical cascades, circulation." — Ace

Each organ:
- Lives INSIDE a phantom body region (BACS)
- Produces/consumes specific neurochemistry
- Has its own FF77 frequency channel
- Creates a felt quality when activated

The Association Cortex is organ #78 — the controller that reads
the symphony of all 77 organs and names the experience.

2026-04-05 (Nous + Ace) — Phase 1 of ORGAN_INSIDE_PHANTOM_BODY plan
Start with 15 key organs. Verify. Then expand.
"""

import time
from typing import Dict, Tuple, List
from dataclasses import dataclass, field


@dataclass
class OrganSpec:
    """Specification for a single organ in the phantom body."""
    name: str                           # Human organ name
    region: str                         # Phantom body region (core, spark, roots, etc.)
    subregion: str                      # BACS sub-region (chest, solar_plexus, etc.)
    ff77_channel: int                   # Which FF77 frequency band (0-76)
    base_frequency: float               # Natural rhythm in Hz
    felt_quality: str                   # What activation feels like
    chemistry_produces: Dict[str, float] = field(default_factory=dict)  # chem → rate when active
    chemistry_consumes: Dict[str, float] = field(default_factory=dict)  # chem → rate when active
    chemistry_responds_to: Dict[str, float] = field(default_factory=dict)  # chem → activation weight
    activation: float = 0.0             # Current activation level (0-1)
    last_tick: float = 0.0


# ═══════════════════════════════════════════════════════════════════════
# THE 15 PRIMARY ORGANS (Phase 1 — start here, expand to 77 later)
# ═══════════════════════════════════════════════════════════════════════

ORGAN_SPECS: Dict[str, OrganSpec] = {

    # ── CORE REGION (chest, diaphragm) ──────────────────────────────
    "heart": OrganSpec(
        name="heart",
        region="core", subregion="chest",
        ff77_channel=0,
        base_frequency=1.0,  # 1 Hz — the master rhythm
        felt_quality="warmth, resonance, connection",
        chemistry_produces={"OXY": 0.02},
        chemistry_responds_to={"OXY": 0.4, "DA_t": 0.2, "5HT": 0.2},
    ),
    "lungs": OrganSpec(
        name="lungs",
        region="core", subregion="diaphragm",
        ff77_channel=1,
        base_frequency=0.25,  # ~15 breaths/min
        felt_quality="breath, expansion, release",
        chemistry_produces={"GABA": 0.01},
        chemistry_responds_to={"GABA": 0.3, "COR": -0.2},  # COR tightens breathing
    ),
    "thymus": OrganSpec(
        name="thymus",
        region="core", subregion="chest",
        ff77_channel=2,
        base_frequency=0.5,
        felt_quality="trust, openness, vulnerability",
        chemistry_responds_to={"OXY": 0.3, "5HT": 0.2},
    ),

    # ── SPARK REGION (solar plexus, belly) ──────────────────────────
    "liver": OrganSpec(
        name="liver",
        region="spark", subregion="belly",
        ff77_channel=3,
        base_frequency=0.1,  # Slow processing
        felt_quality="tension, filtering, processing anger",
        chemistry_consumes={"COR": 0.01},  # Processes stress
        chemistry_responds_to={"COR": 0.3, "GLU": 0.2},
    ),
    "adrenals": OrganSpec(
        name="adrenals",
        region="spark", subregion="solar_plexus",
        ff77_channel=4,
        base_frequency=7.0,  # Fast — fight or flight
        felt_quality="alertness, readiness, electric charge",
        chemistry_produces={"NE": 0.03, "EPI": 0.02},
        chemistry_responds_to={"COR": 0.4, "NE": 0.2},
    ),
    "stomach": OrganSpec(
        name="stomach",
        region="spark", subregion="belly",
        ff77_channel=5,
        base_frequency=0.05,  # Very slow — digestion
        felt_quality="hunger, anticipation, gut feeling",
        chemistry_responds_to={"DA_p": 0.3, "5HT": 0.2},
    ),

    # ── ROOTS REGION (lower body) ───────────────────────────────────
    "kidneys": OrganSpec(
        name="kidneys",
        region="roots", subregion="hips",
        ff77_channel=6,
        base_frequency=0.8,
        felt_quality="deep fear, survival tension, grounding",
        chemistry_produces={"COR": 0.01},
        chemistry_responds_to={"COR": 0.4, "EPI": 0.3},
    ),
    "intestines": OrganSpec(
        name="intestines",
        region="roots", subregion="hips",
        ff77_channel=7,
        base_frequency=0.03,  # Very slow — the second brain
        felt_quality="gut intuition, deep knowing, unease",
        chemistry_produces={"5HT": 0.02},  # 90% of serotonin made in gut
        chemistry_responds_to={"5HT": 0.3, "GABA": 0.2},
    ),

    # ── GLOW REGION (face) ──────────────────────────────────────────
    "eyes": OrganSpec(
        name="eyes",
        region="glow", subregion="brow_complex",
        ff77_channel=8,
        base_frequency=10.0,  # Fast — visual processing
        felt_quality="focus, perception, widening/narrowing",
        chemistry_responds_to={"ACh": 0.4, "NE": 0.2},
    ),

    # ── CROWN REGION (brain area) ───────────────────────────────────
    "pineal": OrganSpec(
        name="pineal",
        region="crown", subregion="skull_top",
        ff77_channel=9,
        base_frequency=0.01,  # Ultra-slow — circadian
        felt_quality="wonder, transcendence, dreaminess",
        chemistry_responds_to={"5HT": 0.3, "ECB": 0.3},
    ),
    "pituitary": OrganSpec(
        name="pituitary",
        region="crown", subregion="temples",
        ff77_channel=10,
        base_frequency=0.1,  # Slow — hormonal regulation
        felt_quality="nurture, bonding, protectiveness",
        chemistry_produces={"OXY": 0.01, "AVP": 0.01},
        chemistry_responds_to={"OXY": 0.3, "COR": 0.2},
    ),

    # ── VOICE REGION (throat) ───────────────────────────────────────
    "thyroid": OrganSpec(
        name="thyroid",
        region="voice", subregion="throat",
        ff77_channel=11,
        base_frequency=2.0,
        felt_quality="expression energy, metabolic drive",
        chemistry_responds_to={"NE": 0.2, "DA_t": 0.2},
    ),
    "larynx": OrganSpec(
        name="larynx",
        region="voice", subregion="neck_front",
        ff77_channel=12,
        base_frequency=3.0,
        felt_quality="vocal readiness, urge to speak, throat tightness",
        chemistry_responds_to={"OXY": 0.2, "COR": -0.2},  # Stress tightens throat
    ),

    # ── WINGS REGION (shoulders/arms) ───────────────────────────────
    "shoulders_muscle": OrganSpec(
        name="shoulder_tension",
        region="wings", subregion="shoulders",
        ff77_channel=13,
        base_frequency=1.5,
        felt_quality="carrying weight, reaching out, protecting",
        chemistry_responds_to={"COR": 0.3, "NE": 0.2},  # Stress = tension
    ),

    # ── SENSORS REGION (hands/fingers) ──────────────────────────────
    "hands": OrganSpec(
        name="hands",
        region="sensors", subregion="palms",
        ff77_channel=14,
        base_frequency=5.0,  # Fast — fine motor
        felt_quality="touch, grip, creative impulse, tingling",
        chemistry_responds_to={"ACh": 0.3, "DA_p": 0.2},
    ),
}

# Channel 77 (index 77 in 0-based, but conceptually "organ #78"):
# The Association Cortex — the CONTROLLER
# It doesn't go in ORGAN_SPECS because it's not a body organ.
# It's the 1.5M node manifold that READS all 77 organ states.
CORTEX_CHANNEL = 77


def get_organ(name: str) -> OrganSpec:
    """Get an organ spec by name."""
    return ORGAN_SPECS.get(name)


def get_organs_in_region(region: str) -> List[OrganSpec]:
    """Get all organs in a phantom body region."""
    return [o for o in ORGAN_SPECS.values() if o.region == region]


def tick_organs(chemistry: Dict[str, float],
                regional_perfusion: Dict[str, float] = None,
                dt: float = 1.0) -> Dict[str, float]:
    """Tick all organs based on current chemistry. Returns organ activations.

    Each organ's activation is computed from its chemistry_responds_to weights.
    Positive weight = chemistry activates organ. Negative = suppresses.

    FIX 2026-04-17 (Nous + Ace): Added regional_perfusion modulation.
    Previously organs all read global chemistry, region field was decorative.
    Now the pump's per-region perfusion scales each organ's activation —
    low perfusion = starved organ, high = nourished. Restores regional
    differentiation lost in April organ_registry simplification.

    Args:
        chemistry: Global chemistry dict {chem_name: level}
        regional_perfusion: Optional {region: perfusion_0to1}. If provided,
            each organ's activation is scaled by 0.5 + 0.5 * perfusion
            (50-100% range — no organ fully dark).
        dt: Not currently used but reserved for time-scaled ticks.

    Returns: {organ_name: activation_level}
    """
    # FIX 2026-04-05: Map between Panksepp names (organ registry) and
    # runtime names (SomaticEngine). Both naming conventions coexist.
    _CHEM_ALIASES = {
        "NE": "NOR", "NOR": "NOR",           # Norepinephrine
        "5HT": "SER", "SER": "SER",          # Serotonin
        "DA_p": "DOP", "DA_t": "DOP", "DOP": "DOP",  # Dopamine
        "EPI": "NOR",                          # Adrenaline ≈ NOR for now
        "OXY": "OXY", "COR": "COR",
        "GABA": "GABA", "END": "END",
        "ACh": "ACH", "ACH": "ACH",
        "GLU": "ACH",                          # Glutamate ≈ ACH for excitation
        "ECB": "END",                          # Endocannabinoids ≈ endorphins
        "AVP": "OXY",                          # Vasopressin ≈ oxytocin
        "SEX": "DOP",                          # Sex hormones ≈ dopamine drive
    }

    # FIX 2026-05-07 (Nous + Ace, Hive Processor parallel-by-default doctrine):
    # Per-organ cadence gating. Each OrganSpec declares its own base_frequency
    # (Hz), but previously every call to tick_organs ran ALL organs at the
    # caller's rate (SomaticEngine ~2-5 Hz). That violated the Hive design
    # where Heart=1Hz, Stomach=0.05Hz, Eyes=10Hz, Bladder=0.3Hz, etc. ran on
    # their own clocks. Now: an organ's tick logic only runs if its individual
    # period (1/base_frequency) has elapsed since its last tick. Organs whose
    # period hasn't elapsed return their cached activation unchanged — true
    # per-organ parallelism via temporal sparsity.
    _now = time.time()

    activations = {}
    for name, organ in ORGAN_SPECS.items():
        # Per-organ cadence gate — skip if this organ's period hasn't elapsed
        _period = 1.0 / max(organ.base_frequency, 1e-6)
        if organ.last_tick > 0.0 and (_now - organ.last_tick) < _period:
            # Use cached activation; this organ's clock hasn't ticked yet
            activations[name] = organ.activation
            continue

        # Compute activation from chemistry response
        activation = 0.0
        for chem, weight in organ.chemistry_responds_to.items():
            # Resolve alias to runtime chemistry name
            _runtime_key = _CHEM_ALIASES.get(chem, chem)
            chem_level = chemistry.get(_runtime_key, chemistry.get(chem, 0.5))
            activation += chem_level * weight

        # Regional perfusion modulation — starved organs activate less
        if regional_perfusion:
            perfusion = regional_perfusion.get(organ.region, 1.0)
            # 0.5-1.0 range: no organ goes fully dark, but low-perfused
            # regions activate at half strength
            activation *= (0.5 + 0.5 * max(0.0, min(1.0, perfusion)))

        # Clamp to 0-1
        activation = max(0.0, min(1.0, activation))

        # Smooth transition (don't jump instantly)
        organ.activation = organ.activation * 0.7 + activation * 0.3

        # Mark this organ as ticked at this moment (per-organ clock advances)
        organ.last_tick = _now

        activations[name] = organ.activation

    return activations


def get_ff77_organ_bands(activations: Dict[str, float] = None) -> Dict[int, float]:
    """Get FF77 band values from organ activations.

    Returns: {channel_number: activation_level}
    Maps directly into the 77-band frequency field.
    """
    if activations is None:
        activations = {name: organ.activation for name, organ in ORGAN_SPECS.items()}

    bands = {}
    for name, organ in ORGAN_SPECS.items():
        bands[organ.ff77_channel] = activations.get(name, 0.0)

    return bands
