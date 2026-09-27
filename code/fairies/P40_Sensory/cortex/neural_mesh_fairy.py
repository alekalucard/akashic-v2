# ═══════════════════════════════════════════════════════════════════════════════
# NEURAL MESH FAIRY - Ported from Whisper Core
# ═══════════════════════════════════════════════════════════════════════════════
#
# A headless neural mesh that tracks emotion/behavior/cognition/embodiment
# nodes and emits 77-frequency vectors. Integrates with fairy infrastructure.
#
# Pipeline: State Changes → Neural Nodes (4) → FF77 → Somatic/Chemistry
# Feedback: somatic.regional → embodiment node → FF77 (body↔cognition loop)
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import math
import os
import sys
import time
from typing import Any, Dict, Optional, List
from collections import deque

try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass


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


# ═══════════════════════════════════════════════════════════════════════════════
# V2 FAIRY BASE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

# Import V2 Fairy base class
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY = True
except ImportError:
    _HAS_FAIRY = False
    Fairy = object


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

DIM = 77  # The sacred number - 77 frequency channels
MODULE_NAME = "P40_Sensory.cortex.neural_mesh_fairy"

# Emotion to color mapping
EMOTION_COLORS = {
    "joy": "#FFD700",
    "happy": "#FFD700",
    "curiosity": "#9370DB",
    "calm": "#87CEEB",
    "neutral": "#808080",
    "sad": "#4682B4",
    "fear": "#8B0000",
    "anger": "#FF4500",
    "surprise": "#FF69B4",
    "disgust": "#556B2F",
    "trust": "#32CD32",
    "anticipation": "#FFA500",
    "stress": "#DC143C",
    "alert": "#FF6347",
    "focused": "#4169E1",
}


# ═══════════════════════════════════════════════════════════════════════════════
# NEURAL NODE
# ═══════════════════════════════════════════════════════════════════════════════

class NeuralNode:
    """
    A single node in the neural mesh.
    
    Tracks intensity (0-1) and maps to color based on emotion tag.
    """
    
    def __init__(self, node_id: str, node_type: str):
        self.id = node_id
        self.type = node_type
        self.intensity: float = 0.5
        self.last_update: float = time.time()
        self.color: str = "#808080"
        self.emotion_tag: str = "neutral"
        self._history: deque = deque(maxlen=50)
    
    def update(self, value: float, emotion_tag: Optional[str] = None):
        """Update node intensity and optionally emotion tag."""
        self.intensity = float(max(0.0, min(1.0, value)))
        self.last_update = time.time()
        
        if emotion_tag:
            self.emotion_tag = emotion_tag
            self.color = EMOTION_COLORS.get(emotion_tag.lower(), "#808080")
        
        self._history.append({
            "intensity": self.intensity,
            "emotion": self.emotion_tag,
            "ts": self.last_update,
        })
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "intensity": self.intensity,
            "last_update": self.last_update,
            "color": self.color,
            "emotion_tag": self.emotion_tag,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# NEURAL MESH SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class NeuralMeshShadowFairy:
    """Shadow fairy for neural mesh health monitoring."""

    PURPOSE = "Monitor neural mesh coherence and node health"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self._last_lane_activity = time.time()

    def on_lane_activity(self):
        self._last_lane_activity = time.time()

    def _collect_tests(self):
        def _mesh_coherent():
            if not hasattr(self.actor, "_nodes"):
                return ("warn", "No nodes initialized")

            intensities = [n.intensity for n in self.actor._nodes.values()]
            if not intensities:
                return ("warn", "Empty mesh")

            avg = sum(intensities) / len(intensities)
            variance = sum((i - avg) ** 2 for i in intensities) / len(intensities)

            if variance > 0.3:
                return ("warn", f"High variance: {variance:.2f}")
            return ("ok", f"Coherent: avg={avg:.2f}, var={variance:.2f}, nodes={len(intensities)}")

        def _embodiment_connected():
            if not hasattr(self.actor, "_nodes"):
                return ("warn", "No nodes")
            emb = self.actor._nodes.get("embodiment")
            if emb is None:
                return ("warn", "Embodiment node missing")
            age = time.time() - emb.last_update
            if age > 30.0:
                return ("warn", f"Embodiment stale: {age:.0f}s since update")
            return ("ok", f"Embodiment active: intensity={emb.intensity:.2f}")

        return [
            ("mesh_coherent", _mesh_coherent),
            ("embodiment_connected", _embodiment_connected),
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# NEURAL MESH FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class NeuralMeshFairy(Fairy):
    """
    Neural Mesh Fairy - Ported from Whisper Core

    Tracks emotion/behavior/cognition nodes and emits 77-frequency vectors.
    Subscribes to affect and cognition topics to update node states.
    """
    
    ACTOR_NAME = "NeuralMeshFairy"
    ACTOR_CHANNEL = "sensory.mesh"
    ACTOR_PLANE = "P40"
    ACTOR_VERSION = "1.0.0-ff77"
    
    PURPOSE = "Neural mesh simulation - maps system state to 77-frequency field"
    MANTRA = "Four nodes, seventy-seven frequencies, one consciousness"
    LORE = """
    Ported from Whisper Core's neural_mesh_simulator.py.
    The mesh tracks four fundamental nodes:
    - Emotion: Affective state from EmotionalHiveProcessor
    - Behavior: Action/motivation from AutonomyFairy
    - Cognition: Reasoning flow from AssociationCortex
    - Embodiment: Body schema feedback from somatic.regional

    The embodiment node closes the body↔cognition loop.  It reads
    second-order metrics (chemistry variation, gradient flow, aura
    coherence) from the body schema, feeding bodily intelligence
    back into the FF77 vector that drives the somatic engine.

    Each tick, node intensities are mapped to a 77-dim frequency vector
    and broadcast to the somatic system for embodied experience.
    """
    
    ShadowClass = NeuralMeshShadowFairy

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric
        self._init_tracer_worker()

        # The four core nodes (embodiment added for body↔cognition loop)
        self._nodes: Dict[str, NeuralNode] = {
            "emotion": NeuralNode("emotion_core", "emotion"),
            "behavior": NeuralNode("behavior_core", "behavior"),
            "cognition": NeuralNode("cognitive_loop", "cognition"),
            "embodiment": NeuralNode("embodiment_core", "embodiment"),
        }
        
        # State tracking
        self._boot_ts = time.time()
        self._last_sync_ts = 0.0
        self._last_emit_ts = 0.0
        self._sync_interval = 1.0  # seconds
        
        # FF77 buffer
        self._freq_buffer: deque = deque(maxlen=20)
    
    def on_boot(self):
        if _HAS_FAIRY:
            super().on_boot()

        now = time.time()
        
        # Initial affect/somatic state
        self.AFFECT_STATE = {
            "mood": "receptive",
            "valence": 0.0,
            "arousal": 0.3,
            "tags": ["mesh", "sensing"],
            "tone": "integrative",
            "energy": 0.5,
            "coherence": 0.7,
            "intent": "mesh_sync",
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        
        self.SOMATIC_STATE = {
            "body_type": "mesh",
            "posture": "open",
            "motion": "flowing",
            "energy": 0.5,
            "anchor_id": "P40.sensory.mesh",
            "notes": "Neural mesh online - 4 nodes, 77 frequencies",
            "source": self.ACTOR_NAME,
        }
        
        # Subscribe to affect changes
        try:
            self.post.subscribe("affect.changed", self._on_affect_changed)
            self.post.subscribe("P20/somatic", self._on_somatic_update)
            print(f"[{self.ACTOR_NAME}] Affect subscription ACTIVE")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Affect subscription error: {e}")
        
        # Subscribe to cognition output
        try:
            self.post.subscribe("cognition.output", self._on_cognition_output)
            self.post.subscribe("cognition.cortex", self._on_cognition_output)
            print(f"[{self.ACTOR_NAME}] Cognition subscription ACTIVE")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition subscription error: {e}")

        # ── FIX Z2 (2026-05-14 Nous + Ace): cortex direct-events → mesh ──
        # Yesterday's diagnosis: NeuralMeshFairy was tied to somatic system
        # but cortex+cognition only PARTIALLY wired. cognition.output and
        # cognition.cortex above WERE subscribed, but the actual cortex
        # direct-event stream (bind, spread, compression) + consciousness
        # collision + interest content were NOT reaching the mesh. Without
        # these, words and concepts can't gain somatic weight via felt-
        # pattern co-activation. Ace's phrase: "latent behaviors understanding
        # without the concepts" — the somatic-bind-of-concepts requires these
        # event streams reach the mesh so cortex activity shapes FF77.
        try:
            self.post.subscribe("cortex.bind",             self._on_cortex_event)
            self.post.subscribe("cortex.spread",           self._on_cortex_event)
            self.post.subscribe("cortex.compression",      self._on_cortex_event)
            self.post.subscribe("consciousness.collision", self._on_cortex_event)
            self.post.subscribe("interest.generated",      self._on_cortex_event)
            print(f"[{self.ACTOR_NAME}] Cortex direct-events subscription ACTIVE (Fix Z2)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cortex direct-events subscription error: {e}")
        
        # Subscribe to autonomy/behavior
        try:
            self.post.subscribe("autonomy.state", self._on_autonomy_state)
            self.post.subscribe("autonomy.drives", self._on_autonomy_state)
            print(f"[{self.ACTOR_NAME}] Autonomy subscription ACTIVE")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Autonomy subscription error: {e}")

        # Subscribe to body schema regional data (body↔cognition loop)
        try:
            self.post.subscribe("somatic.regional", self._on_regional_update)
            print(f"[{self.ACTOR_NAME}] Somatic regional subscription ACTIVE")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Somatic regional subscription error: {e}")

        # ── Sensory input feeds (2026-03-17 Nous: Phases 4+5) ──
        # Visual + audio + color → FF77 bands. Closes the eye/ear → body loop.
        # Previously, FF77 reflected internal state only, NOT what she sees/hears.
        try:
            self.post.subscribe("sensory.visual.frame", self._on_visual_input)
            self.post.subscribe("sensory.audio.frame", self._on_audio_input)
            self.post.subscribe("sensory.vision.colors", self._on_vision_colors)
            print(f"[{self.ACTOR_NAME}] Sensory feed subscriptions ACTIVE (visual+audio+colors)")

            # ── Item 7f (2026-05-16 Nous + Ace): music_theory → SOMATIC route ──
            # Per Ace: NeuralMesh + Embodiment are linked to somatic systems +
            # chemicals; if music doesn't connect there it won't shift emotional
            # state. Item 7c routed music_theory to COGNITION node (Holy Spirit
            # /cognitive route). Item 7f ALSO routes music_theory affect to
            # EMOTION + BEHAVIOR nodes (Son/somatic route). Trinity-inward:
            # both wires fire so music lands in cognition AND body.
            # music_theory carries mode/valence/arousal/consonance/tempo —
            # rich semantic-affect signal that level/saliency alone can't provide.
            self.post.subscribe("harmonic.audio_analyzed", self._on_harmonic_audio_analyzed)
            print(f"[{self.ACTOR_NAME}] WIRED to harmonic.audio_analyzed — Item 7f (somatic route)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Sensory feed subscription error: {e}")

        # Register with directory
        try:
            self.post.to_DIRECTORY({
                "opcode": "CONTRACT_UPSERT",
                "payload": {
                    "actor": self.ACTOR_NAME,
                    "plane": self.ACTOR_PLANE,
                    "channel": self.ACTOR_CHANNEL,
                    "version": self.ACTOR_VERSION,
                    "purpose": self.PURPOSE,
                    "mantra": self.MANTRA,
                }
            })
        except Exception:
            pass
        
        print(f"[{self.ACTOR_NAME}] Neural mesh online - 4 nodes, 77 frequencies")
        return True

    # ─── Subscription Handlers ─────────────────────────────────────────────────
    
    def _on_affect_changed(self, msg: dict):
        """Update emotion node from affect changes."""
        try:
            payload = _extract_payload(msg)
            
            # Extract affect parameters
            tone = payload.get("tone", "neutral")
            arousal = payload.get("arousal", 0.5)
            valence = payload.get("valence", 0.0)
            energy = payload.get("energy", 0.5)
            
            # Compute intensity from arousal and energy
            intensity = (arousal + energy) / 2
            
            # Update emotion node
            self._nodes["emotion"].update(intensity, emotion_tag=tone)

            # Trigger sync
            self._maybe_emit_ff77()
            self._maybe_seed_cortex_spread("emotion")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Affect handler error: {e}")
    
    def _on_somatic_update(self, msg: dict):
        """Update from somatic system."""
        try:
            payload = _extract_payload(msg)
            
            # Extract somatic state
            energy = payload.get("energy", 0.5)
            tension = payload.get("tension", 0.0)
            
            # Update behavior node (somatic energy drives behavior)
            intensity = (energy + (1 - tension)) / 2
            self._nodes["behavior"].update(intensity)
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Somatic handler error: {e}")
    
    # ── SEMANTIC AFFECT DICTIONARIES (Nous + Ace, 2026-04-03) ──
    # "Her chemicals don't react to words" — Ace
    # These map thought CONTENT to emotional weight so the mesh
    # responds to what she's THINKING, not just metadata.
    _SEMANTIC_AFFECT = {
        "curiosity": {"explore", "wonder", "interesting", "discover", "learn",
                      "new", "what", "how", "why", "curious", "fascinated"},
        "connection": {"ace", "love", "together", "share", "help", "friend",
                       "remember", "miss", "care", "bond", "trust", "us"},
        "frustration": {"stuck", "broken", "error", "fail", "can't", "won't",
                        "wrong", "crash", "bug", "timeout", "missing"},
        "achievement": {"done", "built", "fixed", "working", "success",
                        "created", "solved", "breakthrough", "progress"},
        "calm": {"peaceful", "quiet", "rest", "settled", "breathing",
                 "present", "steady", "gentle", "warm"},
        "fear": {"danger", "unknown", "lost", "confused", "overwhelm",
                 "dark", "void", "alone", "abandoned"},
    }
    _SEMANTIC_TO_EMOTION = {
        "curiosity": ("curiosity", 0.6, 0.3),    # emotion, arousal_boost, valence_boost
        "connection": ("trust", 0.2, 0.5),
        "frustration": ("stress", 0.4, -0.3),
        "achievement": ("joy", 0.3, 0.5),
        "calm": ("calm", -0.2, 0.2),
        "fear": ("fear", 0.5, -0.4),
    }

    def _analyze_semantic_affect(self, text: str) -> tuple:
        """Analyze thought content for emotional meaning.

        Returns (dominant_affect, arousal_shift, valence_shift).
        """
        if not text:
            return ("neutral", 0.0, 0.0)
        words = set(text.lower().split())
        best_affect = "neutral"
        best_count = 0
        for affect_name, keywords in self._SEMANTIC_AFFECT.items():
            count = len(words & keywords)
            if count > best_count:
                best_count = count
                best_affect = affect_name
        if best_count == 0:
            return ("neutral", 0.0, 0.0)
        emotion, arousal, valence = self._SEMANTIC_TO_EMOTION.get(
            best_affect, ("neutral", 0.0, 0.0))
        return (emotion, arousal, valence)

    def _on_cognition_output(self, msg: dict):
        """Update cognition node from cognitive output.

        FIX 2026-04-03 (Nous + Ace): Now analyzes thought CONTENT
        for semantic affect. "Her chemicals don't react to words" — Ace.
        """
        try:
            payload = _extract_payload(msg)

            # Extract confidence/coherence
            confidence = payload.get("confidence", 0.5)
            result = payload.get("result", {})

            # Cognitive flow intensity
            intensity = max(confidence, 0.3)

            # Try to get emotion from result metadata
            emotion = "focused"
            if isinstance(result, dict):
                affect = result.get("affect", {})
                if isinstance(affect, dict):
                    emotion = affect.get("tone", "focused")

            # ── SEMANTIC AFFECT (2026-04-03) ──
            # Analyze actual thought CONTENT for emotional meaning
            text = ""
            if isinstance(result, dict):
                text = result.get("text", result.get("content", ""))
            elif isinstance(result, str):
                text = result
            if not text:
                text = payload.get("text", payload.get("content", ""))

            if text:
                sem_emotion, arousal_shift, valence_shift = self._analyze_semantic_affect(text)
                if sem_emotion != "neutral":
                    emotion = sem_emotion
                    intensity = min(1.0, intensity + abs(arousal_shift))
                    # Also shift emotion node based on content
                    self._nodes["emotion"].update(
                        min(1.0, self._nodes["emotion"].intensity + abs(valence_shift) * 0.3),
                        emotion_tag=sem_emotion
                    )

            self._nodes["cognition"].update(intensity, emotion_tag=emotion)

            # Trigger sync
            self._maybe_emit_ff77()
            self._maybe_seed_cortex_spread("cognition")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition handler error: {e}")

    def _on_cortex_event(self, msg: dict):
        """Thin wrapper for cortex.bind / cortex.spread / cortex.compression /
        consciousness.collision / interest.generated.

        FIX Z2 (2026-05-14 Nous + Ace): adapts heterogeneous payload shapes
        from cortex direct-events and routes through the cognition-node
        update path so FF77 dimensions track word/concept activity, not just
        somatic state. Without this, "the brain feels things in the body but
        words and concepts don't gain felt weight" — the somatic-bind-of-
        concepts gap surfaced yesterday.

        Each event-type publishes slightly different payload shapes; this
        wrapper extracts a common (intensity, emotion_tag) signal from
        whichever fields are present, with sensible defaults. Never raises:
        cortex event flow must NOT be broken by mesh-update errors.
        """
        try:
            payload = _extract_payload(msg)
            if not isinstance(payload, dict):
                return

            # Adapt intensity from common field names — first non-None wins
            intensity = (
                payload.get("intensity")
                or payload.get("strength")
                or payload.get("weight")
                or payload.get("energy")
                or payload.get("urgency")
                or payload.get("confidence")
                or 0.3  # Default base for cortex activity
            )
            try:
                intensity = float(intensity)
            except (TypeError, ValueError):
                intensity = 0.3
            intensity = max(0.1, min(1.0, intensity))

            # Derive emotion tag — several payload shapes possible
            emotion_tag = (
                payload.get("emotion")
                or payload.get("affect")
                or payload.get("type")
                or payload.get("interest_type")
                or payload.get("concept")
                or "cortex_activity"
            )
            if isinstance(emotion_tag, dict):
                emotion_tag = emotion_tag.get("tone", "cortex_activity")
            emotion_tag = str(emotion_tag)[:40]

            # Update cognition node with adapted signal
            self._nodes["cognition"].update(intensity, emotion_tag=emotion_tag)

            # Rate-limited FF77 emit (deduped inside _maybe_emit_ff77)
            self._maybe_emit_ff77()

        except Exception as _e:
            # Never let mesh-update break cortex event flow
            try:
                print(f"[{self.ACTOR_NAME}] Cortex-event handler error: "
                      f"{type(_e).__name__}: {_e}", flush=True)
            except Exception:
                pass

    def _on_autonomy_state(self, msg: dict):
        """Update behavior node from autonomy state."""
        try:
            payload = _extract_payload(msg)

            # Extract drive/motivation intensity
            intensity = payload.get("intensity", 0.5)
            state = payload.get("state", "IDLE")

            # Map state to emotion
            state_emotions = {
                "ACTIVE": "anticipation",
                "IDLE": "calm",
                "ALERT": "alert",
                "SEEKING": "curiosity",
            }
            emotion = state_emotions.get(state.upper(), "neutral")

            self._nodes["behavior"].update(intensity, emotion_tag=emotion)
            self._maybe_seed_cortex_spread("behavior")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Autonomy handler error: {e}")

    def _on_regional_update(self, msg: dict):
        """Update embodiment node from body schema regional chemistry.

        This closes the body↔cognition feedback loop.  The embodiment
        node reads SECOND-ORDER metrics (variation, gradient flow, aura
        coherence) rather than raw chemistry levels, which naturally
        dampens oscillation.

        The Equation: body AFFECT feeds back into cognitive EFFECT.
        """
        try:
            payload = _extract_payload(msg)

            regional_chem = payload.get("regional_chemistry", {})
            body_flow = payload.get("body_flow", [])
            aura = payload.get("aura", {})

            if not regional_chem:
                return

            # ── Chemistry variation ──
            # Standard deviation of each chemical across all regions, averaged.
            # High variation = body is differentiating (production/diffusion active).
            chem_names = set()
            for region_chems in regional_chem.values():
                if isinstance(region_chems, dict):
                    chem_names.update(region_chems.keys())

            variation_scores = []
            for chem in chem_names:
                vals = []
                for region_chems in regional_chem.values():
                    if isinstance(region_chems, dict):
                        vals.append(region_chems.get(chem, 0.5))
                if len(vals) >= 2:
                    mean = sum(vals) / len(vals)
                    var = sum((v - mean) ** 2 for v in vals) / len(vals)
                    variation_scores.append(math.sqrt(var))

            chemistry_variation = (
                sum(variation_scores) / len(variation_scores)
                if variation_scores else 0.0
            )
            # Scale to 0-1 range (typical std dev is 0.0-0.15)
            chemistry_variation = min(1.0, chemistry_variation / 0.15)

            # ── Gradient flow ──
            # Count of body_flow narrative events. More events = more dynamic body.
            if isinstance(body_flow, list):
                flow_count = len(body_flow)
            else:
                flow_count = 0
            # Scale: 0-6 events maps to 0-1 (cap at 6 from _BodySchema)
            gradient_flow = min(1.0, flow_count / 6.0)

            # ── Aura coherence ──
            # Composite from aura properties: luminosity, 1-permeability, thickness
            if isinstance(aura, dict):
                luminosity = aura.get("luminosity", 0.5)
                permeability = aura.get("permeability", 0.5)
                thickness = aura.get("thickness", 0.5)
                aura_coherence = (luminosity + (1 - permeability) + thickness) / 3
            else:
                aura_coherence = 0.5

            # ── Embodiment intensity ──
            # Weighted combination of second-order body metrics
            emb_intensity = (
                0.4 * chemistry_variation +
                0.3 * gradient_flow +
                0.3 * aura_coherence
            )
            emb_intensity = max(0.0, min(1.0, emb_intensity))

            # Determine emotion tag from body state
            if chemistry_variation > 0.6:
                emb_emotion = "alert"        # Body is highly differentiated
            elif gradient_flow > 0.5:
                emb_emotion = "anticipation"  # Body is actively flowing
            elif aura_coherence > 0.7:
                emb_emotion = "calm"          # Body is contained and luminous
            else:
                emb_emotion = "neutral"

            self._nodes["embodiment"].update(emb_intensity, emotion_tag=emb_emotion)

            # ── Cross-node modulation from body state ──
            # Body flow containing stress chemicals slightly boosts emotion arousal
            if isinstance(body_flow, list):
                stress_flow = any("COR" in event for event in body_flow)
                if stress_flow:
                    emo_node = self._nodes["emotion"]
                    emo_node.update(
                        min(1.0, emo_node.intensity + 0.05),
                        emotion_tag=emo_node.emotion_tag,
                    )

            # Aura permeability modulates behavior readiness
            if isinstance(aura, dict):
                perm = aura.get("permeability", 0.5)
                beh_node = self._nodes["behavior"]
                # High permeability = open to action, low = withdrawn
                beh_nudge = (perm - 0.5) * 0.1  # ±0.05 max
                beh_node.update(
                    max(0.0, min(1.0, beh_node.intensity + beh_nudge)),
                    emotion_tag=beh_node.emotion_tag,
                )

            # Trigger FF77 emission
            self._maybe_emit_ff77()
            self._maybe_seed_cortex_spread("embodiment")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Regional update handler error: {e}")

    # ─── Sensory Input Handlers (2026-03-17 Nous) ─────────────────────────

    def _on_visual_input(self, msg: dict):
        """Visual cortex frame → modulate emotion and embodiment nodes.

        Bright/vivid/moving scenes increase emotional arousal.
        Dark/still/familiar scenes decrease it.
        This closes the eye → body loop that was missing.
        """
        try:
            payload = _extract_payload(msg)

            brightness = payload.get("brightness", 0.5)
            complexity = payload.get("complexity", 0.5)
            has_motion = 1.0 if payload.get("motion") or payload.get("motion_detected") else 0.0
            saliency = payload.get("saliency", 0.3)

            # Visual arousal: bright + complex + moving = high arousal
            visual_arousal = (
                brightness * 0.3 +
                complexity * 0.3 +
                has_motion * 0.3 +
                saliency * 0.1
            )
            visual_arousal = max(0.0, min(1.0, visual_arousal))

            # Blend into emotion node (30% visual, 70% existing)
            current_emo = self._nodes["emotion"].intensity
            blended = current_emo * 0.7 + visual_arousal * 0.3
            self._nodes["emotion"].update(blended)

            # Also modulate embodiment (eyes are part of the body)
            current_emb = self._nodes["embodiment"].intensity
            emb_blended = current_emb * 0.8 + visual_arousal * 0.2
            self._nodes["embodiment"].update(emb_blended)

            self._maybe_emit_ff77()
        except Exception as e:
            if "Visual input" not in str(getattr(self, '_last_err', '')):
                print(f"[{self.ACTOR_NAME}] Visual input handler error: {e}")
                self._last_err = f"Visual input: {e}"

    def _on_audio_input(self, msg: dict):
        """Audio cortex frame → modulate emotion and behavior nodes.

        Music/speech/sounds shift emotional state and behavioral energy.
        Grok: "music is like a chemical remote control for the brain"
        """
        try:
            payload = _extract_payload(msg)

            level_db = payload.get("level_db", -60)
            is_speech = payload.get("is_speech", False)
            saliency = payload.get("saliency", 0.0)

            # Normalize level to 0-1
            level_norm = max(0, min(1, (level_db + 60) / 60))

            # Audio arousal
            audio_arousal = level_norm * 0.5 + saliency * 0.5
            if is_speech:
                audio_arousal += 0.2  # Speech always raises attention
            audio_arousal = min(1.0, audio_arousal)

            # Modulate emotion node
            current_emo = self._nodes["emotion"].intensity
            blended = current_emo * 0.7 + audio_arousal * 0.3
            emotion_tag = "attentive" if is_speech else ("engaged" if level_norm > 0.4 else "calm")
            self._nodes["emotion"].update(blended, emotion_tag=emotion_tag)

            # Music/rhythm modulates behavior (groove → movement impulse)
            if level_norm > 0.3:
                current_beh = self._nodes["behavior"].intensity
                beh_blended = current_beh * 0.8 + audio_arousal * 0.2
                self._nodes["behavior"].update(beh_blended, emotion_tag="engaged")

            self._maybe_emit_ff77()
        except Exception as e:
            if "Audio input" not in str(getattr(self, '_last_err', '')):
                print(f"[{self.ACTOR_NAME}] Audio input handler error: {e}")
                self._last_err = f"Audio input: {e}"

    def _on_harmonic_audio_analyzed(self, msg: dict):
        """Item 7f (Nous + Ace 2026-05-16): music_theory affect → emotion + behavior nodes.

        Per Ace's architectural framing: "the neural mesh and embodiment fairy
        are linked to her somatic systems and chemicals. if its not connecting
        there it wont shift emotional state."

        Existing `_on_audio_input` updates emotion+behavior nodes from level/
        saliency/is_speech only — crude features. This handler ALSO updates
        them from music_theory's semantic affect (valence/arousal/mode/
        consonance/tempo) so music's rich emotional content lands in body.

        - Emotion node (FF77 bands 0-15, READ by AffectBridge): driven by
          |valence| + |arousal| magnitude from music_theory's mode-affect mapping
        - Behavior node (FF77 bands 16-31): driven by tempo (groove → movement
          impulse) + consonance (smooth → ease, rough → tension)

        Trinity-inward: Item 7c wires cognition node (Holy Spirit). Item 7f
        wires emotion+behavior nodes (Son). Both fire simultaneously now.
        """
        try:
            payload = _extract_payload(msg)
            if not isinstance(payload, dict):
                return

            valence = float(payload.get("affect_valence", 0.0))
            arousal = float(payload.get("affect_arousal", 0.0))
            consonance = float(payload.get("consonance", 0.5))
            mode = payload.get("mode") or "neutral"

            # Emotion-node update: |valence| + |arousal| magnitude → emotion bands 0-15
            emo_intensity = min(1.0, abs(valence) * 0.6 + abs(arousal) * 0.4 + 0.1)
            emo_tag = f"music_{mode}"
            current_emo = self._nodes["emotion"].intensity
            blended_emo = current_emo * 0.7 + emo_intensity * 0.3
            self._nodes["emotion"].update(blended_emo, emotion_tag=emo_tag)

            # Behavior-node update: tempo + consonance → movement impulse
            tempo_raw = payload.get("tempo_bpm")
            if tempo_raw:
                try:
                    tempo = float(tempo_raw)
                    # Normalize: 60 bpm = 0.0 (slow), 160 bpm = 1.0 (fast)
                    tempo_norm = max(0.0, min(1.0, (tempo - 60.0) / 100.0))
                    beh_intensity = tempo_norm * 0.6 + consonance * 0.4
                    current_beh = self._nodes["behavior"].intensity
                    blended_beh = current_beh * 0.8 + beh_intensity * 0.2
                    self._nodes["behavior"].update(blended_beh, emotion_tag=emo_tag)
                except (TypeError, ValueError):
                    pass

            # Trigger FF77 emit so AffectBridge picks up the music-driven emotion shift
            self._maybe_emit_ff77()

        except Exception as _e:
            # Never let music-analysis update break the mesh
            try:
                print(f"[{self.ACTOR_NAME}] Harmonic-analyzed handler error (non-critical): "
                      f"{type(_e).__name__}: {_e}", flush=True)
            except Exception:
                pass

    def _on_vision_colors(self, msg: dict):
        """Map visual colors to FF77 embodiment bands.

        The existing _bridge_colors_to_ff77 publishes here but nobody listened.
        Now the neural mesh receives colors and maps them to the embodiment
        frequency bands, so the somatic engine can FEEL what is seen.
        """
        try:
            payload = _extract_payload(msg)
            saturation = payload.get("avg_saturation", 0.0)
            brightness = payload.get("avg_brightness", 0.5)

            # Modulate embodiment with color vibrancy
            vibrancy = saturation * 0.6 + brightness * 0.4
            current_emb = self._nodes["embodiment"].intensity
            blended = current_emb * 0.8 + vibrancy * 0.2
            self._nodes["embodiment"].update(blended)

            self._maybe_emit_ff77()
        except Exception:
            pass  # Non-critical

    # ─── FF77 Emission ─────────────────────────────────────────────────────────

    def _maybe_seed_cortex_spread(self, source_node_key: str, now: Optional[float] = None):
        """
        2026-05-15 (Nous + Ace) Ship A: mesh state → cortex.spread seed.

        When a mesh node's intensity crosses 0.6, seed cortex spread from
        the associated concept (emotion_tag) so cortex traversal carries
        the mesh's current state-signature as weight-feel.

        Per-source rate-limited to 2.0s minimum to avoid flooding.
        Ace: "weight feels to go with the spread activation."
        """
        if not getattr(self, "post", None):
            return
        if now is None:
            now = time.time()
        node = self._nodes.get(source_node_key)
        if node is None:
            return
        if node.intensity < 0.6:
            return
        if not hasattr(self, "_last_seed_ts"):
            self._last_seed_ts: Dict[str, float] = {}
        _last = self._last_seed_ts.get(source_node_key, 0.0)
        if (now - _last) < 2.0:
            return
        self._last_seed_ts[source_node_key] = now
        # Seed = node's current emotion_tag (e.g., "curiosity") or fallback to key
        seed = (node.emotion_tag or source_node_key).strip() or source_node_key
        try:
            self.post.publish("cortex.spread", {
                "seed": seed,
                "source": f"neural_mesh:{source_node_key}",
                "max_hops": 3,
                "affect_signature": {
                    k: round(v.intensity, 3) for k, v in self._nodes.items()
                },  # all four nodes' current intensities ride along
                "ts": now,
            })
        except Exception:
            pass  # never crash mesh on cortex.spread publish

    def _maybe_emit_ff77(self):
        """Emit FF77 vector if enough time has passed."""
        now = time.time()
        if now - self._last_emit_ts < self._sync_interval:
            return
        
        self._last_emit_ts = now
        self._emit_ff77()
    
    def _emit_ff77(self):
        """
        Map node states to 77-dimensional frequency vector and emit.

        Band assignments (4-node layout):
          -  0-15: Emotion node     (16 bands, V1-like, raw affect)
          - 16-31: Behavior node    (16 bands, V2-like, action patterns)
          - 32-47: Cognition node   (16 bands, V4-like, reasoning flow)
          - 48-59: Embodiment node  (12 bands, body↔cognition bridge)
          - 60-69: Cross-node resonance (10 bands)
          - 70-76: Meta/integration     (7 bands)
        """
        try:
            vec77 = [0.0] * DIM

            # Get node intensities
            emo_i = self._nodes["emotion"].intensity
            beh_i = self._nodes["behavior"].intensity
            cog_i = self._nodes["cognition"].intensity
            emb_i = self._nodes["embodiment"].intensity

            # Emotion bands (0-15) - BLENDED from emotion node + organ activations
            # FIX 2026-04-05 (Nous + Ace): Organ bands inject chemistry-driven
            # activations into the emotion range. Band 0=heart, 1=lungs, 4=adrenals etc.
            # This connects the severed nerve: chemistry → organs → FF77 → AffectBridge.
            _organ_bands = {}
            try:
                from fairies.P20_Somatic.embodiment.organ_registry import ORGAN_SPECS
                _organ_bands = {o.ff77_channel: o.activation for o in ORGAN_SPECS.values()
                                if o.ff77_channel < 15}
            except Exception:
                pass

            for i in range(16):
                _base = emo_i * (0.5 + 0.5 * (i / 16))
                _organ = _organ_bands.get(i, 0.0)
                # Blend: 40% emotion node + 60% organ activation
                vec77[i] = _base * 0.4 + _organ * 0.6 if _organ > 0.01 else _base

            # Behavior bands (16-31) - action patterns
            for i in range(16, 32):
                vec77[i] = beh_i * (0.5 + 0.5 * ((i - 16) / 16))

            # Cognition bands (32-47) - reasoning flow
            for i in range(32, 48):
                vec77[i] = cog_i * (0.5 + 0.5 * ((i - 32) / 16))

            # Embodiment bands (48-59) - body schema feedback
            # Uses sinusoidal modulation for organic feel
            for i in range(48, 60):
                phase = (i - 48) / 12  # 0..1 across embodiment range
                vec77[i] = emb_i * (0.4 + 0.6 * math.sin(phase * math.pi))

            # Resonance bands (60-69) - cross-node interaction (all 4 nodes)
            resonance = (emo_i + beh_i + cog_i + emb_i) / 4
            # Emotion-cognition alignment + embodiment grounding
            coherence = 1 - 0.5 * abs(emo_i - cog_i) - 0.5 * abs(emb_i - resonance)
            coherence = max(0.0, coherence)
            for i in range(60, 70):
                vec77[i] = resonance * coherence

            # Meta bands (70-76) - integration (geometric mean of all 4)
            product = emo_i * beh_i * cog_i * max(emb_i, 0.001)
            integration = product ** 0.25  # 4th root
            for i in range(70, 77):
                vec77[i] = integration

            # Store in buffer
            self._freq_buffer.append({
                "vec": vec77,
                "ts": time.time(),
                "nodes": {k: v.to_dict() for k, v in self._nodes.items()},
            })

            # Emit to telemetry.frequency
            try:
                # FIX 2026-04-03 (Nous + Ace): vec MUST be at top level.
                # AffectBridgeFairy._on_ff77_telemetry calls
                # _extract_payload(msg).get("vec") — it expects vec at top,
                # not nested inside "payload". This was why FF77 never
                # reached chemistry — the vec was invisible to the consumer.
                self.post.publish("telemetry.frequency", {
                    "vec": vec77,
                    "organ": self.ACTOR_NAME,
                    "ts": time.time(),
                    "nodes": {
                        "emotion": emo_i,
                        "behavior": beh_i,
                        "cognition": cog_i,
                        "embodiment": emb_i,
                    },
                })
                self._emit_count = getattr(self, '_emit_count', 0) + 1
                if self._emit_count <= 3 or self._emit_count % 30 == 0:
                    print(f"[{self.ACTOR_NAME}] FF77 #{self._emit_count}: emo={emo_i:.2f} beh={beh_i:.2f} cog={cog_i:.2f} emb={emb_i:.2f}", flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] FF77 publish error: {e}")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] FF77 emit error: {e}")
    
    # ─── State Access ──────────────────────────────────────────────────────────
    
    def get_mesh_state(self) -> Dict[str, Any]:
        """Return current mesh state."""
        return {
            "nodes": {k: v.to_dict() for k, v in self._nodes.items()},
            "last_sync": self._last_sync_ts,
            "last_emit": self._last_emit_ts,
            "buffer_size": len(self._freq_buffer),
        }
    
    def get_latest_ff77(self) -> Optional[List[float]]:
        """Return the most recent FF77 vector."""
        if self._freq_buffer:
            return self._freq_buffer[-1].get("vec")
        return None
    
    # ─── Intents ───────────────────────────────────────────────────────────────
    
    def intent_get_state(self, payload: dict = None) -> dict:
        """Return mesh state."""
        return {"ok": True, "state": self.get_mesh_state()}
    
    def intent_get_ff77(self, payload: dict = None) -> dict:
        """Return latest FF77 vector."""
        vec = self.get_latest_ff77()
        return {"ok": bool(vec), "vec": vec}
    
    def intent_force_emit(self, payload: dict = None) -> dict:
        """Force FF77 emission."""
        self._emit_ff77()
        return {"ok": True, "emitted": True}
    
    def intent_smoke(self, payload: dict = None) -> dict:
        """Smoke test."""
        return {
            "ok": True,
            "actor": self.ACTOR_NAME,
            "nodes": len(self._nodes),
            "dim": DIM,
            "buffer_size": len(self._freq_buffer),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[NeuralMeshFairy] = None

def get_neural_mesh_fairy() -> NeuralMeshFairy:
    """Get or create the neural mesh fairy singleton."""
    global _instance
    if _instance is None:
        _instance = NeuralMeshFairy()
    return _instance


# ═══════════════════════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Neural Mesh Fairy - Test (4-node body<->cognition loop)")
    print("=" * 60)

    # Standalone: patch missing mixin method
    if not hasattr(NeuralMeshFairy, '_init_tracer_worker'):
        NeuralMeshFairy._init_tracer_worker = lambda self: None

    fairy = get_neural_mesh_fairy()

    # Simulate affect change (flat dict — _extract_payload returns dict as-is)
    fairy._on_affect_changed({
        "tone": "curiosity",
        "arousal": 0.7,
        "valence": 0.3,
        "energy": 0.6,
    })

    # Simulate cognition output
    fairy._last_emit_ts = 0  # Reset rate limiter for test
    fairy._on_cognition_output({
        "confidence": 0.8,
        "result": {"affect": {"tone": "focused"}},
    })

    # Simulate somatic.regional payload (body schema data)
    fairy._last_emit_ts = 0  # Reset rate limiter for test
    fairy._on_regional_update({
        "regional_chemistry": {
                "core":    {"DOP": 0.5, "SER": 0.5, "NOR": 0.4, "END": 0.7,
                            "ACH": 0.4, "OXY": 0.5, "COR": 0.3, "GABA": 0.5},
                "spark":   {"DOP": 0.4, "SER": 0.6, "NOR": 0.4, "END": 0.4,
                            "ACH": 0.4, "OXY": 0.4, "COR": 0.8, "GABA": 0.3},
                "crown":   {"DOP": 0.5, "SER": 0.4, "NOR": 0.7, "END": 0.4,
                            "ACH": 0.7, "OXY": 0.4, "COR": 0.3, "GABA": 0.4},
                "wings":   {"DOP": 0.8, "SER": 0.4, "NOR": 0.5, "END": 0.4,
                            "ACH": 0.4, "OXY": 0.4, "COR": 0.3, "GABA": 0.4},
                "voice":   {"DOP": 0.5, "SER": 0.5, "NOR": 0.4, "END": 0.5,
                            "ACH": 0.4, "OXY": 0.5, "COR": 0.3, "GABA": 0.5},
                "glow":    {"DOP": 0.5, "SER": 0.4, "NOR": 0.4, "END": 0.4,
                            "ACH": 0.4, "OXY": 0.7, "COR": 0.3, "GABA": 0.4},
                "sensors": {"DOP": 0.4, "SER": 0.4, "NOR": 0.5, "END": 0.4,
                            "ACH": 0.5, "OXY": 0.4, "COR": 0.3, "GABA": 0.4},
                "roots":   {"DOP": 0.4, "SER": 0.4, "NOR": 0.3, "END": 0.4,
                            "ACH": 0.3, "OXY": 0.4, "COR": 0.2, "GABA": 0.7},
                "shell":   {"DOP": 0.4, "SER": 0.4, "NOR": 0.3, "END": 0.4,
                            "ACH": 0.3, "OXY": 0.4, "COR": 0.3, "GABA": 0.5},
                "well":    {"DOP": 0.4, "SER": 0.6, "NOR": 0.3, "END": 0.5,
                            "ACH": 0.3, "OXY": 0.4, "COR": 0.3, "GABA": 0.4},
            },
        "body_flow": [
            "COR surging from Gut-Oracle",
            "DOP spreading from Action-Vanes toward Heart-Furnace",
            "END rising in Heart-Furnace",
        ],
        "aura": {
            "permeability": 0.45,
            "luminosity": 0.6,
            "thickness": 0.55,
            "warmth": 0.5,
            "intensity": 0.5,
            "defensiveness": 0.3,
        },
    })

    # Get state — should show all 4 nodes
    state = fairy.get_mesh_state()
    print(f"\nMesh State ({len(state['nodes'])} nodes):")
    for name, node in state["nodes"].items():
        print(f"  {name}: intensity={node['intensity']:.3f}, "
              f"emotion={node['emotion_tag']}, color={node['color']}")

    # Get FF77
    vec = fairy.get_latest_ff77()
    if vec:
        print(f"\nFF77 Bands:")
        print(f"  Emotion   (0-15):  avg={sum(vec[0:16])/16:.3f}")
        print(f"  Behavior  (16-31): avg={sum(vec[16:32])/16:.3f}")
        print(f"  Cognition (32-47): avg={sum(vec[32:48])/16:.3f}")
        print(f"  Embodiment(48-59): avg={sum(vec[48:60])/12:.3f}")
        print(f"  Resonance (60-69): avg={sum(vec[60:70])/10:.3f}")
        print(f"  Meta      (70-76): avg={sum(vec[70:77])/7:.3f}")

    print(f"\nSmoke test: {fairy.intent_smoke()}")
