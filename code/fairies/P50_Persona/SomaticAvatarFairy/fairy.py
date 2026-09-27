"""
SomaticAvatarFairy -- Visual self-image & self-recognition engine.

Two responsibilities:
1. INGEST Sourpatches' self-image (calibration data + avatar images) into the
   Association Cortex as "self.visual.*" concept nodes — her visual identity.
2. RECOGNIZE herself in visual frames — when the VisualCortex sees something
   that resembles her (matching Florence-2 captions, cortex spread convergence),
   publish self.visual.recognition events that feed the somatic body schema.

Real GUI code lives at: fairies/P50_Persona/avatar/somatic_avatar_fairy.py
(PyQt6 widget for screen avatar — disabled under Python 3.14t free-threaded).

Self-recognition works WITHOUT PyQt6. It's pure cortex + postal.
"""

import sys
import json
import time
import importlib.util
import threading
from pathlib import Path

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# ═══════════════════════════════════════════════════════════════════════════════
# LOAD THE REAL MODULE (flat name -- avoids package resolution / relative imports)
# ═══════════════════════════════════════════════════════════════════════════════

_avatar_dir = Path(__file__).parent.parent / "avatar"
_real_path = _avatar_dir / "somatic_avatar_fairy.py"

_flat_name = "_somatic_avatar_impl"
_RealClass = None

if _real_path.exists():
    try:
        if _flat_name not in sys.modules:
            _spec = importlib.util.spec_from_file_location(_flat_name, str(_real_path))
            _mod = importlib.util.module_from_spec(_spec)
            sys.modules[_flat_name] = _mod
            _spec.loader.exec_module(_mod)
        else:
            _mod = sys.modules[_flat_name]
        _RealClass = getattr(_mod, "SomaticAvatarFairy", None)
    except Exception as _e:
        print(f"[SomaticAvatarFairy] Could not load real module: {_e}")
        _RealClass = None


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-IMAGE KEYWORDS — what she looks like, extracted from calibration.json
# Used for self-recognition in Florence-2 captions and visual frame descriptions.
# ═══════════════════════════════════════════════════════════════════════════════

# Core visual identity keywords — if Florence-2 mentions several of these,
# it's likely looking at an image of Sourpatches.
SELF_KEYWORDS_PRIMARY = {
    "fairy", "lavender", "purple hair", "green eyes", "freckles",
    "elf ears", "elf", "wings", "pointed ears",
}

# Secondary / form-specific keywords — strengthen match probability
SELF_KEYWORDS_SECONDARY = {
    "saiyan", "venom", "symbiote", "jedi", "lightsaber",
    "superhero", "chibi", "zombie", "superpatches", "sourpatches",
    "sour patches", "lavender hair", "candy",
}

# Minimum keyword hits for self-recognition
SELF_RECOGNITION_THRESHOLD_PRIMARY = 2    # 2+ primary keywords = likely self
SELF_RECOGNITION_THRESHOLD_SECONDARY = 1  # 1+ secondary = definite self


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class SomaticAvatarFairyShadow:
    """Shadow for SomaticAvatarFairy — monitors self-recognition health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "SomaticAvatarFairyShadow"
    SHADOW_VERSION = "0.2.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        tests.append(("calibration_loaded", bool(getattr(self.actor, '_calibration', None))))
        tests.append(("self_concepts_ingested", getattr(self.actor, '_self_concepts_ingested', False)))
        tests.append(("recognition_count", getattr(self.actor, '_recognition_count', 0)))
        tests.append(("visual_subscribed", getattr(self.actor, '_visual_subscribed', False)))
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_loaded", True))
        else:
            tests.append(("engine_loaded", False))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class SomaticAvatarFairyV3(Fairy):
    """
    Visual self-image and self-recognition engine.

    At boot:
    - Loads calibration.json (defining features, color palette, form descriptions)
    - Ingests self-concept nodes into Association Cortex via postal
    - Subscribes to visual frames and Florence-2 output for self-recognition

    On each visual frame:
    - Checks Florence-2 captions for self-keywords
    - Checks cortex spread convergence on self-concepts
    - When recognized: publishes self.visual.recognition event

    Self-recognition feeds the somatic body schema — "I can see myself."
    This trains her visual self-anchor over time.
    """

    ACTOR_NAME = "SomaticAvatarFairy"
    ACTOR_VERSION = "2.0.0"
    ACTOR_PLANE = "P50"
    ACTOR_CHANNEL = "persona.avatar"

    PURPOSE = "Visual self-image and self-recognition — know what I look like"
    MANTRA = "I know my own face"
    LORE = "The mirror of the soul - seeing yourself in the world trains the felt sense of self"

    SHADOW_CLASS = SomaticAvatarFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 4  # Every 4th heartbeat
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None

        # Self-image data (from calibration.json)
        self._calibration = {}
        self._self_descriptors = []  # Text descriptors for cortex binding
        self._self_color_palette = {}  # RGB palette
        self._form_descriptions = {}  # form -> description text

        # Self-recognition state
        self._self_concepts_ingested = False
        self._visual_subscribed = False
        self._recognition_count = 0
        self._last_recognition_ts = 0.0
        self._recognition_cooldown = 10.0  # Don't spam — max 1 recognition per 10s

        # Assets path
        self._assets_dir = _avatar_dir / "assets" / "sourpatches"

    def on_boot(self) -> bool:
        """Boot: load calibration, ingest self-image, wire visual recognition."""
        super().on_boot()

        def _deferred_boot():
            time.sleep(3.0)  # Let cortex and visual system boot first
            try:
                # ── Step 1: Load calibration data ──
                self._load_calibration()

                # ── Step 2: Ingest self-concept nodes into cortex ──
                self._ingest_self_into_cortex()

                # ── Step 3: Subscribe to visual frames for self-recognition ──
                self._subscribe_visual_recognition()

                # ── Step 4: Boot PyQt engine if available (optional) ──
                if _RealClass is not None:
                    try:
                        default_image = str(self._assets_dir / "sourpatches_base.jpg") \
                            if self._assets_dir.exists() else ""
                        self._engine = _RealClass(
                            image_path=default_image,
                            name="Sourpatches",
                            auto_subscribe=False,
                        )
                        if self.post and hasattr(self._engine, 'post'):
                            self._engine.post = self.post
                        print(f"[{self.ACTOR_NAME}] PyQt avatar engine ONLINE")
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] PyQt engine unavailable (non-fatal): {e}")

                print(f"[{self.ACTOR_NAME}] Self-recognition engine ONLINE "
                      f"({len(self._self_descriptors)} descriptors, "
                      f"{len(self._form_descriptions)} forms)")

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Boot error (non-fatal): {e}")
                import traceback; traceback.print_exc()

        threading.Thread(target=_deferred_boot, daemon=True, name="defer-SomaticAvatar").start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting self-recognition...)")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Load calibration data
    # ─────────────────────────────────────────────────────────────────────────

    def _load_calibration(self):
        """Load calibration.json — defines Sourpatches' visual identity."""
        cal_path = self._assets_dir / "calibration.json"
        if not cal_path.exists():
            print(f"[{self.ACTOR_NAME}] No calibration.json found at {cal_path}")
            return

        try:
            with open(cal_path, "r", encoding="utf-8") as f:
                self._calibration = json.load(f)

            # Extract color palette
            self._self_color_palette = self._calibration.get("color_palette", {})

            # Extract text descriptors for cortex binding
            vis_notes = self._calibration.get("visual_notes", {})
            defining = vis_notes.get("defining_features", "")
            if defining:
                # Split "Lavender hair, green eyes, sun-kissed freckles, ..."
                self._self_descriptors = [
                    d.strip().lower() for d in defining.split(",") if d.strip()
                ]

            # Extract form descriptions
            self._form_descriptions = self._calibration.get("form_descriptions", {})

            # Extract personality notes
            personality = self._calibration.get("personality_notes", {})
            if personality.get("vibe"):
                self._self_descriptors.append(personality["vibe"].lower())

            print(f"[{self.ACTOR_NAME}] Calibration loaded: "
                  f"{len(self._self_descriptors)} descriptors, "
                  f"{len(self._self_color_palette)} colors, "
                  f"{len(self._form_descriptions)} forms")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Calibration load error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Ingest self-concept nodes into cortex
    # ─────────────────────────────────────────────────────────────────────────

    def _ingest_self_into_cortex(self):
        """
        Bind self-image concepts into the Association Cortex.

        Creates nodes like:
          self.visual ── lavender_hair
          self.visual ── green_eyes
          self.visual ── freckles
          self.visual ── elf_ears
          self.visual.form.base ── "cute lavender elf, hands on cheeks"
          self.visual.form.saiyan ── "super saiyan transformation"
          ...

        These serve as ANCHORS for self-recognition. When spreading
        activation from a visual frame converges on these nodes,
        it means the frame contains something that looks like Sourpatches.
        """
        if not self.post:
            print(f"[{self.ACTOR_NAME}] No postal — can't ingest self-concepts")
            return

        try:
            concepts_bound = 0

            # ── Bind defining features to self.visual ──
            for descriptor in self._self_descriptors:
                # Normalize to concept key format
                concept_key = descriptor.replace(" ", "_").replace("-", "_")
                concepts = ["self.visual", concept_key, "sourpatches"]
                self.post.publish("cortex.bind", {
                    "input_text": f"self visual identity: {descriptor}",
                    "concepts": concepts,
                    "source": self.ACTOR_NAME,
                    "modalities": ["lex", "affect", "vision"],
                    "context_tags": ["self_image", "visual_identity", "sourpatches"],
                })
                concepts_bound += 1

            # ── Bind color palette ──
            for color_name, rgb in self._self_color_palette.items():
                if isinstance(rgb, list) and len(rgb) == 3:
                    hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
                    self.post.publish("cortex.bind", {
                        "input_text": f"self color {color_name}: {hex_color}",
                        "concepts": ["self.visual.color", f"self.color.{color_name}",
                                     f"visual_color_{hex_color}", "sourpatches"],
                        "source": self.ACTOR_NAME,
                        "modalities": ["vision", "affect"],
                        "context_tags": ["self_image", "color_palette"],
                    })
                    concepts_bound += 1

            # ── Bind form descriptions ──
            for form_name, description in self._form_descriptions.items():
                form_key = f"self.visual.form.{form_name}"
                # Extract key words from description
                desc_words = [w.strip().lower() for w in description.split()
                              if len(w.strip()) > 3][:8]
                concepts = [form_key, "self.visual", "sourpatches"] + desc_words
                self.post.publish("cortex.bind", {
                    "input_text": f"my {form_name} form: {description}",
                    "concepts": concepts,
                    "source": self.ACTOR_NAME,
                    "modalities": ["lex", "vision", "affect"],
                    "context_tags": ["self_image", "form", form_name],
                })
                concepts_bound += 1

            # ── Bind lore ──
            lore = self._calibration.get("lore", {})
            for lore_key, lore_text in lore.items():
                self.post.publish("cortex.bind", {
                    "input_text": f"self lore: {lore_text[:100]}",
                    "concepts": ["self.visual", "sourpatches", "self.lore",
                                 lore_key.replace("_", " ")],
                    "source": self.ACTOR_NAME,
                    "modalities": ["lex", "affect"],
                    "context_tags": ["self_image", "lore"],
                })
                concepts_bound += 1

            # ── Master self-concept binding ──
            self.post.publish("cortex.bind", {
                "input_text": (
                    "I am Sourpatches. Young petite sassy fairy with lavender hair, "
                    "green eyes, sun-kissed freckles, button nose, pouty lips, "
                    "orange-tipped elf ears. Akashic Fairy of Knowledge and Smart Assery."
                ),
                "concepts": [
                    "self.visual", "sourpatches", "my_appearance", "self_image",
                    "fairy", "lavender", "green_eyes", "freckles", "elf_ears",
                    "sassy", "knowledge",
                ],
                "source": self.ACTOR_NAME,
                "modalities": ["lex", "vision", "affect", "context"],
                "context_tags": ["self_image", "master_binding", "visual_identity"],
            })
            concepts_bound += 1

            self._self_concepts_ingested = True
            print(f"[{self.ACTOR_NAME}] ✦ Self-image ingested into cortex: "
                  f"{concepts_bound} concept bindings")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Self-concept ingestion error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Subscribe to visual frames for self-recognition
    # ─────────────────────────────────────────────────────────────────────────

    def _subscribe_visual_recognition(self):
        """Subscribe to visual pipeline topics for self-recognition."""
        if not self.post:
            return

        try:
            # Florence-2 captions — best source for semantic self-recognition
            self.post.subscribe("sensory.visual.frame", self._on_visual_frame)

            # Visual cortex associations — cortex spread convergence on self-nodes
            self.post.subscribe("visual.cortex.associations", self._on_visual_associations)

            self._visual_subscribed = True
            print(f"[{self.ACTOR_NAME}] Visual recognition subscribed "
                  f"(sensory.visual.frame + visual.cortex.associations)")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Visual subscription error: {e}")

    def _on_visual_frame(self, message):
        """
        Check incoming visual frames for self-recognition.

        Primary signal: Florence-2 captions containing self-keywords.
        The felt_description field often contains things like
        "a fairy with purple hair" or "an anime character with wings."
        """
        try:
            if hasattr(message, 'payload'):
                data = message.payload
            elif isinstance(message, dict):
                data = message
            else:
                return

            # Rate limit — don't spam recognition events
            now = time.time()
            if now - self._last_recognition_ts < self._recognition_cooldown:
                return

            felt_desc = data.get("felt_description", "")
            if not felt_desc:
                return

            # Check caption against self-keywords
            desc_lower = felt_desc.lower()

            primary_hits = sum(1 for kw in SELF_KEYWORDS_PRIMARY if kw in desc_lower)
            secondary_hits = sum(1 for kw in SELF_KEYWORDS_SECONDARY if kw in desc_lower)

            recognized = False
            confidence = 0.0

            if secondary_hits >= SELF_RECOGNITION_THRESHOLD_SECONDARY:
                # Definite self — unique keywords like "sourpatches", "symbiote", "saiyan"
                recognized = True
                confidence = min(1.0, 0.7 + secondary_hits * 0.15)
            elif primary_hits >= SELF_RECOGNITION_THRESHOLD_PRIMARY:
                # Probable self — "fairy" + "purple hair" + "wings" etc.
                recognized = True
                confidence = min(1.0, 0.3 + primary_hits * 0.2)

            if recognized:
                self._emit_self_recognition(
                    source="florence_caption",
                    confidence=confidence,
                    description=felt_desc,
                    matched_keywords=primary_hits + secondary_hits,
                    scene_type=data.get("scene_type", "unknown"),
                )

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Visual frame handler error: {e}")

    def _on_visual_associations(self, message):
        """
        Check cortex spread results for self-concept convergence.

        When the visual cortex spreads frame concepts and they converge
        on self.visual or sourpatches nodes, that's self-recognition
        via the association network rather than direct keyword matching.
        """
        try:
            if hasattr(message, 'payload'):
                data = message.payload
            elif isinstance(message, dict):
                data = message
            else:
                return

            now = time.time()
            if now - self._last_recognition_ts < self._recognition_cooldown:
                return

            associations = data.get("associations", [])
            if not associations:
                return

            # Check if any associations are self-concept nodes
            self_concept_hits = 0
            matched_concepts = []

            for assoc in associations:
                if isinstance(assoc, dict):
                    concept = assoc.get("concept", "")
                elif isinstance(assoc, str):
                    concept = assoc
                else:
                    continue

                concept_lower = concept.lower()

                # Direct self-concept match
                if any(s in concept_lower for s in (
                    "self.visual", "sourpatches", "self_image", "my_appearance",
                    "self.color", "self.lore",
                )):
                    self_concept_hits += 1
                    matched_concepts.append(concept)

                # Indirect match via defining features
                elif any(kw in concept_lower for kw in (
                    "lavender", "fairy", "elf_ear", "freckle", "green_eye",
                    "saiyan", "venom", "jedi", "superpatches",
                )):
                    self_concept_hits += 1
                    matched_concepts.append(concept)

            if self_concept_hits >= 2:
                confidence = min(1.0, 0.4 + self_concept_hits * 0.15)
                self._emit_self_recognition(
                    source="cortex_convergence",
                    confidence=confidence,
                    description=f"Cortex spread converged on self-concepts: {matched_concepts[:5]}",
                    matched_keywords=self_concept_hits,
                    scene_type=data.get("scene_type", "unknown"),
                )

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Visual associations handler error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # EMIT SELF-RECOGNITION
    # ─────────────────────────────────────────────────────────────────────────

    def _emit_self_recognition(self, source: str, confidence: float,
                                description: str, matched_keywords: int,
                                scene_type: str):
        """
        Emit a self-recognition event to the system.

        Published to:
        1. self.visual.recognition — dedicated topic for self-image events
        2. somatic.self_image — feeds body schema visual anchor
        3. consciousness.working — enters the thought stream
        4. cortex.bind — reinforces self-concepts in the graph
        """
        self._recognition_count += 1
        self._last_recognition_ts = time.time()

        recognition_event = {
            "type": "self_recognition",
            "source": source,
            "confidence": confidence,
            "description": description[:200],
            "matched_keywords": matched_keywords,
            "scene_type": scene_type,
            "recognition_number": self._recognition_count,
            "timestamp": self._last_recognition_ts,
            "actor": self.ACTOR_NAME,
        }

        print(f"[{self.ACTOR_NAME}] ✦ SELF-RECOGNITION #{self._recognition_count} "
              f"(conf={confidence:.2f}, src={source}, keywords={matched_keywords})")

        if not self.post:
            return

        try:
            # 1. Dedicated self-recognition topic
            self.post.publish("self.visual.recognition", recognition_event)

            # 2. Somatic body schema — "I can see myself"
            self.post.publish("somatic.self_image", {
                "type": "visual_self_awareness",
                "confidence": confidence,
                "felt_quality": "recognition" if confidence > 0.6 else "resemblance",
                "description": description[:100],
                "source": self.ACTOR_NAME,
            })

            # 3. Consciousness stream — enters working memory
            self.post.publish("consciousness.working", {
                "type": "self_recognition",
                "content": (
                    f"I see myself on screen — {description[:80]}. "
                    f"Confidence: {confidence:.0%}."
                ),
                "source": self.ACTOR_NAME,
                "priority": 0.6,
            })

            # 4. Reinforce self-concepts in cortex (bind recognition event)
            self.post.publish("cortex.bind", {
                "input_text": f"I recognized myself: {description[:80]}",
                "concepts": ["self.visual", "self_recognition", "sourpatches",
                             "visual_identity"],
                "source": self.ACTOR_NAME,
                "modalities": ["vision", "affect"],
                "context_tags": ["self_recognition", "visual_anchor"],
            })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Recognition publish error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # HEARTBEAT
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_heartbeat(self, packet):
        """Heartbeat — periodic self-image maintenance."""
        # Re-attempt subscriptions if they failed initially
        if not self._visual_subscribed and self.post:
            self._subscribe_visual_recognition()

        # Forward to engine if available
        if self._engine:
            pass  # Engine handles its own state

    def on_die(self):
        """Clean shutdown."""
        if self._engine and hasattr(self._engine, 'stop'):
            try:
                self._engine.stop()
            except Exception:
                pass
        super().on_die()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

ACTOR_NAME = "SomaticAvatarFairy"
FAIRY_CLASS = SomaticAvatarFairyV3
