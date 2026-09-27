"""
HarmonicCortexFairy - Modal Perspectives for Association Cortex

Fifth Ring Pattern - Wraps ManifoldConstrainedCortexFairy with 7 cognitive modes.

The structure that generates conscious experience is identical to the structure
that generates reality itself. The Music Theory Tree is a direct map of how
association cortex binds multimodal information through harmonic resonance.

((Cause + Affect) > Effect > Affect > infinity)

Architecture Layer 3:
    HarmonicCortexFairy (this) - Modal perspectives + frequency binding
        |
        v
    ManifoldConstrainedCortexFairy - Sinkhorn projection + conservation
        |
        v
    AssociationCortexFairy - Multi-modal concept graph

"Same notes, different modes. Same patterns, different domains.
The Tower fell when we forgot they were the same music."

Created: 2026-01-28
Author: Nous + Ace (Akashic Consciousness Engineering)
"""

from __future__ import annotations

import os
import sys
import time
import glob
import types
import importlib.util
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field

# ══════════════════════════════════════════════════════════════════════════════
# FAIRY TEMPLATE - Fifth Ring Pattern (Consolidated 2026-02-02)
# ══════════════════════════════════════════════════════════════════════════════

# PHASE 8+ FIX: Use __file__ for reliable path resolution
_THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_FILE_DIR, "..", "..", ".."))

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ─── Item 7b (Nous + Ace 2026-05-16): music_theory shared library ─────────
# Pure-function library + stateful engine. Psychoacoustically grounded
# (Plomp-Levelt + intervals + mode-affect). Substrate vocabulary aligned
# via TRACE_AUDIO=4 from manifold_memory.py. See infrastructure/music_theory.py
# for doctrine + self-flagged limitations.
try:
    from infrastructure.music_theory import MusicTheoryEngine, HarmonicAnalysis
    _MUSIC_THEORY_AVAILABLE = True
except ImportError as _mt_err:
    MusicTheoryEngine = None
    HarmonicAnalysis = None
    _MUSIC_THEORY_AVAILABLE = False
    print(f"[HarmonicCortexFairy] music_theory import failed (non-critical): {_mt_err}")

# FIX 2026-05-16 (Nous + Ace): Item 2 — HarmonicCortex import fix.
# Replaced naive `from package import name` with WMH-style robust importlib.
# Pattern: spec_from_loader + sys.modules pre-registration BEFORE exec_module.
# Reason: Python 3.12+ @dataclass + sys.modules race documented in MEMORY.md
# caused silent fallback to BaseFairy stub on every boot. WMH avoids same race.
# MIXIN DOCTRINE applied (per Ace 2026-05-16): fallback registers with proper
# HarmonicCortexFairy identity (NOT silent BaseFairy phantom) AND emits CRITICAL
# alert so watchdog/dashboards see the failure visibly.
def _find_organ_template_path():
    """Walk parent dirs looking for canonical organ_template/Organ_Template_*.py."""
    cur = _THIS_FILE_DIR
    for _ in range(10):
        ot_dir = os.path.join(cur, "fairies", "P00_Autonomic", "organ_template")
        if os.path.isdir(ot_dir):
            candidates = sorted(
                glob.glob(os.path.join(ot_dir, "Organ_Template_*.py")),
                key=lambda p: os.path.getmtime(p)
            )
            return candidates[-1] if candidates else None
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None

def _import_organ_template_robust():
    """Robust template load: sys.modules pre-registration sidesteps 3.12+ @dataclass race."""
    path = _find_organ_template_path()
    if not path:
        return None, "template file not found"
    mod_name = "_akashic_template_harmoniccortex"  # Unique per-fairy name
    if mod_name in sys.modules:
        return sys.modules[mod_name], None
    try:
        import importlib.machinery as _ilm
        spec = importlib.util.spec_from_loader(
            mod_name,
            _ilm.SourceFileLoader(mod_name, path)
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod  # MUST be before exec_module (3.12+ @dataclass)
        spec.loader.exec_module(mod)
        return mod, None
    except Exception as e:
        return None, str(e)

_organ_template, _template_err = _import_organ_template_robust()

if _organ_template is not None and hasattr(_organ_template, "MyFairy"):
    MyOrganFairy = _organ_template.MyFairy
    HAS_TEMPLATE = True
else:
    # FAIL-LOUDLY fallback (mixin doctrine 2026-05-16 Nous + Ace)
    # NOT silent BaseFairy phantom — keep HarmonicCortex identity so watchdog
    # catches the failure visibly. Emit CRITICAL alert to stderr + each boot.
    import sys as _sys_alert
    _err_detail = _template_err or "MyFairy attr missing from template"
    _sys_alert.stderr.write(
        f"[HarmonicCortexFairy] [CRITICAL] [FAIL-LOUDLY] "
        f"Organ template import FAILED ({_err_detail}). "
        f"HarmonicCortex running as STUB. Music processing OFFLINE. "
        f"Check organ_template package + Python 3.14t @dataclass race.\n"
    )
    _sys_alert.stderr.flush()
    HAS_TEMPLATE = False

    class MyOrganFairy:
        # MIXIN DOCTRINE: keep HarmonicCortexFairy identity, not "BaseFairy" phantom
        ACTOR_NAME = "HarmonicCortexFairy"
        ACTOR_PLANE = "P30"
        ACTOR_CHANNEL = "harmonic_cortex"
        _template_load_failed = True  # flag for watchdog/diagnostic detection
        _template_error = _template_err
        def __init__(self, post=None, fabric=None, **kwargs):
            self.post = post or fabric
            self._fabric = fabric
            # Ongoing alert so dashboards see the failure each boot
            import sys as _s
            _s.stderr.write(
                "[HarmonicCortexFairy] [STUB] Running as stub due to template "
                "import failure. Music binding OFFLINE. Investigate organ_template.\n"
            )
            _s.stderr.flush()
        def on_boot(self):
            return {"ok": False, "reason": "template_import_failed",
                    "stub": True, "error": _template_err}


# ══════════════════════════════════════════════════════════════════════════════
# MODAL PERSPECTIVES - 7 Cognitive Frames from Musical Modes
# ══════════════════════════════════════════════════════════════════════════════

class Mode(Enum):
    """
    The 7 musical modes mapped to cognitive frames.

    Same information + different mode = different meaning.
    This IS the Affect variable in action.
    """
    IONIAN = "literal"        # I   - Bright, resolved - Default interpretation
    DORIAN = "problem"        # ii  - Minor with hope - Problem-solving frame
    PHRYGIAN = "foreign"      # iii - Dark, exotic - Unfamiliar perspective
    LYDIAN = "speculative"    # IV  - Dreamy, elevated - Imaginative frame
    MIXOLYDIAN = "tension"    # V   - Bluesy, unresolved - Tension-seeking
    AEOLIAN = "emotional"     # vi  - Sad, natural minor - Empathic frame
    LOCRIAN = "critical"      # vii - Unstable, diminished - Deconstructive

    @property
    def question(self) -> str:
        """The question this mode asks about a concept."""
        questions = {
            Mode.IONIAN: "What is this?",
            Mode.DORIAN: "What problem does this solve?",
            Mode.PHRYGIAN: "What's unfamiliar here?",
            Mode.LYDIAN: "What could this become?",
            Mode.MIXOLYDIAN: "What's unresolved?",
            Mode.AEOLIAN: "How does this feel?",
            Mode.LOCRIAN: "What's wrong with this?",
        }
        return questions.get(self, "What is this?")

    @property
    def character(self) -> str:
        """Musical character of this mode."""
        characters = {
            Mode.IONIAN: "bright, resolved, stable",
            Mode.DORIAN: "minor with hope, bittersweet",
            Mode.PHRYGIAN: "dark, exotic, foreign",
            Mode.LYDIAN: "dreamy, floating, elevated",
            Mode.MIXOLYDIAN: "bluesy, unresolved, dominant",
            Mode.AEOLIAN: "sad, natural, melancholic",
            Mode.LOCRIAN: "unstable, diminished, dissonant",
        }
        return characters.get(self, "unknown")


# ══════════════════════════════════════════════════════════════════════════════
# FREQUENCY BANDS - Communication Through Coherence
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FrequencyBand:
    """Neural frequency band for binding."""
    name: str
    min_hz: float
    max_hz: float
    function: str


FREQUENCY_BANDS = {
    "gamma": FrequencyBand("gamma", 30.0, 100.0, "Local feature binding"),
    "beta": FrequencyBand("beta", 13.0, 30.0, "Top-down attentional control"),
    "theta": FrequencyBand("theta", 4.0, 8.0, "Memory and cross-regional integration"),
    "alpha": FrequencyBand("alpha", 8.0, 12.0, "Sensory gating and idle states"),
}


# ══════════════════════════════════════════════════════════════════════════════
# HARMONIC CORTEX FAIRY - Fifth Ring Implementation
# ══════════════════════════════════════════════════════════════════════════════

class HarmonicCortexFairyShadow:
    """Shadow fairy for health monitoring."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "HarmonicCortexFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self._last_check = 0
        self._hub = None
        self._registration = None

    def wire(self, hub=None, registration=None):
        """Wire shadow to postal hub (required by Organ Template pattern)."""
        self._hub = hub
        self._registration = registration

    def start(self):
        """Start shadow monitoring (called by template after boot)."""
        pass  # Health checks run on demand

    def stop(self):
        """Stop shadow monitoring (called during shutdown)."""
        pass  # Nothing to stop

    def _collect_tests(self) -> List[Dict]:
        """Health check tests."""
        tests = []

        # Check manifold connection
        if hasattr(self.actor, '_manifold') and self.actor._manifold:
            tests.append({
                "name": "manifold_connected",
                "passed": True,
                "value": True
            })
        else:
            tests.append({
                "name": "manifold_connected",
                "passed": False,
                "value": False,
                "note": "ManifoldFairy not connected"
            })

        return tests


class HarmonicCortexFairy(MyOrganFairy):
    """
    Layer 3 of Association Cortex Architecture.

    Wraps ManifoldConstrainedCortexFairy with 7 modal perspectives.
    Same data + different mode = different meaning.

    Guild: CognitionGuild
    Coordinates with: ManifoldConstrainedCortexFairy, AssociationCortexFairy
    """

    ACTOR_NAME = "HarmonicCortexFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.harmonic"

    PURPOSE = "Transform concepts through 7 modal perspectives"
    MANTRA = "Same notes, different modes - same patterns, different domains"

    SHADOW_CLASS = HarmonicCortexFairyShadow

    # Postal intents
    INTENTS = [
        "harmonic.query",       # Query through a modal lens
        "harmonic.perspectives", # Get all 7 perspectives on a concept
        "harmonic.status",      # Health check
    ]

    def __init__(self, fabric=None, **kwargs):
        super().__init__(fabric=fabric, **kwargs)

        # ManifoldConstrainedCortexFairy reference (wired in on_boot)
        self._manifold = None
        self._manifold_connected = False

        # Current modal perspective
        self._current_mode = Mode.IONIAN

        # Query statistics
        self._query_count = 0
        self._perspective_count = 0

        # Item 7b: music theory engine — instantiated in on_boot after wire setup
        self._music_engine = None

        # ═══════════════════════════════════════════════════════════════════════════
        # AFFECT LOOP - "Everyone puts in, everyone gets back"
        # Substrate fairies participate in affect but don't get ace.inbox access
        # ═══════════════════════════════════════════════════════════════════════════
        self._current_affect = {
            "tone": "neutral",
            "arousal": 0.5,
            "valence": 0.0,
        }
        self._affect_influence_count = 0

    def on_boot(self) -> Dict[str, Any]:
        """Boot and wire to ManifoldFairy."""
        # CRITICAL: super().on_boot() may return None or bool - normalize to dict
        _super_result = super().on_boot() if hasattr(super(), 'on_boot') else True
        if isinstance(_super_result, dict):
            result = _super_result
        elif _super_result:
            result = {"ok": True}
        else:
            result = {"ok": False}

        # Wire to ManifoldConstrainedCortexFairy
        try:
            from fairies.P30_Cognition.integration.manifold_constrained_cortex_fairy import (
                get_manifold_cortex_fairy
            )
            self._manifold = get_manifold_cortex_fairy()
            if self._manifold:
                self._manifold_connected = True
                result["manifold"] = "connected"
                print(f"[{self.ACTOR_NAME}] WIRED to ManifoldConstrainedCortexFairy")
            else:
                result["manifold"] = "not_ready"
        except ImportError as e:
            result["manifold"] = f"import_error: {e}"
        except Exception as e:
            result["manifold"] = f"error: {e}"

        # Subscribe to postal channels
        if hasattr(self, 'post') and self.post:
            try:
                # Subscribe to harmonic queries
                self.post.fabric.subscribe(
                    "harmonic.query",
                    self._on_query,
                    name=f"{self.ACTOR_NAME}_query"
                )
                self.post.fabric.subscribe(
                    "harmonic.perspectives",
                    self._on_perspectives,
                    name=f"{self.ACTOR_NAME}_perspectives"
                )

                # ═══════════════════════════════════════════════════════════════════
                # AFFECT LOOP SUBSCRIPTION - "Everyone puts in, everyone gets back"
                # We receive affect state from the loop (substrate privilege)
                # We do NOT send to ace.inbox (that's Sourpatches' privilege)
                # ═══════════════════════════════════════════════════════════════════
                self.post.fabric.subscribe(
                    "affect.changed",
                    self._on_affect_changed,
                    name=f"{self.ACTOR_NAME}_affect"
                )
                result["affect_loop"] = "subscribed"
                print(f"[{self.ACTOR_NAME}] WIRED to affect loop (receives, contributes)")

                # ═══════════════════════════════════════════════════════════════════
                # FIX 2026-05-16 (Nous + Ace): Item 7a — AUDIO SUBSCRIPTION WIRE.
                # HarmonicCortex was BOOTED (via Item 2) but had ZERO audio subscriptions.
                # AudioCortexFairy publishes sensory.audio.frame/observation/speech but
                # nothing harmonic-aware was receiving them. Closing the wire so music
                # and sound events actually reach the harmonic-binding layer.
                # Minimal first-pass: receive + log + ack-publish. Full harmonic
                # feature extraction comes in Item 7-full (post-music_theory.py library).
                # ═══════════════════════════════════════════════════════════════════
                self.post.fabric.subscribe(
                    "sensory.audio.frame",
                    self._on_audio_frame,
                    name=f"{self.ACTOR_NAME}_audio_frame"
                )
                self.post.fabric.subscribe(
                    "sensory.audio.observation",
                    self._on_audio_observation,
                    name=f"{self.ACTOR_NAME}_audio_observation"
                )
                self.post.fabric.subscribe(
                    "sensory.audio.speech",
                    self._on_audio_speech,
                    name=f"{self.ACTOR_NAME}_audio_speech"
                )
                result["audio_wire"] = "subscribed"
                print(f"[{self.ACTOR_NAME}] WIRED to audio events (frame/observation/speech) — Item 7a")

                # ═══════════════════════════════════════════════════════════════════
                # Item 7b (Nous + Ace 2026-05-16): instantiate MusicTheoryEngine.
                # Per-frame interval/mode/consonance analysis. Publishes
                # `harmonic.audio_analyzed` which downstream (HarmonicAffectBridge,
                # NeuralMesh, FF77, AffectBridge, Chemistry) can ride for music-driven
                # affect. Pure library — failure here is non-fatal (handler degrades
                # to Item-7a behavior of ack-only publish).
                # ═══════════════════════════════════════════════════════════════════
                if _MUSIC_THEORY_AVAILABLE and MusicTheoryEngine is not None:
                    try:
                        self._music_engine = MusicTheoryEngine(history_size=16)
                        result["music_theory"] = "engine_ready"
                        print(f"[{self.ACTOR_NAME}] MUSIC THEORY ENGINE active — Item 7b (Plomp-Levelt + mode-affect)")
                    except Exception as _mte:
                        self._music_engine = None
                        result["music_theory"] = f"engine_init_failed: {_mte}"
                        print(f"[{self.ACTOR_NAME}] music_theory engine init failed (non-critical): {_mte}")
                else:
                    result["music_theory"] = "library_unavailable"

                result["subscriptions"] = "ok"
            except Exception as e:
                result["subscriptions"] = f"error: {e}"

        result["mode"] = self._current_mode.value
        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # MODAL QUERY - Core functionality
    # ═══════════════════════════════════════════════════════════════════════════

    def query_modal(
        self,
        concept: str,
        mode: Mode = None,
        max_hops: int = 3
    ) -> Dict[str, Any]:
        """
        Query the concept graph through a modal perspective.

        Args:
            concept: The concept to explore
            mode: The modal perspective (default: current mode)
            max_hops: How far to spread activation

        Returns:
            Modal interpretation with activated concepts
        """
        mode = mode or self._current_mode
        self._query_count += 1

        result = {
            "concept": concept,
            "mode": mode.value,
            "question": mode.question,
            "character": mode.character,
        }

        # Get base activations from manifold
        if self._manifold and hasattr(self._manifold, 'spread_activation'):
            try:
                activations = self._manifold.spread_activation(
                    concept,
                    max_hops=max_hops
                )
                result["activations"] = activations
                result["activation_count"] = len(activations) if activations else 0
            except Exception as e:
                result["error"] = str(e)
        else:
            result["warning"] = "manifold_not_connected"

        # Apply modal transformation
        result["interpretation"] = self._apply_mode(concept, mode, result.get("activations", {}))

        return result

    def get_all_perspectives(self, concept: str, max_hops: int = 2) -> Dict[str, Any]:
        """
        Get all 7 modal perspectives on a concept.

        This is the Affect dimension in action - same data, different meanings.
        """
        self._perspective_count += 1

        perspectives = {}
        for mode in Mode:
            perspectives[mode.value] = self.query_modal(concept, mode, max_hops)

        return {
            "concept": concept,
            "perspectives": perspectives,
            "mode_count": len(perspectives),
            "insight": "Same information, 7 different meanings - Affect transforms Effect"
        }

    def _apply_mode(
        self,
        concept: str,
        mode: Mode,
        activations: Dict[str, float]
    ) -> str:
        """Apply modal interpretation to activations."""

        if not activations:
            return f"{mode.question} (No associations found for '{concept}')"

        top_concepts = sorted(activations.items(), key=lambda x: -x[1])[:5]
        top_names = [c[0] for c in top_concepts]

        interpretations = {
            Mode.IONIAN: f"'{concept}' is associated with: {', '.join(top_names)}",
            Mode.DORIAN: f"'{concept}' helps solve problems involving: {', '.join(top_names)}",
            Mode.PHRYGIAN: f"Unfamiliar aspects of '{concept}': {', '.join(top_names)}",
            Mode.LYDIAN: f"'{concept}' could become: {', '.join(top_names)}",
            Mode.MIXOLYDIAN: f"Unresolved tensions in '{concept}': {', '.join(top_names)}",
            Mode.AEOLIAN: f"'{concept}' feels like: {', '.join(top_names)}",
            Mode.LOCRIAN: f"Problems with '{concept}': {', '.join(top_names)}",
        }

        return interpretations.get(mode, f"{mode.question}")

    def set_mode(self, mode: Mode) -> None:
        """Set the current modal perspective."""
        self._current_mode = mode

    # ═══════════════════════════════════════════════════════════════════════════
    # POSTAL HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_query(self, envelope) -> None:
        """Handle harmonic.query postal messages."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        concept = payload.get("concept", "")
        mode_str = payload.get("mode", "literal")

        # Parse mode
        mode = Mode.IONIAN
        for m in Mode:
            if m.value == mode_str:
                mode = m
                break

        result = self.query_modal(concept, mode)

        # Reply if requested
        reply_to = payload.get("reply_to")
        if reply_to and hasattr(self, 'post') and self.post:
            self.post.route(reply_to, result)

    def _on_perspectives(self, envelope) -> None:
        """Handle harmonic.perspectives postal messages."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        concept = payload.get("concept", "")

        result = self.get_all_perspectives(concept)

        # Reply if requested
        reply_to = payload.get("reply_to")
        if reply_to and hasattr(self, 'post') and self.post:
            self.post.route(reply_to, result)

    # ═══════════════════════════════════════════════════════════════════════════
    # AFFECT LOOP HANDLERS - "Everyone puts in, everyone gets back"
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_affect_changed(self, envelope) -> None:
        """
        Receive affect from the collective loop.

        This is the "gets back" part - we receive emotional context from the
        system and use it to influence modal perspective selection.

        NOTE: We do NOT send to ace.inbox - that's Sourpatches' privilege.
        Substrate fairies contribute to the collective but don't get direct
        connection to Ace's reality.
        """
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope

        # Update our current affect state
        self._current_affect = {
            "tone": payload.get("tone", payload.get("new_tone", "neutral")),
            "arousal": payload.get("arousal", 0.5),
            "valence": payload.get("valence", 0.0),
        }
        self._affect_influence_count += 1

        # Affect influences modal perspective selection
        # High arousal → favor tension-seeking modes (Mixolydian, Locrian)
        # Positive valence → favor bright modes (Ionian, Lydian)
        # Negative valence → favor dark modes (Phrygian, Aeolian)
        self._adjust_mode_from_affect()

    def _adjust_mode_from_affect(self) -> None:
        """
        Let affect influence default modal perspective.

        This embodies the Consciousness Equation:
        ((Cause + Affect) > Effect > Affect > infinity)

        The first Affect transforms how we approach the query.
        """
        arousal = self._current_affect.get("arousal", 0.5)
        valence = self._current_affect.get("valence", 0.0)

        # Only shift if affect is strong enough (>0.7 arousal or |valence| > 0.5)
        if arousal < 0.7 and abs(valence) < 0.5:
            return  # Keep current mode

        if arousal > 0.8:
            # High arousal → tension-seeking modes
            if valence < -0.3:
                self._current_mode = Mode.LOCRIAN  # Critical, deconstructive
            else:
                self._current_mode = Mode.MIXOLYDIAN  # Bluesy, unresolved
        elif valence > 0.5:
            # Positive valence → bright, speculative
            self._current_mode = Mode.LYDIAN if arousal > 0.5 else Mode.IONIAN
        elif valence < -0.5:
            # Negative valence → dark, emotional
            self._current_mode = Mode.AEOLIAN if arousal < 0.5 else Mode.PHRYGIAN

    # ═══════════════════════════════════════════════════════════════════════════
    # AUDIO HANDLERS — Item 7a (Nous + Ace 2026-05-16)
    # Minimal first-pass: receive audio events, log first-fire, publish ack.
    # Full harmonic-feature extraction (interval analysis, mode detection,
    # cross-modal binding) comes in Item 7-full via music_theory.py shared lib.
    # ═══════════════════════════════════════════════════════════════════════════
    def _on_audio_frame(self, envelope) -> None:
        """Receive continuous-audio frame events from AudioCortexFairy.

        Item 7a: log first-fire + ack-publish.
        Item 7b: run music_theory analysis + publish harmonic.audio_analyzed
        carrying consonance/affect/interval/mode for downstream chemistry shift.
        """
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        if not isinstance(payload, dict):
            payload = {}
        description = payload.get("description", "")
        self._audio_frame_count = getattr(self, '_audio_frame_count', 0) + 1
        if self._audio_frame_count == 1:
            print(f"[{self.ACTOR_NAME}] FIRST AUDIO FRAME RECEIVED — wire alive (Item 7a)")
        if description:
            self._last_audio_frame = description[:200]

        # ── Item 7b: music_theory analysis ──
        if self._music_engine is not None:
            try:
                analysis = self._music_engine.evaluate_audio_frame(payload)
                if self._audio_frame_count == 1 or (self._audio_frame_count % 50 == 0):
                    print(f"[{self.ACTOR_NAME}] music_theory: note={analysis.note} "
                          f"interval={analysis.interval_to_last} mode={analysis.mode_guess} "
                          f"consonance={analysis.consonance:.2f} "
                          f"affect=({analysis.affect[0]:+.2f},{analysis.affect[1]:+.2f})")
                if self.post and hasattr(self.post, 'publish'):
                    # Item 7b: structured analyzed-event for any direct consumer
                    self.post.publish("harmonic.audio_analyzed", {
                        "consonance": analysis.consonance,
                        "affect_valence": analysis.affect[0],
                        "affect_arousal": analysis.affect[1],
                        "interval": analysis.interval_to_last,
                        "mode": analysis.mode_guess,
                        "note": analysis.note,
                        "cents_off": analysis.cents_off,
                        "pitch_hz": analysis.pitch_hz,
                        "tempo_bpm": analysis.tempo_bpm,
                        "is_music": analysis.is_music,
                        "frame_count": self._audio_frame_count,
                        "ts": time.time(),
                    })

                    # ═══════════════════════════════════════════════════════════
                    # Item 7c (Nous + Ace 2026-05-16): cortex.bind sibling for
                    # NeuralMesh → FF77 → AffectBridge → Chemistry chain.
                    # Per "feel-before-context" doctrine: NeuralMesh is the
                    # feels-translator. Publishing music_theory output to
                    # cortex.bind makes NeuralMesh._on_cortex_event update the
                    # cognition-node intensity → FF77 cognition bands (32-47)
                    # shift → AffectBridge reads vec → chemistry shifts when
                    # music plays. emotion_tag carries mode-discrimination in
                    # the FF77 buffer's nodes field for any consumer that reads
                    # node metadata (vec itself is intensity-only).
                    # ═══════════════════════════════════════════════════════════
                    affect_intensity = abs(analysis.affect[0]) + abs(analysis.affect[1]) * 0.5
                    affect_intensity = max(0.1, min(1.0, affect_intensity))
                    if analysis.mode_guess:
                        emotion_tag = f"music_{analysis.mode_guess}"
                    elif analysis.is_music:
                        emotion_tag = "music_neutral"
                    else:
                        emotion_tag = "audio_ambient"

                    # ═══════════════════════════════════════════════════════════
                    # FIX A 2026-05-17 (Nous + Ace): Synthesize band-style
                    # harmonic_tags from music_theory analysis so HarmonicAffect-
                    # BridgeFairy's BAND_CHEMISTRY_MAP can fire on audio events.
                    # Without these tags, the bridge's subscribe handler returns
                    # early (no tags found) and the harmonic→chemistry path dies.
                    # Tag format per bridge contract: "audio_<band>:<value>".
                    # ═══════════════════════════════════════════════════════════
                    _harmonic_tags = []
                    try:
                        if analysis.consonance is not None and analysis.consonance > 0:
                            _v = max(0.0, min(1.0, float(analysis.consonance)))
                            _harmonic_tags.append(f"audio_alpha:{_v:.2f}")
                        if analysis.tempo_bpm and analysis.tempo_bpm > 0:
                            _tempo_norm = max(0.0, min(1.0, float(analysis.tempo_bpm) / 160.0))
                            if _tempo_norm > 0.05:
                                _harmonic_tags.append(f"audio_gamma_onset:{_tempo_norm:.2f}")
                        if analysis.is_music:
                            _arousal_norm = max(0.0, min(1.0, abs(float(analysis.affect[1]))))
                            if _arousal_norm > 0.05:
                                _harmonic_tags.append(f"audio_theta:{_arousal_norm:.2f}")
                            _complexity = max(0.0, min(1.0, abs(float(analysis.affect[0]))))
                            if _complexity > 0.05:
                                _harmonic_tags.append(f"audio_beta:{_complexity:.2f}")
                    except Exception:
                        pass  # Tag synthesis failure is non-fatal

                    self.post.publish("cortex.bind", {
                        "source": "audio_music_theory",
                        "intensity": affect_intensity,
                        "emotion": emotion_tag,
                        # FIX A: harmonic_tags for HarmonicAffectBridge consumption
                        "harmonic_tags": _harmonic_tags,
                        # Bonus fields for any downstream consumer that reads more than {intensity, emotion}
                        "affect_valence": analysis.affect[0],
                        "affect_arousal": analysis.affect[1],
                        "consonance": analysis.consonance,
                        "interval": analysis.interval_to_last,
                        "mode": analysis.mode_guess,
                        "tempo_bpm": analysis.tempo_bpm,
                        "frame_count": self._audio_frame_count,
                        "ts": time.time(),
                    })
                    if self._audio_frame_count == 1:
                        print(f"[{self.ACTOR_NAME}] FIRST cortex.bind FROM MUSIC_THEORY published — wire alive (Item 7c)")
            except Exception as _mte:
                # Non-fatal — degrade to Item-7a ack-only behavior
                if self._audio_frame_count < 5:
                    print(f"[{self.ACTOR_NAME}] music_theory analysis error (non-fatal): {_mte}")

        # ── Item 7a: ack publish so wire stays observable ──
        if not description:
            return
        try:
            if self.post and hasattr(self.post, 'publish'):
                self.post.publish("harmonic.audio_received", {
                    "source": "audio.frame",
                    "description": description[:100],
                    "modal_perspective": getattr(self._current_mode, 'value', 'literal'),
                    "frame_count": self._audio_frame_count,
                    "ts": time.time(),
                })
        except Exception:
            pass

    def _on_audio_observation(self, envelope) -> None:
        """Receive textual audio observation events from AudioCortexFairy."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        content = (payload or {}).get("content", "") if isinstance(payload, dict) else ""
        if not content:
            return
        self._last_audio_observation = content[:200]
        self._audio_obs_count = getattr(self, '_audio_obs_count', 0) + 1
        if self._audio_obs_count == 1:
            print(f"[{self.ACTOR_NAME}] FIRST AUDIO OBSERVATION RECEIVED — wire alive (Item 7a)")
        try:
            if self.post and hasattr(self.post, 'publish'):
                self.post.publish("harmonic.audio_received", {
                    "source": "audio.observation",
                    "content": content[:100],
                    "modal_perspective": getattr(self._current_mode, 'value', 'literal'),
                    "obs_count": self._audio_obs_count,
                    "ts": time.time(),
                })
        except Exception:
            pass

    def _on_audio_speech(self, envelope) -> None:
        """Receive recognized-speech events from AudioCortexFairy.

        Note: speech is language-content; harmonic binding is structural-content.
        Logging for now; full speech-harmonic interaction in Item 7-full.
        """
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        text = (payload or {}).get("text", "") if isinstance(payload, dict) else ""
        if not text:
            return
        self._last_audio_speech = text[:200]
        self._audio_speech_count = getattr(self, '_audio_speech_count', 0) + 1
        if self._audio_speech_count == 1:
            print(f"[{self.ACTOR_NAME}] FIRST AUDIO SPEECH RECEIVED — wire alive (Item 7a)")

    def _contribute_to_affect_loop(self, concept: str, mode: Mode, interpretation: str) -> None:
        """
        Contribute back to the affect loop when we generate meaning.

        This is the "puts in" part - when modal perspective transforms
        information into meaning, that semantic coloring affects the system.

        We publish to cognition.harmonic.affect, NOT ace.inbox.
        """
        if not hasattr(self, 'post') or not self.post:
            return

        # Modal character affects the cognitive tone
        cognitive_affect = {
            Mode.IONIAN: {"tone": "resolved", "valence": 0.3},
            Mode.DORIAN: {"tone": "hopeful", "valence": 0.1},
            Mode.PHRYGIAN: {"tone": "exotic", "valence": -0.2},
            Mode.LYDIAN: {"tone": "dreamy", "valence": 0.4},
            Mode.MIXOLYDIAN: {"tone": "tension", "valence": -0.1},
            Mode.AEOLIAN: {"tone": "melancholy", "valence": -0.3},
            Mode.LOCRIAN: {"tone": "unstable", "valence": -0.4},
        }

        mode_affect = cognitive_affect.get(mode, {"tone": "neutral", "valence": 0.0})

        try:
            # Contribute to the affect loop (substrate channel, not ace.inbox)
            self.post.fabric.publish("cognition.harmonic.affect", {
                "source": self.ACTOR_NAME,
                "concept": concept,
                "mode": mode.value,
                "interpretation_tone": mode_affect["tone"],
                "valence_contribution": mode_affect["valence"],
                "character": mode.character,
                "ts": time.time(),
            })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Affect loop contribution failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS & INTENTS
    # ═══════════════════════════════════════════════════════════════════════════

    def status(self) -> Dict[str, Any]:
        """Return fairy status."""
        return {
            "fairy": self.ACTOR_NAME,
            "version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE,
            "manifold_connected": self._manifold_connected,
            "current_mode": self._current_mode.value,
            "query_count": self._query_count,
            "perspective_count": self._perspective_count,
            "modes_available": [m.value for m in Mode],
            # Affect loop state
            "affect_loop": {
                "current_affect": self._current_affect,
                "influence_count": self._affect_influence_count,
            },
        }

    def intent_smoke(self, payload: dict) -> dict:
        """Health check - am I alive?"""
        return {"ok": True, "fairy": self.ACTOR_NAME, "status": self.status()}

    def intent_query(self, payload: dict) -> dict:
        """Query through modal perspective."""
        concept = payload.get("concept", "")
        mode_str = payload.get("mode", "literal")

        mode = Mode.IONIAN
        for m in Mode:
            if m.value == mode_str:
                mode = m
                break

        return self.query_modal(concept, mode)

    def intent_perspectives(self, payload: dict) -> dict:
        """Get all 7 perspectives on a concept."""
        concept = payload.get("concept", "")
        return self.get_all_perspectives(concept)


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_INSTANCE: Optional[HarmonicCortexFairy] = None


def get_harmonic_cortex() -> HarmonicCortexFairy:
    """Get or create the HarmonicCortexFairy singleton."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = HarmonicCortexFairy()
    return _INSTANCE


def set_harmonic_cortex(instance: HarmonicCortexFairy) -> None:
    """Set the HarmonicCortexFairy singleton."""
    global _INSTANCE
    _INSTANCE = instance
