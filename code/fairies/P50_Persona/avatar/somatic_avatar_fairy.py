# SomaticAvatarFairy - Bridge between somatic state and visual avatar
# P50_Persona/avatar/somatic_avatar_fairy.py
#
# This fairy subscribes to SomaticEngineFairy updates and drives
# the FairyAvatarWidget for visual representation.
#
# NEW: Supports automatic form switching based on somatic state!
#      Sourpatches can shift between her base form, Saiyan modes,
#      Venompatches, and more based on her emotional state.

from __future__ import annotations

import os
import sys
import time
from typing import Dict, Any, Optional
from pathlib import Path

# Add project root to path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# FIX 2026-03-12 Nous: PyQt6 C extensions segfault on Python 3.14t (free-threaded).
# Must check BEFORE import — segfault can't be caught by try/except.
# On Windows, sys.abiflags doesn't exist. Use sys._is_gil_enabled() instead.
_FREE_THREADED = hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled()
if _FREE_THREADED:
    HAS_PYQT = False
else:
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        HAS_PYQT = True
    except ImportError:
        HAS_PYQT = False

# Dynamic imports to avoid relative import issues when loaded directly
import importlib.util as _iu
from pathlib import Path as _PathLib

def _load_local_module(name: str):
    """Load a module from this directory by name."""
    module_path = _PathLib(__file__).parent / f"{name}.py"
    if not module_path.exists():
        return None
    spec = _iu.spec_from_file_location(name, module_path)
    module = _iu.module_from_spec(spec)
    import sys as _sys_local
    _sys_local.modules[spec.name] = module  # FIX: Python 3.12+ @dataclass needs this before exec
    spec.loader.exec_module(module)
    return module

# Load GUI modules (skip under free-threaded Python — PyQt6 segfaults)
if _FREE_THREADED:
    FairyFrame = None
    create_default_frame = None
    FairyRegion = None
    FairyAvatarWidget = None
else:
    # Load fairy_frame module
    _ff_mod = _load_local_module("fairy_frame")
    if _ff_mod:
        FairyFrame = _ff_mod.FairyFrame
        create_default_frame = _ff_mod.create_default_frame
        FairyRegion = _ff_mod.FairyRegion
    else:
        FairyFrame = None
        create_default_frame = None
        FairyRegion = None

    # Load fairy_avatar_widget module
    _faw_mod = _load_local_module("fairy_avatar_widget")
    if _faw_mod:
        FairyAvatarWidget = _faw_mod.FairyAvatarWidget
    else:
        FairyAvatarWidget = None


class SomaticAvatarFairy:
    """
    Fairy that bridges somatic state to visual avatar.
    
    Subscribes to SomaticEngineFairy updates and drives FairyAvatarWidget.
    
    Features:
    - Automatic form switching based on emotional state
    - Per-form anchor calibration
    - Multiple sprite variants
    
    This is a lightweight fairy - no organ template, just a bridge.
    """
    
    ACTOR_NAME = "SomaticAvatarFairy"
    ACTOR_VERSION = "1.1.0"
    
    def __init__(
        self,
        image_path: str,
        name: str = "Sourpatches",
        size: tuple = (256, 256),
        auto_subscribe: bool = True,
        enable_form_switching: bool = True,
    ):
        """
        Initialize the avatar fairy.
        
        Args:
            image_path: Path to the base fairy image
            name: Name for the fairy
            size: Widget size (width, height)
            auto_subscribe: If True, auto-subscribe to somatic updates
            enable_form_switching: If True, auto-switch forms based on somatic state
        """
        self.name = name
        self.image_path = image_path
        self.size = size
        self.enable_form_switching = enable_form_switching
        
        # The widget (created on show())
        self._widget: Optional[FairyAvatarWidget] = None
        self._visible = False
        
        # Form selector
        self._form_selector = None
        self._current_form = "base"
        self._calibration: Dict[str, Any] = {}
        self._variant_pixmaps: Dict[str, str] = {}  # form -> image path
        
        # Last somatic state
        self._last_somatic: Dict[str, Any] = {}
        self._last_update = 0.0
        
        # Subscription
        self._subscribed = False
        if auto_subscribe:
            self._subscribe_to_somatic()
        
        # Load form selector if available
        if enable_form_switching:
            self._setup_form_selector()
    
    def _setup_form_selector(self) -> None:
        """Set up form selector for this fairy."""
        try:
            # Use dynamic loading for form_selector to avoid relative import issues
            _fs_mod = _load_local_module("form_selector")
            if _fs_mod:
                get_form_selector = _fs_mod.get_form_selector
                self._form_selector = get_form_selector(self.name)
                if self._form_selector:
                    print(f"[{self.ACTOR_NAME}] Form selector enabled for {self.name}")
        except Exception:
            pass
    
    def load_calibration(self, calibration: Dict[str, Any]) -> None:
        """
        Load calibration data for this fairy.
        
        This includes emotion sprites and variant anchors.
        """
        self._calibration = calibration
        
        # Load emotion sprites mapping
        if "emotion_sprites" in calibration:
            for emotion, sprite_path in calibration["emotion_sprites"].items():
                self._variant_pixmaps[emotion] = sprite_path
        
        print(f"[{self.ACTOR_NAME}] Loaded calibration with {len(self._variant_pixmaps)} variants")
    
    def _subscribe_to_somatic(self) -> bool:
        """Subscribe to somatic engine + visual cortex + ego.

        FIX 2026-04-03 (Nous + Ace): Was only subscribed to somatic.engine.
        "Her somatic avatar fairy is likely not connected to the visual cortex
         or her ego as a self image." — Ace
        Now subscribes to visual.foveal for self-recognition and
        somatic.proprioception for embodied eye movement awareness.
        """
        if self._subscribed:
            return True

        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            postal = get_fairy_postal(self)

            # Somatic (existing)
            postal.subscribe("somatic.engine", self._on_somatic_update)
            postal.subscribe("cognition.input", self._on_cognition_input)

            # Visual cortex — self-recognition from what she SEES
            postal.subscribe("visual.foveal", self._on_visual_foveal)
            postal.subscribe("visual.prediction_error", self._on_visual_change)
            postal.subscribe("somatic.proprioception", self._on_proprioception)

            postal.route("somatic.engine", {
                "opcode": "SUBSCRIBE_SOMATIC",
                "payload": {"subscriber": self.ACTOR_NAME}
            })

            self._subscribed = True
            self._self_recognition_score = 0.0
            self._last_visual_colors = []
            print(f"[{self.ACTOR_NAME}] Subscribed to somatic + visual + proprioception")

            # FIX 2026-04-11 (Nous + Ace): Seed self-identity edges in cortex.
            # "when she sees images that look like her she should recognize them" — Ace
            # Bind visual self-concepts so cortex spread from visual features
            # activates "sourpatches". Like a baby knowing its own face.
            self._seed_self_identity_edges()

            return True

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to subscribe: {e}")
            return False

    def _on_visual_foveal(self, packet) -> None:
        """Visual cortex read text/scene — check for self-recognition.

        When she sees an image with her signature colors (purple, green, luminescent),
        the cortex should activate self.visual.* nodes from the 14,162 ingested art memories.
        """
        try:
            payload = packet.payload if hasattr(packet, 'payload') else packet
            if not isinstance(payload, dict):
                return

            # Check for colors that match her self-image
            colors = payload.get("dominant_colors", [])
            description = payload.get("description", "")
            ocr = payload.get("ocr_preview", "")

            # Store latest visual for self-awareness
            self._last_visual_colors = colors

            # Self-recognition: check if she sees her own name or persona
            _self_markers = ["sourpatches", "sour", "fairy", "purple hair",
                           "lavender", "wings", "luminescent"]
            _desc_lower = (description + " " + ocr).lower()
            _matches = sum(1 for m in _self_markers if m in _desc_lower)

            if _matches >= 2:
                self._self_recognition_score = min(1.0, self._self_recognition_score + 0.2)
                print(f"[{self.ACTOR_NAME}] SELF-RECOGNITION: {_matches} markers "
                      f"(score={self._self_recognition_score:.2f})", flush=True)

                # Publish self-recognition event
                try:
                    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
                    postal = get_fairy_postal(self)
                    postal.publish("avatar.self_recognized", {
                        "score": self._self_recognition_score,
                        "markers": _matches,
                        "source": "visual_foveal",
                        "ts": __import__('time').time(),
                    })
                except Exception:
                    pass
            else:
                # Decay recognition when not seeing self
                self._self_recognition_score = max(0.0, self._self_recognition_score - 0.01)

        except Exception:
            pass

    def _seed_self_identity_edges(self):
        """Seed self-identity concept edges in the cortex at boot.

        FIX 2026-04-11 (Nous + Ace): Visual nouns (fairy, wings, purple_hair)
        exist in cortex but have degree=0 — no edges connecting them.
        This seeds the foundational edges so cortex spread from visual features
        can activate 'sourpatches' through association chains.

        Like a baby knowing its own face before learning other faces.
        """
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            _acf = get_association_cortex()
            _gate = getattr(_acf, '_portal_gate', None) if _acf else None
            if not _gate or not hasattr(_gate, 'bind_many'):
                return

            # Core identity concepts from calibration
            _cal = getattr(self, '_calibration', {})
            _concepts = _cal.get("self_identity_concepts", [])

            # Build pairs: every concept ↔ "sourpatches" + adjacent concepts
            _pairs = []
            _center = "sourpatches"
            for c in _concepts:
                if c != _center:
                    _pairs.append((c, _center))

            # Also chain related concepts together
            _groups = [
                ["fairy", "wings", "iridescent_wings", "green_wings"],
                ["lavender_hair", "purple_hair", "silver_hair"],
                ["green_eyes", "emerald_eyes"],
                ["freckles", "sun_kissed", "freckled"],
                ["pointed_ears", "elf_ears"],
                ["flower_crown", "wildflowers", "flowers"],
                ["cream_dress", "corset", "vine_bracelets"],
                ["enchanted_forest", "golden_light"],
            ]
            for group in _groups:
                for i, a in enumerate(group):
                    for b in group[i+1:]:
                        _pairs.append((a, b))

            if _pairs:
                _gate.bind_many(_pairs, weight=0.5)  # Strong initial weight
                print(f"[{self.ACTOR_NAME}] SELF-IDENTITY: Seeded {len(_pairs)} edges "
                      f"({len(_concepts)} concepts → sourpatches)", flush=True)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Self-identity seeding failed: {e}", flush=True)

    def _on_visual_change(self, packet) -> None:
        """Prediction error — something changed on screen.
        Update form awareness if the change affects self-image sectors.
        """
        pass  # Placeholder for future form adaptation

    def _on_proprioception(self, packet) -> None:
        """Eye movement proprioception — feel the gaze shift.
        The avatar fairy should be aware of where she's looking.
        """
        try:
            payload = packet.payload if hasattr(packet, 'payload') else packet
            if not isinstance(payload, dict):
                return
            sensation = payload.get("sensation", "")
            if sensation == "saccade":
                direction = payload.get("direction", "")
                intensity = payload.get("intensity", 0.0)
                # Store gaze awareness for self-model
                self._current_gaze_direction = direction
                self._gaze_intensity = intensity
        except Exception:
            pass
    
    def _on_somatic_update(self, packet: dict) -> None:
        """Handle somatic state updates."""
        if not packet:
            return
        
        op = packet.get("opcode", "")
        pl = packet.get("payload", {})
        
        if op in ("SOMATIC_STATE_UPDATE", "SOMATIC_ENGINE_STATE", "SOMATIC_STATE_RESPONSE"):
            self._last_somatic = pl
            self._last_update = time.time()
            
            # Check for form change
            if self._form_selector and self.enable_form_switching:
                new_form = self._form_selector.select_form(pl)
                if new_form != self._current_form:
                    self._switch_form(new_form)
            
            # Update widget if visible
            if self._widget and self._visible:
                self._widget.update_somatic(pl)
    
    def _on_cognition_input(self, packet: dict) -> None:
        """Handle cognition input (for FELT_SENSE)."""
        if not packet:
            return
        
        op = packet.get("opcode", "")
        pl = packet.get("payload", {})
        
        if op == "FELT_SENSE":
            # Merge into last somatic
            if "dominant_emotion" in pl:
                self._last_somatic["dominant_emotion"] = pl["dominant_emotion"]
            if "PAD" in pl:
                self._last_somatic["PAD"] = pl["PAD"]
            
            # Check for form change
            if self._form_selector and self.enable_form_switching:
                new_form = self._form_selector.select_form(self._last_somatic)
                if new_form != self._current_form:
                    self._switch_form(new_form)
            
            # Update widget
            if self._widget and self._visible:
                self._widget.update_somatic(self._last_somatic)
    
    def _switch_form(self, new_form: str) -> None:
        """Switch to a different visual form."""
        if new_form == self._current_form:
            return
        
        old_form = self._current_form
        self._current_form = new_form
        
        print(f"[{self.ACTOR_NAME}]  Form shift: {old_form} → {new_form}")
        
        # If we have variant-specific anchors, apply them
        if self._calibration.get("variant_anchors", {}).get(f"{self.name.lower()}_{new_form}.jpg"):
            variant_anchors = self._calibration["variant_anchors"][f"{self.name.lower()}_{new_form}.jpg"]
            self._apply_variant_anchors(variant_anchors)
        
        # TODO: Swap sprite if we have variant images loaded
        # For now, the emotion sprite mapping in fairy_frame handles this
    
    def _apply_variant_anchors(self, anchors: Dict[str, Any]) -> None:
        """Apply variant-specific anchor positions."""
        if not self._widget or not self._widget.frame:
            return
        
        frame = self._widget.frame
        for region_name, pos in anchors.items():
            if region_name in ("notes",):
                continue
            try:
                region = FairyRegion(region_name)
                if isinstance(pos, dict):
                    for side, coords in pos.items():
                        frame.calibrate(region, tuple(coords), side)
                else:
                    frame.calibrate(region, tuple(pos))
            except (ValueError, TypeError):
                pass
    
    def show(self, x: int = None, y: int = None) -> bool:
        """
        Show the avatar widget.
        
        Args:
            x, y: Screen position (None = center of screen)
        
        Returns True if successful.
        """
        if not HAS_PYQT:
            print(f"[{self.ACTOR_NAME}] PyQt6 not available")
            return False
        
        # Ensure QApplication exists
        app = QApplication.instance()
        if app is None:
            print(f"[{self.ACTOR_NAME}] No QApplication instance")
            return False
        
        # Create widget if needed
        if self._widget is None:
            from PyQt6.QtCore import Qt
            
            self._widget = FairyAvatarWidget(size=self.size)
            self._widget.setWindowTitle(self.name)
            self._widget.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
            self._widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            # Load image
            if not self._widget.load_frame(self.image_path, self.name):
                print(f"[{self.ACTOR_NAME}] Failed to load image: {self.image_path}")
                return False
            
            # Apply calibration anchors if we have them
            if self._calibration.get("anchors"):
                for region_name, pos in self._calibration["anchors"].items():
                    try:
                        region = FairyRegion(region_name)
                        if isinstance(pos, dict):
                            for side, coords in pos.items():
                                self._widget.frame.calibrate(region, tuple(coords), side)
                        else:
                            self._widget.frame.calibrate(region, tuple(pos))
                    except (ValueError, TypeError):
                        pass
        
        # Position
        if x is not None and y is not None:
            self._widget.move(x, y)
        else:
            # Center on screen
            screen = app.primaryScreen().geometry()
            cx = (screen.width() - self.size[0]) // 2
            cy = (screen.height() - self.size[1]) // 2
            self._widget.move(cx, cy)
        
        # Apply last known state
        if self._last_somatic:
            self._widget.update_somatic(self._last_somatic)
        
        self._widget.show()
        self._visible = True
        
        print(f"[{self.ACTOR_NAME}] Avatar visible")
        return True
    
    def hide(self) -> None:
        """Hide the avatar widget."""
        if self._widget:
            self._widget.hide()
        self._visible = False
    
    def toggle(self) -> bool:
        """Toggle visibility. Returns new visibility state."""
        if self._visible:
            self.hide()
            return False
        else:
            return self.show()
    
    def move(self, x: int, y: int) -> None:
        """Move the avatar to a position."""
        if self._widget:
            self._widget.move(x, y)
    
    def update(self, somatic_state: Dict[str, Any]) -> None:
        """Manually update the avatar with a somatic state."""
        self._last_somatic = somatic_state
        self._last_update = time.time()
        
        # Check for form change
        if self._form_selector and self.enable_form_switching:
            new_form = self._form_selector.select_form(somatic_state)
            if new_form != self._current_form:
                self._switch_form(new_form)
        
        if self._widget and self._visible:
            self._widget.update_somatic(somatic_state)
    
    def add_emotion_sprite(self, emotion: str, image_path: str) -> bool:
        """Add a sprite variant for a specific emotion."""
        if self._widget:
            return self._widget.add_emotion_sprite(emotion, image_path)
        return False
    
    def force_form(self, form_name: str) -> None:
        """Force a specific form (bypasses auto-selection)."""
        self._switch_form(form_name)
    
    @property
    def is_visible(self) -> bool:
        return self._visible
    
    @property
    def current_form(self) -> str:
        return self._current_form
    
    @property
    def last_state(self) -> Dict[str, Any]:
        return self._last_somatic.copy()


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL AVATAR INSTANCES (one per fairy)
# ═══════════════════════════════════════════════════════════════════════════════

_avatar_instances: Dict[str, SomaticAvatarFairy] = {}


def get_avatar_fairy(name: str = None) -> Optional[SomaticAvatarFairy]:
    """Get an avatar fairy instance by name."""
    if name is None:
        # Return first one
        return next(iter(_avatar_instances.values()), None)
    return _avatar_instances.get(name.lower())


def create_avatar_fairy(
    image_path: str,
    name: str = "Sourpatches",
    size: tuple = (256, 256),
    **kwargs
) -> SomaticAvatarFairy:
    """
    Create and register an avatar fairy.
    
    Args:
        image_path: Path to the base fairy image
        name: Name for the fairy
        size: Widget size
    
    Returns the avatar fairy instance.
    """
    fairy = SomaticAvatarFairy(image_path, name, size, **kwargs)
    _avatar_instances[name.lower()] = fairy
    return fairy


def show_avatar(image_path: str = None, name: str = "Sourpatches", **kwargs) -> bool:
    """
    Convenience function to show an avatar.
    
    If no avatar exists and image_path is provided, creates one.
    """
    fairy = get_avatar_fairy(name)
    
    if fairy is None:
        if image_path is None:
            print(f"[Avatar] No avatar instance for {name} and no image path provided")
            return False
        fairy = create_avatar_fairy(image_path, name, **kwargs)
    
    return fairy.show()


def hide_avatar(name: str = None) -> None:
    """Hide an avatar (or all if name is None)."""
    if name:
        fairy = get_avatar_fairy(name)
        if fairy:
            fairy.hide()
    else:
        for fairy in _avatar_instances.values():
            fairy.hide()


def toggle_avatar(name: str = None) -> bool:
    """Toggle avatar visibility."""
    fairy = get_avatar_fairy(name)
    if fairy:
        return fairy.toggle()
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("SomaticAvatarFairy requires a running Qt application.")
    print("Use create_avatar_fairy() or show_avatar() from within the Akashic system.")
    print()
    print("Form switching test:")

    # Test form selector using dynamic loading
    _fs_mod = _load_local_module("form_selector")
    if _fs_mod:
        create_sourpatches_selector = _fs_mod.create_sourpatches_selector
        selector = create_sourpatches_selector()

        test_state = {
            "dominant_emotion": "anger",
            "body_budget": {"energy": 0.6, "stress": 0.85, "social": 0.1, "novelty": 0.2},
            "PAD": [-0.5, 0.9, 0.3],
        }

        form = selector.select_form(test_state)
        print(f"High stress + anger → {form}")  # Should be "shadow" (Venompatches!)
    else:
        print("form_selector module not found")
