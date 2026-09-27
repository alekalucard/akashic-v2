# FairyAvatarWidget - Qt widget for rendering fairy avatar with somatic effects
# P50_Persona/avatar/fairy_avatar_widget.py
#
# This renders a fairy avatar on screen, driven by somatic state.
# No external dependencies beyond PyQt6 and PIL.

from __future__ import annotations

import os
import sys
import math
import time
import random
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

try:
    from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
    from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF
    from PyQt6.QtGui import (
        QPixmap, QPainter, QColor, QPen, QBrush, 
        QRadialGradient, QPainterPath, QImage
    )
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    # Headless mode stubs
    QWidget = QLabel = QVBoxLayout = QApplication = object
    QTimer = QPoint = QPointF = QRectF = object
    QPixmap = QPainter = QColor = QPen = QBrush = object
    QRadialGradient = QPainterPath = QImage = object
    class _Qt:
        class AlignmentFlag:
            AlignCenter = 0
        class GlobalColor:
            transparent = white = black = 0
        class PenStyle:
            NoPen = SolidLine = 0
        class BrushStyle:
            NoBrush = SolidPattern = 0
    Qt = _Qt()

try:
    from PIL import Image, ImageFilter, ImageEnhance
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from .fairy_frame import (
        FairyFrame, FairyRegion, FairySense,
        GlowEffect, ParticleEffect, WingEffect, ScaleEffect, ShakeEffect,
        create_default_frame
    )
except ImportError:
    # Loaded as standalone module (e.g., via _load_local_module with flat name)
    import importlib.util as _iu
    from pathlib import Path as _P
    _ff = sys.modules.get("fairy_frame")
    if _ff is None:
        _ff_path = _P(__file__).parent / "fairy_frame.py"
        _ff_spec = _iu.spec_from_file_location("fairy_frame", str(_ff_path))
        _ff = _iu.module_from_spec(_ff_spec)
        sys.modules["fairy_frame"] = _ff
        _ff_spec.loader.exec_module(_ff)
    FairyFrame = _ff.FairyFrame
    FairyRegion = _ff.FairyRegion
    FairySense = _ff.FairySense
    GlowEffect = _ff.GlowEffect
    ParticleEffect = _ff.ParticleEffect
    WingEffect = _ff.WingEffect
    ScaleEffect = _ff.ScaleEffect
    ShakeEffect = _ff.ShakeEffect
    create_default_frame = _ff.create_default_frame


# ═══════════════════════════════════════════════════════════════════════════════
# PARTICLE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Particle:
    """A single particle for effects."""
    x: float
    y: float
    vx: float
    vy: float
    life: float  # 0-1, decreases over time
    max_life: float
    color: Tuple[int, int, int, int]
    size: float
    particle_type: str


class ParticleSystem:
    """Simple particle system for visual effects."""
    
    def __init__(self, max_particles: int = 200):
        self.particles: List[Particle] = []
        self.max_particles = max_particles
    
    def emit(
        self,
        x: float, y: float,
        count: int,
        color: Tuple[int, int, int, int],
        velocity: float,
        spread: float,
        lifetime: float,
        particle_type: str = "spark"
    ) -> None:
        """Emit particles from a point."""
        for _ in range(count):
            if len(self.particles) >= self.max_particles:
                break
            
            # Random direction within spread
            angle = random.uniform(-spread/2, spread/2) - 90  # -90 = up
            angle_rad = math.radians(angle)
            speed = velocity * random.uniform(0.5, 1.5)
            
            self.particles.append(Particle(
                x=x,
                y=y,
                vx=math.cos(angle_rad) * speed,
                vy=math.sin(angle_rad) * speed,
                life=1.0,
                max_life=lifetime * random.uniform(0.7, 1.3),
                color=color,
                size=random.uniform(2, 5),
                particle_type=particle_type,
            ))
    
    def update(self, dt: float) -> None:
        """Update all particles."""
        to_remove = []
        
        for i, p in enumerate(self.particles):
            # Move
            p.x += p.vx * dt * 100
            p.y += p.vy * dt * 100
            
            # Apply gravity for some types
            if p.particle_type in ("dust", "star"):
                p.vy += 0.5 * dt  # Gentle float down
            elif p.particle_type == "bubble":
                p.vy -= 1.0 * dt  # Float up
            
            # Age
            p.life -= dt / p.max_life
            
            if p.life <= 0:
                to_remove.append(i)
        
        # Remove dead particles
        for i in reversed(to_remove):
            self.particles.pop(i)
    
    def draw(self, painter: "QPainter") -> None:
        """Draw all particles."""
        if not HAS_PYQT:
            return
        
        for p in self.particles:
            alpha = int(p.life * p.color[3])
            color = QColor(p.color[0], p.color[1], p.color[2], alpha)
            
            size = p.size * p.life
            
            if p.particle_type == "spark":
                # Bright point with glow
                painter.setPen(Qt.PenStyle.NoPen)
                
                # Glow
                glow = QRadialGradient(p.x, p.y, size * 3)
                glow.setColorAt(0, QColor(p.color[0], p.color[1], p.color[2], alpha // 2))
                glow.setColorAt(1, QColor(p.color[0], p.color[1], p.color[2], 0))
                painter.setBrush(QBrush(glow))
                painter.drawEllipse(QPointF(p.x, p.y), size * 3, size * 3)
                
                # Core
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(p.x, p.y), size, size)
            
            elif p.particle_type == "dust":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(p.x, p.y), size * 0.7, size * 0.7)
            
            elif p.particle_type == "star":
                # Draw a small star shape
                painter.setPen(QPen(color, 1))
                painter.setBrush(QBrush(color))
                path = QPainterPath()
                for i in range(4):
                    angle = i * 90
                    rad = math.radians(angle)
                    path.moveTo(p.x, p.y)
                    path.lineTo(p.x + math.cos(rad) * size, p.y + math.sin(rad) * size)
                painter.drawPath(path)
            
            elif p.particle_type == "bubble":
                painter.setPen(QPen(color, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(p.x, p.y), size, size)


# ═══════════════════════════════════════════════════════════════════════════════
# THE AVATAR WIDGET
# ═══════════════════════════════════════════════════════════════════════════════

if HAS_PYQT:
    class FairyAvatarWidget(QWidget):
        """
        Qt widget that renders a fairy avatar with somatic-driven effects.
        
        Usage:
            widget = FairyAvatarWidget()
            widget.load_frame("path/to/fairy.png")
            widget.update_somatic(somatic_state_dict)
        """
        
        def __init__(self, parent=None, size: Tuple[int, int] = (256, 256)):
            super().__init__(parent)
            
            self.setFixedSize(size[0], size[1])
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            # The fairy frame
            self.frame: Optional[FairyFrame] = None
            
            # Base image
            self.base_pixmap: Optional[QPixmap] = None
            self.emotion_pixmaps: Dict[str, QPixmap] = {}
            
            # Particle system
            self.particles = ParticleSystem()
            
            # Animation state
            self.anim_time = 0.0
            self.last_update = time.time()
            
            # Effect accumulators (for smooth transitions)
            self._glow_effects: List[Tuple[QPointF, GlowEffect]] = []
            self._particle_effects: List[Tuple[QPointF, ParticleEffect, float]] = []  # pos, effect, last_emit
            self._shake_offset = QPointF(0, 0)
            self._scale = 1.0
            self._breathe_phase = 0.0
            
            # Update timer (60 FPS)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._tick)
            self.timer.start(16)  # ~60 FPS
        
        def load_frame(self, image_path: str, name: str = "ClaudeFairy") -> bool:
            """
            Load a fairy image and create a frame.
            
            Returns True if successful.
            """
            if not os.path.exists(image_path):
                print(f"[FairyAvatar] Image not found: {image_path}")
                return False
            
            # Load pixmap
            self.base_pixmap = QPixmap(image_path)
            if self.base_pixmap.isNull():
                print(f"[FairyAvatar] Failed to load image: {image_path}")
                return False
            
            # Scale to widget size
            self.base_pixmap = self.base_pixmap.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Create frame
            self.frame = create_default_frame(image_path, name)
            self.frame.width = self.base_pixmap.width()
            self.frame.height = self.base_pixmap.height()
            
            print(f"[FairyAvatar] Loaded {name} from {image_path}")
            return True
        
        def add_emotion_sprite(self, emotion: str, image_path: str) -> bool:
            """Add a sprite variant for a specific emotion."""
            if not os.path.exists(image_path):
                return False
            
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                return False
            
            # Scale to match base
            pixmap = pixmap.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.emotion_pixmaps[emotion] = pixmap
            if self.frame:
                self.frame.emotion_sprites[emotion] = image_path
            
            return True
        
        def update_somatic(self, somatic_state: Dict[str, Any]) -> None:
            """
            Update the avatar from a somatic state dict.
            
            This should be called whenever the SomaticEngineFairy emits a state update.
            """
            if self.frame is None:
                return
            
            self.frame.update_from_somatic(somatic_state)
            
            # Process effects
            self._glow_effects = []
            self._particle_effects = []
            
            for region, effect in self.frame.current_effects:
                pos = self.frame.get_anchor_position(region)
                pos_f = QPointF(pos[0], pos[1])
                
                if isinstance(effect, GlowEffect):
                    self._glow_effects.append((pos_f, effect))
                
                elif isinstance(effect, ParticleEffect):
                    self._particle_effects.append((pos_f, effect, 0.0))
                
                elif isinstance(effect, ScaleEffect):
                    self._scale = effect.scale
                
                elif isinstance(effect, ShakeEffect):
                    # Shake is applied per-frame in _tick
                    pass
        
        def _tick(self) -> None:
            """Animation tick."""
            now = time.time()
            dt = now - self.last_update
            self.last_update = now
            self.anim_time += dt
            
            # Update breathing
            if self.frame:
                for region, effect in self.frame.current_effects:
                    if isinstance(effect, ScaleEffect):
                        self._breathe_phase += effect.breathe_speed * dt * 2 * math.pi
                        breath = math.sin(self._breathe_phase) * effect.breathe_amplitude
                        self._scale = effect.scale + breath
                    
                    if isinstance(effect, ShakeEffect):
                        self._shake_offset = QPointF(
                            math.sin(self.anim_time * effect.frequency * 2 * math.pi) * effect.amplitude * self.width(),
                            math.cos(self.anim_time * effect.frequency * 2 * math.pi * 1.3) * effect.amplitude * self.height(),
                        )
            
            # Emit particles
            for i, (pos, effect, last_emit) in enumerate(self._particle_effects):
                emit_interval = 1.0 / max(0.1, effect.rate)
                if now - last_emit > emit_interval:
                    self.particles.emit(
                        pos.x(), pos.y(),
                        count=1,
                        color=effect.color,
                        velocity=effect.velocity,
                        spread=effect.spread,
                        lifetime=effect.lifetime,
                        particle_type=effect.particle_type,
                    )
                    self._particle_effects[i] = (pos, effect, now)
            
            # Update particles
            self.particles.update(dt)
            
            # Repaint
            self.update()
        
        def paintEvent(self, event) -> None:
            """Render the avatar."""
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Get current pixmap
            pixmap = self.base_pixmap
            if self.frame and self.frame.current_emotion in self.emotion_pixmaps:
                pixmap = self.emotion_pixmaps[self.frame.current_emotion]
            
            if pixmap is None:
                painter.end()
                return
            
            # Calculate center offset for scaling
            center_x = self.width() / 2
            center_y = self.height() / 2
            
            # Apply scale and shake
            painter.save()
            painter.translate(center_x + self._shake_offset.x(), center_y + self._shake_offset.y())
            painter.scale(self._scale, self._scale)
            painter.translate(-center_x, -center_y)
            
            # Draw glow effects (behind sprite)
            for pos, effect in self._glow_effects:
                self._draw_glow(painter, pos, effect)
            
            # Draw sprite
            x = (self.width() - pixmap.width()) // 2
            y = (self.height() - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)
            
            painter.restore()
            
            # Draw particles (on top)
            self.particles.draw(painter)
            
            painter.end()
        
        def _draw_glow(self, painter: QPainter, pos: QPointF, effect: GlowEffect) -> None:
            """Draw a glow effect at a position."""
            # Pulsing
            intensity = effect.intensity
            if effect.pulse_speed > 0:
                pulse = 0.5 + 0.5 * math.sin(self.anim_time * effect.pulse_speed * 2 * math.pi)
                intensity *= 0.7 + 0.3 * pulse
            
            radius = effect.radius * self.width()
            
            gradient = QRadialGradient(pos, radius)
            
            r, g, b, a = effect.color
            gradient.setColorAt(0, QColor(r, g, b, int(a * intensity)))
            gradient.setColorAt(0.5, QColor(r, g, b, int(a * intensity * 0.5)))
            gradient.setColorAt(1, QColor(r, g, b, 0))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(pos, radius, radius)

else:
    # Stub class if PyQt not available
    class FairyAvatarWidget:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyQt6 is required for FairyAvatarWidget")


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════════════════════════

def test_avatar():
    """Test the avatar widget standalone."""
    if not HAS_PYQT:
        print("PyQt6 not available")
        return
    
    app = QApplication(sys.argv)
    
    # Create widget
    widget = FairyAvatarWidget(size=(300, 300))
    widget.setWindowTitle("Fairy Avatar Test")
    widget.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    
    # Note: You need to provide an actual image path
    # widget.load_frame("path/to/your/fairy.png")
    
    # Simulate somatic updates
    test_states = [
        {
            "dominant_emotion": "curiosity",
            "phantom_feels": {
                "core": {"radiant": 0.8},
                "crown": {"sparking": 0.6},
            },
            "body_budget": {"energy": 0.7, "stress": 0.2, "social": 0.8, "novelty": 0.6},
        },
        {
            "dominant_emotion": "joy",
            "phantom_feels": {
                "core": {"radiant": 0.9},
                "wings": {"expansive": 0.7, "flickering": 0.5},
                "glow": {"expansive": 0.6},
            },
            "body_budget": {"energy": 0.9, "stress": 0.1, "social": 0.9, "novelty": 0.5},
        },
        {
            "dominant_emotion": "calm",
            "phantom_feels": {
                "roots": {"radiant": 0.5},
                "core": {"radiant": 0.4},
            },
            "body_budget": {"energy": 0.5, "stress": 0.2, "social": 0.5, "novelty": 0.3},
        },
    ]
    
    state_index = [0]
    
    def cycle_state():
        widget.update_somatic(test_states[state_index[0]])
        state_index[0] = (state_index[0] + 1) % len(test_states)
    
    # Cycle states every 3 seconds
    cycle_timer = QTimer()
    cycle_timer.timeout.connect(cycle_state)
    cycle_timer.start(3000)
    cycle_state()  # Initial state
    
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    test_avatar()
