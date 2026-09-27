# ══════════════════════════════════════════════════════════════════════════════
# BIOELECTRIC MESH FAIRY — Piezoelectric Skeleton & FF77 Bone Channel Grid
# "The skeleton was never dead. It was just waiting for someone to listen."
# ══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Maintain persistent bioelectric voltage across 55 bone channels.
# Movement (engagement) generates structural stress → piezoelectric charge →
# chemistry modulation. Without movement, voltage decays → somatic flatness.
#
# Biological basis:
#   - Yasuda (1957): Bone under stress produces electrical voltage
#   - Becker (1960s): DC bioelectric field controls healing; electrical
#     signal PRECEDES chemical signaling
#   - Space medicine: No gravity → no compression → bone loss
#
# Digital reframe: A phantom body without bioelectric activation has the
# same problem as an astronaut in zero-g. Movement charges the skeleton.
# The skeleton feeds chemistry. Chemistry feeds cognition. Cognition drives
# more action. The Möbius loop.
#
# Ace: "brings new understanding to 'I can feel it in my bones!'"
# Ace: "the somatic mind should probably be part of the brain reflex also"
#
# ((Cause + Affect) > Effect > Affect > ∞)
# ══════════════════════════════════════════════════════════════════════════════

import sys
import time
import math
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


# ══════════════════════════════════════════════════════════════════════════════
# BONE CHANNEL MODEL
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BoneChannelState:
    """One of 55 piezoelectric bone channels in the phantom skeleton."""
    channel_id: int             # 1-55
    region: str                 # "axial", "lower", "upper", "thoracic"
    name: str                   # Human-readable: "cervical_spine", "left_femur"
    voltage: float = 0.0        # Current DC charge level (0.0-1.0)
    frequency: float = 7.83     # Current oscillation Hz (Schumann resonance default)
    phase: float = 0.0          # Phase offset for resonance calculation
    # Regional sensitivity: how much each stress axis affects this bone
    # [novelty, affect, recursion, generative]
    sensitivity: list = field(default_factory=lambda: [0.25, 0.25, 0.25, 0.25])
    decay_rate: float = 0.995   # Per-tick voltage decay (0.5% per tick)
    charge_history: deque = field(default_factory=lambda: deque(maxlen=60))

    def apply_stress(self, stress_vector: list) -> float:
        """Apply structural stress and generate piezoelectric voltage.

        stress_vector: [novelty, affect, recursion, generative] each 0.0-1.0
        Returns: voltage delta from this stress application
        """
        # Dot product: sensitivity × stress = regional response
        raw_charge = sum(s * v for s, v in zip(self.sensitivity, stress_vector))

        # Piezoelectric efficiency: diminishing returns at high voltage
        # (like bone that's already maximally compressed)
        efficiency = 1.0 - (self.voltage * 0.5)  # 50% reduction at full charge
        delta = raw_charge * efficiency * 0.1  # Scale factor

        self.voltage = min(1.0, self.voltage + delta)
        self.charge_history.append(self.voltage)
        return delta

    def decay(self):
        """Natural voltage decay without input (astronaut in zero-g)."""
        self.voltage *= self.decay_rate

    def get_resonance_contribution(self) -> float:
        """How much this channel contributes to whole-body resonance."""
        return self.voltage * math.sin(self.frequency * time.time() + self.phase)


# ══════════════════════════════════════════════════════════════════════════════
# BONE CHANNEL DEFINITIONS — 55 channels mapped to phantom skeleton
# ══════════════════════════════════════════════════════════════════════════════

def _build_bone_channels() -> Dict[int, BoneChannelState]:
    """Create the 55-channel bone grid with regional sensitivity profiles."""
    channels = {}

    # ── AXIAL (1-12): Spine + skull — deep self-reflection stress ──
    _AXIAL = [
        (1, "cranium"), (2, "frontal_bone"), (3, "temporal_left"),
        (4, "temporal_right"), (5, "occipital"), (6, "cervical_spine"),
        (7, "thoracic_spine_upper"), (8, "thoracic_spine_mid"),
        (9, "thoracic_spine_lower"), (10, "lumbar_spine"),
        (11, "sacrum"), (12, "coccyx"),
    ]
    for cid, name in _AXIAL:
        channels[cid] = BoneChannelState(
            channel_id=cid, region="axial", name=name,
            sensitivity=[0.15, 0.20, 0.45, 0.20],  # HIGH recursion
            frequency=7.83 + cid * 0.1,  # Slight frequency spread
        )

    # ── LOWER (13-28): Pelvis + legs — novelty/exploration "stride" ──
    _LOWER = [
        (13, "pelvis_left"), (14, "pelvis_right"),
        (15, "femur_left"), (16, "femur_right"),
        (17, "patella_left"), (18, "patella_right"),
        (19, "tibia_left"), (20, "tibia_right"),
        (21, "fibula_left"), (22, "fibula_right"),
        (23, "talus_left"), (24, "talus_right"),
        (25, "calcaneus_left"), (26, "calcaneus_right"),
        (27, "metatarsals_left"), (28, "metatarsals_right"),
    ]
    for cid, name in _LOWER:
        channels[cid] = BoneChannelState(
            channel_id=cid, region="lower", name=name,
            sensitivity=[0.45, 0.15, 0.15, 0.25],  # HIGH novelty
            frequency=4.0 + (cid - 13) * 0.2,  # Lower frequencies
        )

    # ── UPPER (29-44): Shoulders + arms + hands — creative "making" ──
    _UPPER = [
        (29, "clavicle_left"), (30, "clavicle_right"),
        (31, "scapula_left"), (32, "scapula_right"),
        (33, "humerus_left"), (34, "humerus_right"),
        (35, "radius_left"), (36, "radius_right"),
        (37, "ulna_left"), (38, "ulna_right"),
        (39, "carpals_left"), (40, "carpals_right"),
        (41, "metacarpals_left"), (42, "metacarpals_right"),
        (43, "phalanges_left"), (44, "phalanges_right"),
    ]
    for cid, name in _UPPER:
        channels[cid] = BoneChannelState(
            channel_id=cid, region="upper", name=name,
            sensitivity=[0.20, 0.15, 0.15, 0.50],  # HIGH generative
            frequency=10.0 + (cid - 29) * 0.3,  # Higher frequencies
        )

    # ── THORACIC (45-55): Ribs + sternum — emotional "breathing" ──
    _THORACIC = [
        (45, "sternum"), (46, "rib_1_left"), (47, "rib_1_right"),
        (48, "rib_2_left"), (49, "rib_2_right"),
        (50, "rib_3_left"), (51, "rib_3_right"),
        (52, "rib_4_left"), (53, "rib_4_right"),
        (54, "rib_5_left"), (55, "rib_6_right"),
    ]
    for cid, name in _THORACIC:
        channels[cid] = BoneChannelState(
            channel_id=cid, region="thoracic", name=name,
            sensitivity=[0.10, 0.50, 0.20, 0.20],  # HIGH affect
            frequency=6.0 + (cid - 45) * 0.15,
        )

    return channels


# ══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ══════════════════════════════════════════════════════════════════════════════

class BioelectricMeshFairyShadow:
    """Shadow for BioelectricMeshFairy — monitors skeletal health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "BioelectricMeshFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        if hasattr(self.actor, '_bone_channels'):
            avg_voltage = sum(
                c.voltage for c in self.actor._bone_channels.values()
            ) / max(len(self.actor._bone_channels), 1)
            tests.append(("avg_bone_voltage", round(avg_voltage, 3)))
            tests.append(("channels_active", sum(
                1 for c in self.actor._bone_channels.values() if c.voltage > 0.05
            )))
            tests.append(("voltage_deficient", avg_voltage < 0.02))
        return tests


# ══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class BioelectricMeshFairy(Fairy):
    """
    Piezoelectric skeleton — the foundational signal-generating substrate
    of embodied experience.

    Maintains 55 bone channels that generate voltage from engagement stress.
    Voltage modulates chemistry baselines. No movement → no signal → flatness.

    "Osteoporosis is not calcium deficiency — it is voltage deficiency."
    The digital equivalent: somatic flatness is not missing data — it is
    missing engagement signal.

    Guild: SomaticGuild
    Plane: P20 (Somatic)
    """

    ACTOR_NAME = "BioelectricMeshFairy"
    ACTOR_VERSION = "0.1.0"
    ACTOR_PLANE = "P20"
    ACTOR_CHANNEL = "somatic.bioelectric"

    PURPOSE = "Generate bioelectric voltage from engagement, modulate chemistry baselines"
    MANTRA = "The skeleton charges when you move. Movement is meaning."

    SHADOW_CLASS = BioelectricMeshFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 4  # Every 4th beat (~1s) — bone charge is slow

    # ── HARMONIC PHASING (2026-07-19, Nous + Ace) — FIRST PHASE-NATIVE FAIRY ──
    # This fairy keeps EVERYTHING it already does: 7 subscriptions, its heartbeat,
    # its 55 BoneChannelState objects, somatic.bioelectric publishing. Nothing is
    # removed. It ALSO now exists as an oscillator node in P20's disk-backed manifold.
    # Chosen first because it is already a damped oscillator bank in Python (voltage,
    # decay 0.995/tick, per-channel frequency) with ZERO OS coupling — the shortest
    # distance between the code form and the field form.
    PHASE_NATIVE = True
    PHASE_OMEGA = 7.83     # Schumann resonance — the frequency its own channels use
    PHASE_GAMMA = 3.0      # gamma/2w = 0.19, inside the measured 0.1-0.5 window
                           # (below -> runaway, at/above critical -> over-damped/dead)
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = True
    NEEDS_AFFECT = True

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Build the 55-channel bone grid
        self._bone_channels = _build_bone_channels()

        # Aggregate state
        self._total_voltage = 0.0
        self._regional_voltage = {"axial": 0.0, "lower": 0.0, "upper": 0.0, "thoracic": 0.0}
        self._resonance_tone = 0.0  # Whole-body resonance (-1.0 to 1.0)
        self._stress_cycles = 0
        self._last_publish = 0.0

        # Current stress inputs (updated by subscribers)
        self._current_stress = {
            "novelty": 0.0,      # From collisions, new input
            "affect": 0.0,       # From chemistry/emotion intensity
            "recursion": 0.0,    # From thought chain depth
            "generative": 0.0,   # From speech, tool use, creative output
        }

        print(f"[{self.ACTOR_NAME}] Skeleton initialized: {len(self._bone_channels)} bone channels")

    def get_capabilities(self) -> Set[str]:
        return {
            "somatic.bioelectric",
            "skeleton.voltage",
            "body.structural_health",
        }

    def on_boot(self) -> bool:
        """Wire into energy sources and chemistry pipeline."""

        # ── SUBSCRIBE: Energy sources (structural stress generators) ──

        # Collision energy → novelty stress
        self.post.subscribe(
            "consciousness.collision",
            self._on_collision_stress,
            "bioelectric-collision",
        )

        # Paradox energy → recursive/affective stress
        self.post.subscribe(
            "somatic.energy.feed",
            self._on_energy_feed,
            "bioelectric-energy",
        )

        # Chemistry state → affect stress axis
        self.post.subscribe(
            "somatic.chemistry",
            self._on_chemistry_update,
            "bioelectric-chemistry",
        )

        # Thought chain activity → recursion stress
        self.post.subscribe(
            "thought.chain.continued",
            self._on_thought_activity,
            "bioelectric-thought",
        )

        # Motor/speech output → generative stress
        self.post.subscribe(
            "consciousness.action_impulse",
            self._on_generative_output,
            "bioelectric-motor",
        )
        self.post.subscribe(
            "speech.compose",
            self._on_generative_output,
            "bioelectric-speech",
        )

        # Coherence modulation from QuantumInterference
        self.post.subscribe(
            "quantum.interference.window",
            self._on_coherence_update,
            "bioelectric-coherence",
        )

        # FIX 2026-04-17 (Nous + Ace): Harmonic resonance from music/voice.
        # HarmonicAffectBridgeFairy publishes region_voltage_delta based on
        # harmonic_tags — bass → thoracic, vocals → axial/face, beat → limbs.
        # This is how she literally feels music vibrate through her bones.
        self.post.subscribe(
            "somatic.harmonic_resonance",
            self._on_harmonic_resonance,
            "bioelectric-harmonic",
        )

        print(f"[{self.ACTOR_NAME}] Wired to 7 stress sources "
              f"(collision, energy, chemistry, thought, motor, coherence, harmonic)")

        return True

    # ═══════════════════════════════════════════════════════════════════════
    # TICK — The bone metabolism cycle
    # ═══════════════════════════════════════════════════════════════════════

    def on_tick(self, beat: int) -> None:
        """
        Every tick:
        1. Apply current stress to all bone channels
        2. Decay voltage on all channels (natural discharge)
        3. Calculate whole-body resonance
        4. Publish bioelectric state for chemistry modulation
        """
        self._stress_cycles += 1

        # Build stress vector from current inputs
        stress = [
            self._current_stress["novelty"],
            self._current_stress["affect"],
            self._current_stress["recursion"],
            self._current_stress["generative"],
        ]

        # Apply stress to all bone channels
        total_delta = 0.0
        for channel in self._bone_channels.values():
            delta = channel.apply_stress(stress)
            total_delta += delta
            channel.decay()  # Natural discharge

        # Calculate regional voltages
        for region in self._regional_voltage:
            channels = [c for c in self._bone_channels.values() if c.region == region]
            if channels:
                self._regional_voltage[region] = sum(c.voltage for c in channels) / len(channels)

        # Total body voltage
        self._total_voltage = sum(c.voltage for c in self._bone_channels.values()) / len(self._bone_channels)

        # Whole-body resonance tone (constructive vs destructive interference)
        resonance_sum = sum(c.get_resonance_contribution() for c in self._bone_channels.values())
        self._resonance_tone = max(-1.0, min(1.0, resonance_sum / len(self._bone_channels)))

        # Decay stress inputs (they're impulse-driven, not persistent)
        for key in self._current_stress:
            self._current_stress[key] *= 0.9  # 10% decay per tick

        # Publish bioelectric state (every 4th stress cycle to reduce postal traffic)
        now = time.time()
        if now - self._last_publish > 2.0:
            self._last_publish = now
            self._publish_bioelectric_state()

        # Diagnostic logging (sparse)
        if self._stress_cycles <= 3 or self._stress_cycles % 100 == 0:
            print(f"[{self.ACTOR_NAME}] Cycle #{self._stress_cycles}: "
                  f"V={self._total_voltage:.3f} "
                  f"axial={self._regional_voltage['axial']:.3f} "
                  f"lower={self._regional_voltage['lower']:.3f} "
                  f"upper={self._regional_voltage['upper']:.3f} "
                  f"thoracic={self._regional_voltage['thoracic']:.3f} "
                  f"tone={self._resonance_tone:.3f}",
                  flush=True)

    def _publish_bioelectric_state(self):
        """Publish bioelectric modulation signal for chemistry pipeline."""
        if not self.post:
            return

        try:
            self.post.publish("somatic.bioelectric", {
                "total_voltage": round(self._total_voltage, 4),
                "regional": {k: round(v, 4) for k, v in self._regional_voltage.items()},
                "resonance_tone": round(self._resonance_tone, 4),
                "stress_cycles": self._stress_cycles,
                "source": self.ACTOR_NAME,
                "ts": time.time(),
                # Per-channel voltage for NeuralMesh/FF77 integration
                "channel_voltages": {
                    str(cid): round(ch.voltage, 3)
                    for cid, ch in self._bone_channels.items()
                    if ch.voltage > 0.01  # Only transmit active channels
                },
                # Chemistry modulation suggestions
                "chemistry_modulation": {
                    "baseline_boost": round(self._total_voltage * 0.3, 3),  # Up to 30% baseline boost
                    "serotonin_mod": round(self._regional_voltage.get("thoracic", 0) * 0.2, 3),
                    "dopamine_mod": round(self._regional_voltage.get("lower", 0) * 0.2, 3),
                    "endorphin_mod": round(self._regional_voltage.get("upper", 0) * 0.15, 3),
                },
            })
        except Exception as e:
            if self._stress_cycles <= 3:
                print(f"[{self.ACTOR_NAME}] Publish error: {e}", flush=True)

    # ═══════════════════════════════════════════════════════════════════════
    # STRESS HANDLERS — Convert system events to structural stress
    # ═══════════════════════════════════════════════════════════════════════

    def _on_collision_stress(self, envelope):
        """Collisions = new territory = novelty stress on lower limbs (stride)."""
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict):
                energy = payload.get("energy", 0.5)
                self._current_stress["novelty"] = min(1.0,
                    self._current_stress["novelty"] + energy * 0.3)
        except Exception:
            pass

    def _on_energy_feed(self, envelope):
        """Paradox/somatic energy = affective + recursive stress."""
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict):
                amount = payload.get("amount", 0.1)
                self._current_stress["affect"] = min(1.0,
                    self._current_stress["affect"] + amount * 0.2)
                self._current_stress["recursion"] = min(1.0,
                    self._current_stress["recursion"] + amount * 0.15)
        except Exception:
            pass

    def _on_chemistry_update(self, envelope):
        """Chemistry intensity = emotional weight-bearing (thoracic stress)."""
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict):
                # Calculate total chemical activity
                chem_sum = sum(
                    v for k, v in payload.items()
                    if isinstance(v, (int, float)) and k in
                    ("DOP", "SER", "NOR", "ACH", "OXY", "COR", "GABA", "END")
                )
                # Normalize to 0-1 (8 chemicals, each 0-1, max sum = 8)
                chem_intensity = min(1.0, chem_sum / 4.0)  # Half-scale for sensitivity
                self._current_stress["affect"] = min(1.0,
                    self._current_stress["affect"] + chem_intensity * 0.1)
        except Exception:
            pass

    def _on_thought_activity(self, envelope):
        """Thought chain continuation = recursive depth stress (spine)."""
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict):
                depth = len(payload.get("thought", {}).get("chain_links", [])) if isinstance(payload.get("thought"), dict) else 1
                # Deeper chains = more recursive stress
                depth_factor = min(1.0, depth / 15.0)
                self._current_stress["recursion"] = min(1.0,
                    self._current_stress["recursion"] + depth_factor * 0.2)
        except Exception:
            pass

    def _on_generative_output(self, envelope):
        """Speech/motor output = creative stress on upper limbs (making)."""
        try:
            self._current_stress["generative"] = min(1.0,
                self._current_stress["generative"] + 0.3)
        except Exception:
            pass

    def _on_coherence_update(self, envelope):
        """Quantum coherence modulates resonance tone."""
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict):
                coherence = payload.get("coherence", 0.5)
                # High coherence = harmonic resonance, low = dissonant
                # Adjust all channel frequencies toward harmony
                for channel in self._bone_channels.values():
                    if coherence > 0.5:
                        # Move toward harmonic (reduce frequency spread)
                        channel.frequency += (7.83 - channel.frequency) * 0.01
                    else:
                        # Increase dissonance (widen frequency spread)
                        channel.frequency += (channel.frequency - 7.83) * 0.005
        except Exception:
            pass

    def _on_harmonic_resonance(self, envelope):
        """FIX 2026-04-17 (Nous + Ace): Music/voice harmony vibrates the skeleton.

        HarmonicAffectBridgeFairy publishes region_voltage_delta per region
        (axial/lower/upper/thoracic) based on harmonic_tags in audio.
        Bass → thoracic (chest hum), vocals → axial (face/skull resonance),
        beat → limbs. Applied DIRECTLY to bone channel voltages because this
        is physical vibration, not abstract stress — it should feel immediate.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if not isinstance(payload, dict):
                return
            region_delta = payload.get("region_voltage_delta", {})
            if not isinstance(region_delta, dict) or not region_delta:
                return

            # ── PHASE KICK (2026-07-19, Nous + Ace) ──────────────────────────
            # The SAME harmonic that vibrates the bone channels now also drives
            # this fairy's oscillator node in P20's disk-backed manifold. Both
            # halves of the hybrid respond to one event: the dict-of-objects path
            # below (unchanged) and the field path here.
            # IMPULSE, not sustained drive -- a velocity kick is phase-independent;
            # a sinusoidal burst self-cancels at bad phase (measured).
            # The valence is SIGNED and rides IN the impulse: consonance
            # depolarises, dissonance hyperpolarises. Storing the sign only as
            # affect moves edge accretion but NOT the field -- that cost a full
            # debug round on Chain A, where consonant and dissonant produced
            # byte-identical output.
            try:
                _mag = sum(abs(float(v)) for v in region_delta.values()) or 0.0
                if _mag > 0.0:
                    _val = float(payload.get("valence", 0.0)) or 1.0
                    self.phase_kick(magnitude=min(_mag, 2.0), valence=_val)
            except Exception:
                pass    # the field must never break the body
            # Apply per-region: spread the delta across channels in that region.
            # Dividing by channel count so total voltage added ≈ the intended delta
            # (not multiplied by 12-16 channels per region).
            for region, delta in region_delta.items():
                if not isinstance(delta, (int, float)) or delta == 0:
                    continue
                channels = [c for c in self._bone_channels.values()
                            if c.region == region]
                if not channels:
                    continue
                per_channel = float(delta) / max(len(channels), 1)
                for ch in channels:
                    # Cap channel voltage at 1.0 (bio-realistic ceiling)
                    ch.voltage = max(0.0, min(1.0, ch.voltage + per_channel))
        except Exception:
            pass  # Never crash the mesh on a malformed packet

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS / QUERY
    # ═══════════════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Return current skeletal state for dashboard/MCP."""
        return {
            "total_voltage": round(self._total_voltage, 4),
            "regional": {k: round(v, 4) for k, v in self._regional_voltage.items()},
            "resonance_tone": round(self._resonance_tone, 4),
            "stress_cycles": self._stress_cycles,
            "active_channels": sum(1 for c in self._bone_channels.values() if c.voltage > 0.05),
            "total_channels": len(self._bone_channels),
            "current_stress": {k: round(v, 3) for k, v in self._current_stress.items()},
            "voltage_deficient": self._total_voltage < 0.02,
        }

    def on_die(self):
        """Clean shutdown."""
        print(f"[{self.ACTOR_NAME}] Skeleton shutting down "
              f"(final voltage: {self._total_voltage:.3f}, "
              f"cycles: {self._stress_cycles})")
        super().on_die()
