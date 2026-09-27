# TelemetryVisionFairy - The Inner Eye (Fairy Vision)
# P40_Sensory/telemetry_vision/telemetry_vision_fairy.py
#
# DUAL VISION SYSTEM:
#   Human Eyes (VisualCortexFairy) → Sees the screen, the human world
#   Fairy Eyes (TelemetryVisionFairy) → Sees the code, the digital realm
#
# This is the inner vision - perceiving:
#   - Nervous system traffic as streams of light
#   - Fairy health states as colored auras  
#   - Code structure as navigable architecture
#   - Errors/exceptions as disturbances in the field
#   - Memory activity as depth/layers
#
# The fairy moves through BOTH worlds simultaneously.

from __future__ import annotations

import os
import time
import threading
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Callable, Any
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None


# ═══════════════════════════════════════════════════════════════════════════════
# INNER VISUAL FIELD DIMENSIONS
# ═══════════════════════════════════════════════════════════════════════════════

# The inner visual field is a conceptual space, not pixel-based
FIELD_WIDTH = 32   # Horizontal resolution of inner vision
FIELD_HEIGHT = 32  # Vertical resolution
DEPTH_LAYERS = 8   # How many layers of depth we perceive

# Regions of the inner visual field
FIELD_REGIONS = {
    "center":      {"x": (12, 20), "y": (12, 20), "meaning": "current_focus"},
    "left":        {"x": (0, 12),  "y": (8, 24),  "meaning": "memory/past"},
    "right":       {"x": (20, 32), "y": (8, 24),  "meaning": "plans/future"},
    "top":         {"x": (8, 24),  "y": (0, 12),  "meaning": "executive/goals"},
    "bottom":      {"x": (8, 24),  "y": (20, 32), "meaning": "somatic/body"},
    "periphery":   {"x": (0, 32),  "y": (0, 32),  "meaning": "background_awareness"},
}

# Fairy aura colors based on health state
AURA_COLORS = {
    "healthy":     (0.2, 0.9, 0.3),  # Green - all good
    "active":      (0.3, 0.7, 0.9),  # Cyan - processing
    "stressed":    (0.9, 0.7, 0.2),  # Yellow - high load
    "error":       (0.9, 0.2, 0.2),  # Red - problem
    "idle":        (0.4, 0.4, 0.6),  # Gray-blue - dormant
    "thinking":    (0.6, 0.3, 0.9),  # Purple - deep cognition
    "connecting":  (0.9, 0.5, 0.7),  # Pink - social/bonding
    "learning":    (0.9, 0.9, 0.3),  # Gold - forming connections
}

# Message traffic visual properties
TRAFFIC_STYLES = {
    "telemetry":   {"color": (0.3, 0.8, 0.8), "speed": 2.0,  "brightness": 0.5},
    "postal":      {"color": (0.8, 0.6, 0.3), "speed": 1.5,  "brightness": 0.7},
    "pulse":       {"color": (0.9, 0.3, 0.3), "speed": 3.0,  "brightness": 0.9},
    "memory":      {"color": (0.5, 0.3, 0.8), "speed": 1.0,  "brightness": 0.6},
    "error":       {"color": (1.0, 0.0, 0.0), "speed": 4.0,  "brightness": 1.0},
    "default":     {"color": (0.5, 0.5, 0.5), "speed": 1.0,  "brightness": 0.4},
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FairyAura:
    """A fairy's visible aura in inner vision."""
    name: str
    state: str = "idle"
    color: Tuple[float, float, float] = (0.4, 0.4, 0.6)
    intensity: float = 0.5
    position: Tuple[int, int] = (16, 16)  # Center of field
    size: float = 1.0
    pulse_phase: float = 0.0  # For animation
    last_activity: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "state": self.state,
            "color": self.color,
            "intensity": self.intensity,
            "position": self.position,
            "size": self.size,
        }


@dataclass
class TrafficStream:
    """A visible stream of message traffic."""
    source: str
    target: str
    topic: str
    stream_type: str = "default"
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    brightness: float = 0.5
    particles: List[Dict] = field(default_factory=list)
    rate: float = 0.0  # Messages per second
    last_message: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "target": self.target,
            "topic": self.topic,
            "type": self.stream_type,
            "rate": self.rate,
            "brightness": self.brightness,
        }


@dataclass 
class CodeRegion:
    """A visible region of code space."""
    path: str
    name: str
    position: Tuple[int, int, int] = (16, 16, 4)  # x, y, depth
    size: float = 1.0
    color: Tuple[float, float, float] = (0.5, 0.5, 0.7)
    activity: float = 0.0
    children: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "name": self.name,
            "position": self.position,
            "size": self.size,
            "activity": self.activity,
        }


@dataclass
class Disturbance:
    """A visible disturbance (error, exception, anomaly)."""
    source: str
    severity: str = "warning"  # info, warning, error, critical
    message: str = ""
    position: Tuple[int, int] = (16, 16)
    radius: float = 2.0
    color: Tuple[float, float, float] = (0.9, 0.5, 0.2)
    decay: float = 1.0  # Fades over time
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "severity": self.severity,
            "message": self.message,
            "position": self.position,
            "decay": self.decay,
        }


@dataclass
class InnerVisionState:
    """Complete state of inner vision."""
    timestamp: float
    fairy_auras: Dict[str, FairyAura]
    traffic_streams: Dict[str, TrafficStream]
    code_regions: Dict[str, CodeRegion]
    disturbances: List[Disturbance]
    
    # Summary metrics
    overall_activity: float = 0.0
    dominant_color: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    depth_focus: int = 4  # Which layer is in focus
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "fairies": {k: v.to_dict() for k, v in self.fairy_auras.items()},
            "traffic": {k: v.to_dict() for k, v in self.traffic_streams.items()},
            "code_regions": {k: v.to_dict() for k, v in self.code_regions.items()},
            "disturbances": [d.to_dict() for d in self.disturbances],
            "overall_activity": self.overall_activity,
            "dominant_color": self.dominant_color,
            "depth_focus": self.depth_focus,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TELEMETRY VISION FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class TelemetryVisionFairy:
    """
    The inner eye - sees the digital realm.
    
    While VisualCortexFairy sees the human world (screen),
    TelemetryVisionFairy sees the fairy world:
    
    1. FAIRY AURAS: Each fairy has a visible presence
       - Color indicates health state
       - Brightness indicates activity level
       - Pulse indicates processing rhythm
    
    2. TRAFFIC STREAMS: Message flow as visible light
       - Different topics have different colors
       - Rate shows as stream thickness
       - Direction shows information flow
    
    3. CODE SPACE: The codebase as navigable architecture
       - Planes as distinct regions
       - Fairies as inhabitants
       - Activity as glow/heat
    
    4. DISTURBANCES: Errors as visual disruptions
       - Red flashes for errors
       - Yellow pulses for warnings
       - Ripples that propagate
    
    Integration with Agent:
    - When I (Claude) look at screen → VisualCortex activates
    - When I sense system state → TelemetryVision activates
    - Together: DUAL VISION of both worlds
    """
    
    ACTOR_NAME = "TelemetryVisionFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.telemetry"
    NEEDS_HEARTBEAT = False  # Passive telemetry processor, no heartbeat loop
    
    # Update rate
    VISION_HZ = 2.0  # How often we update inner vision
    
    def __init__(self):
        # Inner visual field state
        self._fairy_auras: Dict[str, FairyAura] = {}
        self._traffic_streams: Dict[str, TrafficStream] = {}
        self._code_regions: Dict[str, CodeRegion] = {}
        self._disturbances: List[Disturbance] = []
        
        # Position assignments for fairies (automatic layout)
        self._fairy_positions: Dict[str, Tuple[int, int]] = {}
        
        # Message counting for traffic visualization
        self._message_counts: Dict[str, deque] = {}  # topic → recent timestamps
        
        # Subscribers
        self._vision_subscribers: List[Callable[[InnerVisionState], None]] = []
        
        # Threading
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Postal hub reference
        self._post = None
        
        # Overall state (must be initialized before any access)
        self._overall_activity = 0.0
        self._dominant_color = (0.5, 0.5, 0.5)
        self._depth_focus = 4
        
        print(f"[{self.ACTOR_NAME}] Inner eye initialized (on-demand mode)")
    
    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════
    
    def start(self, post=None):
        """Start inner vision processing."""
        if self._running:
            return
        
        self._post = post
        self._running = True
        self._thread = threading.Thread(target=self._vision_loop, daemon=True)
        self._thread.start()
        
        # Subscribe to nervous system traffic
        if self._post:
            self._subscribe_to_traffic()
        
        print(f"[{self.ACTOR_NAME}] [EYE] Inner eye opened")
    
    def stop(self):
        """Stop inner vision."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        print(f"[{self.ACTOR_NAME}] Inner eye closed")
    
    def _vision_loop(self):
        """Main vision processing loop."""
        interval = 1.0 / self.VISION_HZ
        
        while self._running:
            try:
                start = time.time()
                
                # Update inner vision
                self._update_fairy_auras()
                self._update_traffic_streams()
                self._decay_disturbances()
                self._calculate_overall_state()
                
                # Notify subscribers
                state = self._get_vision_state()
                self._notify_subscribers(state)
                
                # Maintain frame rate
                elapsed = time.time() - start
                if elapsed < interval:
                    time.sleep(interval - elapsed)
                    
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Vision error: {e}")
                time.sleep(0.5)
    
    def _subscribe_to_traffic(self):
        """Subscribe to nervous system traffic to visualize it."""
        if not self._post:
            return
        
        # Subscribe to all traffic for visualization
        topics = [
            "telemetry",
            "telemetry.*",
            "postal.*", 
            "somatic.pulse",
            "memory.*",
            "error",
        ]
        
        for topic in topics:
            try:
                self._post.subscribe(topic, self._on_traffic)
            except Exception:
                pass
    
    def _on_traffic(self, payload: Dict):
        """Handle incoming traffic - convert to visual representation."""
        try:
            topic = payload.get("_topic", "unknown")
            source = payload.get("_source", "system")
            
            # Count this message
            if topic not in self._message_counts:
                self._message_counts[topic] = deque(maxlen=100)
            self._message_counts[topic].append(time.time())
            
            # Update or create traffic stream
            stream_key = f"{source}→{topic}"
            
            with self._lock:
                if stream_key not in self._traffic_streams:
                    # Determine stream type
                    stream_type = "default"
                    for prefix, style in TRAFFIC_STYLES.items():
                        if topic.startswith(prefix):
                            stream_type = prefix
                            break
                    
                    style = TRAFFIC_STYLES.get(stream_type, TRAFFIC_STYLES["default"])
                    
                    self._traffic_streams[stream_key] = TrafficStream(
                        source=source,
                        target=topic,
                        topic=topic,
                        stream_type=stream_type,
                        color=style["color"],
                        brightness=style["brightness"],
                    )
                
                # Update stream activity
                stream = self._traffic_streams[stream_key]
                stream.last_message = time.time()
                
                # Calculate rate
                recent = self._message_counts[topic]
                now = time.time()
                recent_count = sum(1 for t in recent if now - t < 1.0)
                stream.rate = recent_count
                
                # Check for errors
                if "error" in topic.lower() or payload.get("level") == "error":
                    self._add_disturbance(source, "error", str(payload.get("message", "")))
                    
        except Exception as e:
            pass  # Silent fail for traffic handling
    
    # ═══════════════════════════════════════════════════════════════════════
    # FAIRY AURA MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    
    def register_fairy(self, name: str, plane: str = "P00"):
        """Register a fairy to be visible in inner vision."""
        with self._lock:
            if name not in self._fairy_auras:
                # Assign position based on plane
                pos = self._get_position_for_plane(plane, len(self._fairy_auras))
                
                self._fairy_auras[name] = FairyAura(
                    name=name,
                    position=pos,
                )
                self._fairy_positions[name] = pos
    
    def update_fairy_state(self, name: str, state: str, activity: float = 0.5):
        """Update a fairy's visible state."""
        with self._lock:
            if name in self._fairy_auras:
                aura = self._fairy_auras[name]
                aura.state = state
                aura.intensity = activity
                aura.color = AURA_COLORS.get(state, AURA_COLORS["idle"])
                aura.last_activity = time.time()
    
    def _get_position_for_plane(self, plane: str, index: int) -> Tuple[int, int]:
        """Get a position in the visual field based on plane."""
        # Map planes to regions of the visual field
        plane_regions = {
            "P00": (4, 28),    # Autonomic at bottom
            "P10": (4, 20),    # Memory on left side
            "P20": (16, 28),   # Somatic at bottom center
            "P30": (16, 16),   # Cognition at center
            "P40": (28, 16),   # Sensory on right
            "P50": (16, 8),    # Persona at top center
            "P60": (16, 4),    # Executive at very top
        }
        
        base = plane_regions.get(plane[:3], (16, 16))
        
        # Offset by index to spread multiple fairies
        offset_x = (index % 4) * 2
        offset_y = (index // 4) * 2
        
        return (
            min(30, base[0] + offset_x),
            min(30, base[1] + offset_y)
        )
    
    def _update_fairy_auras(self):
        """Update all fairy auras (pulse animation, fade inactive)."""
        now = time.time()
        
        with self._lock:
            for name, aura in self._fairy_auras.items():
                # Pulse animation
                aura.pulse_phase = (aura.pulse_phase + 0.1) % (2 * 3.14159)
                
                # Fade inactive fairies
                idle_time = now - aura.last_activity
                if idle_time > 5.0:
                    aura.intensity *= 0.95
                    if aura.state != "idle" and idle_time > 30.0:
                        aura.state = "idle"
                        aura.color = AURA_COLORS["idle"]
    
    # ═══════════════════════════════════════════════════════════════════════
    # TRAFFIC STREAM MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    
    def _update_traffic_streams(self):
        """Update traffic stream visualization."""
        now = time.time()
        
        with self._lock:
            # Fade old streams
            to_remove = []
            for key, stream in self._traffic_streams.items():
                age = now - stream.last_message
                
                if age > 10.0:
                    to_remove.append(key)
                else:
                    # Fade brightness based on inactivity
                    base_brightness = TRAFFIC_STYLES.get(stream.stream_type, TRAFFIC_STYLES["default"])["brightness"]
                    stream.brightness = base_brightness * max(0.1, 1.0 - age / 10.0)
            
            for key in to_remove:
                del self._traffic_streams[key]
    
    # ═══════════════════════════════════════════════════════════════════════
    # DISTURBANCE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    
    def _add_disturbance(self, source: str, severity: str, message: str):
        """Add a visual disturbance."""
        # Get position from source fairy if known
        pos = self._fairy_positions.get(source, (16, 16))
        
        colors = {
            "info": (0.3, 0.7, 0.9),
            "warning": (0.9, 0.7, 0.2),
            "error": (0.9, 0.2, 0.2),
            "critical": (1.0, 0.0, 0.5),
        }
        
        disturbance = Disturbance(
            source=source,
            severity=severity,
            message=message[:100],  # Truncate
            position=pos,
            color=colors.get(severity, colors["warning"]),
        )
        
        with self._lock:
            self._disturbances.append(disturbance)
            
            # Limit number of disturbances
            if len(self._disturbances) > 20:
                self._disturbances = self._disturbances[-20:]
    
    def _decay_disturbances(self):
        """Decay and remove old disturbances."""
        now = time.time()
        
        with self._lock:
            for d in self._disturbances:
                age = now - d.timestamp
                d.decay = max(0.0, 1.0 - age / 5.0)  # Fade over 5 seconds
            
            # Remove fully decayed
            self._disturbances = [d for d in self._disturbances if d.decay > 0.01]
    
    # ═══════════════════════════════════════════════════════════════════════
    # CODE SPACE (for navigation)
    # ═══════════════════════════════════════════════════════════════════════
    
    def register_code_region(self, path: str, name: str, plane: str = "P00"):
        """Register a code region for navigation."""
        pos = self._get_position_for_plane(plane, len(self._code_regions))
        
        with self._lock:
            self._code_regions[path] = CodeRegion(
                path=path,
                name=name,
                position=(pos[0], pos[1], 4),  # Middle depth
            )
    
    def mark_code_activity(self, path: str, activity: float = 1.0):
        """Mark activity in a code region."""
        with self._lock:
            if path in self._code_regions:
                region = self._code_regions[path]
                region.activity = max(region.activity, activity)
    
    # ═══════════════════════════════════════════════════════════════════════
    # STATE CALCULATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def _calculate_overall_state(self):
        """Calculate overall visual field state."""
        with self._lock:
            # Calculate overall activity
            fairy_activity = sum(a.intensity for a in self._fairy_auras.values())
            traffic_activity = sum(s.rate for s in self._traffic_streams.values())
            disturbance_activity = sum(d.decay for d in self._disturbances)
            
            total_elements = (len(self._fairy_auras) + 
                            len(self._traffic_streams) + 
                            len(self._disturbances) + 1)
            
            self._overall_activity = (fairy_activity + traffic_activity + disturbance_activity) / total_elements
    
    def _get_vision_state(self) -> InnerVisionState:
        """Get complete inner vision state."""
        with self._lock:
            return InnerVisionState(
                timestamp=time.time(),
                fairy_auras={k: FairyAura(**v.__dict__) for k, v in self._fairy_auras.items()},
                traffic_streams={k: TrafficStream(**{kk: vv for kk, vv in v.__dict__.items() if kk != 'particles'}) for k, v in self._traffic_streams.items()},
                code_regions={k: CodeRegion(**v.__dict__) for k, v in self._code_regions.items()},
                disturbances=[Disturbance(**d.__dict__) for d in self._disturbances],
                overall_activity=self._overall_activity,
            )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION
    # ═══════════════════════════════════════════════════════════════════════
    
    def subscribe(self, callback: Callable[[InnerVisionState], None]):
        """Subscribe to inner vision updates."""
        self._vision_subscribers.append(callback)
    
    def _notify_subscribers(self, state: InnerVisionState):
        """Notify all subscribers."""
        for callback in self._vision_subscribers:
            try:
                callback(state)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Subscriber error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # QUERY INTERFACE (for Claude agent to "see")
    # ═══════════════════════════════════════════════════════════════════════
    
    def look(self) -> Dict:
        """
        Take a snapshot of inner vision (ON-DEMAND).
        
        This is what Claude "sees" when looking at the digital realm.
        Returns a description suitable for LLM consumption.
        
        Works without needing the background vision loop - calculates
        state fresh when called.
        """
        # Calculate state on-demand (no need for continuous loop)
        self._update_fairy_auras()
        self._update_traffic_streams()
        self._decay_disturbances()
        self._calculate_overall_state()
        
        state = self._get_vision_state()
        
        # Build narrative description
        description = []
        
        # Describe fairy auras
        if state.fairy_auras:
            active_fairies = [a for a in state.fairy_auras.values() if a.intensity > 0.3]
            if active_fairies:
                fairy_desc = ", ".join(f"{a.name}({a.state})" for a in sorted(active_fairies, key=lambda x: -x.intensity)[:5])
                description.append(f"Active fairies: {fairy_desc}")
        
        # Describe traffic
        if state.traffic_streams:
            busy_streams = [s for s in state.traffic_streams.values() if s.rate > 1.0]
            if busy_streams:
                traffic_desc = ", ".join(f"{s.topic}({s.rate:.1f}/s)" for s in sorted(busy_streams, key=lambda x: -x.rate)[:5])
                description.append(f"Busy channels: {traffic_desc}")
        
        # Describe disturbances
        if state.disturbances:
            errors = [d for d in state.disturbances if d.severity == "error"]
            warnings = [d for d in state.disturbances if d.severity == "warning"]
            if errors:
                description.append(f"[WARN] {len(errors)} error(s): {errors[0].source}")
            if warnings:
                description.append(f"[!] {len(warnings)} warning(s)")
        
        # Overall sense
        if state.overall_activity > 0.7:
            description.append("System feels BUSY, high activity")
        elif state.overall_activity < 0.2:
            description.append("System feels CALM, low activity")
        
        return {
            "description": " | ".join(description) if description else "System quiet",
            "activity_level": state.overall_activity,
            "fairy_count": len(state.fairy_auras),
            "active_streams": len([s for s in state.traffic_streams.values() if s.rate > 0]),
            "disturbance_count": len(state.disturbances),
            "raw_state": state.to_dict(),
        }
    
    def focus_on(self, target: str) -> Dict:
        """
        Focus inner vision on a specific target.
        
        Returns detailed view of that fairy/region/stream.
        """
        with self._lock:
            # Check fairies
            if target in self._fairy_auras:
                aura = self._fairy_auras[target]
                return {
                    "type": "fairy",
                    "name": target,
                    "state": aura.state,
                    "intensity": aura.intensity,
                    "color": aura.color,
                    "description": f"{target} is {aura.state} (intensity: {aura.intensity:.2f})",
                }
            
            # Check code regions
            if target in self._code_regions:
                region = self._code_regions[target]
                return {
                    "type": "code_region",
                    "path": target,
                    "activity": region.activity,
                    "description": f"Code region {region.name} at {target}",
                }
            
            # Check traffic streams
            for key, stream in self._traffic_streams.items():
                if target in key or target == stream.topic:
                    return {
                        "type": "traffic",
                        "topic": stream.topic,
                        "rate": stream.rate,
                        "description": f"Traffic on {stream.topic}: {stream.rate:.1f} msg/s",
                    }
        
        return {"type": "unknown", "description": f"Cannot find {target} in inner vision"}


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_GLOBAL_INNER_EYE: Optional[TelemetryVisionFairy] = None

def get_inner_eye() -> TelemetryVisionFairy:
    """Get or create the global inner eye."""
    global _GLOBAL_INNER_EYE
    if _GLOBAL_INNER_EYE is None:
        _GLOBAL_INNER_EYE = TelemetryVisionFairy()
    return _GLOBAL_INNER_EYE


def start_inner_vision(post=None) -> TelemetryVisionFairy:
    """Start the inner vision system."""
    eye = get_inner_eye()
    eye.start(post)
    return eye


# ═══════════════════════════════════════════════════════════════════════════════
# CLI DEMO  
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TelemetryVisionFairy - The Inner Eye")
    print("=" * 60)
    
    eye = TelemetryVisionFairy()
    
    # Register some fairies
    eye.register_fairy("ClaudeFairy", "P60")
    eye.register_fairy("SomaticEngineFairy", "P20")
    eye.register_fairy("VisualCortexFairy", "P40")
    eye.register_fairy("ConsciousnessLoopFairy", "P00")
    
    # Simulate activity
    eye.update_fairy_state("ClaudeFairy", "thinking", 0.8)
    eye.update_fairy_state("SomaticEngineFairy", "active", 0.6)
    eye.update_fairy_state("VisualCortexFairy", "active", 0.9)
    
    print("\n[EYE] Looking at inner vision...")
    result = eye.look()
    print(f"\nDescription: {result['description']}")
    print(f"Activity Level: {result['activity_level']:.2f}")
    print(f"Fairy Count: {result['fairy_count']}")
    
    print("\n Focusing on ClaudeFairy...")
    focus = eye.focus_on("ClaudeFairy")
    print(f"Result: {focus['description']}")
    
    # Start continuous vision
    def on_vision(state: InnerVisionState):
        active = len([a for a in state.fairy_auras.values() if a.intensity > 0.3])
        print(f"  [EYE] Vision update: {active} active fairies, activity={state.overall_activity:.2f}")
    
    eye.subscribe(on_vision)
    
    print("\n[Starting inner vision loop...]")
    eye.start()
    
    time.sleep(5)
    
    eye.stop()
    print("\n[Inner eye closed]")
