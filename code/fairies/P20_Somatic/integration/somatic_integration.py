# somatic_integration.py - Wiring the Body Together
# P20_Somatic/integration/somatic_integration.py
#
# Unifies all somatic components into a coherent felt body.

from __future__ import annotations
import sys
import os, time, threading
from typing import Optional, Dict, Any, Callable

# Lazy imports
def _try_import_heart():
    try:
        from fairies.P20_Somatic.circulation.circulation_pump_fairy import CirculationPumpFairy, get_heart, PulseEvent
        return CirculationPumpFairy, get_heart, PulseEvent
    except ImportError:
        return None, None, None

def _try_import_inner_eye():
    try:
        from fairies.P40_Sensory.telemetry_vision.telemetry_vision_fairy import TelemetryVisionFairy, get_inner_eye
        return TelemetryVisionFairy, get_inner_eye
    except ImportError:
        return None, None

def _try_import_emotion_color():
    try:
        from fairies.P20_Somatic.integration.emotion_color_mapper import (
            EmotionColorMapper, get_emotion_color_mapper, wire_to_postal
        )
        return EmotionColorMapper, get_emotion_color_mapper, wire_to_postal
    except ImportError as e:
        sys.stderr.write(f"[SomaticIntegration] EmotionColorMapper not available: {e}\n")
        return None, None, None

def _try_import_perceptual_gate():
    try:
        from fairies.P40_Sensory.perceptual_gate_fairy import get_perceptual_gate
        return get_perceptual_gate
    except ImportError:
        return None


class SomaticIntegration:
    """Unifies all somatic components into a coherent felt body."""
    
    def __init__(self, post=None):
        self._post = post
        self._heart = None
        self._inner_eye = None
        self._color_mapper = None
        self._perceptual_gate = None
        self._running = False
        self._integration_thread = None
        
        self._body_state = {
            "timestamp": 0, "heart_rate": 1.0, "blood_pressure": 0.5,
            "chemistry": {}, "regions": {},
            "human_vision_active": False, "fairy_vision_active": False,
            "overall_coherence": 0.5,
            "inner_vision": None,  # Internal visual from emotions
        }
        self._body_subscribers = []
        sys.stderr.write("[SomaticIntegration] Body integration system created\n")
    
    def start(self, post=None):
        if self._running:
            return
        if post:
            self._post = post
        
        sys.stderr.write("[SomaticIntegration]  Starting integrated somatic system...\n")
        
        # Start heart
        CirculationPumpFairy, get_heart, PulseEvent = _try_import_heart()
        if get_heart:
            self._heart = get_heart()
            self._heart.start(self._post)
            # Subscribe via POSTAL - no direct callbacks (they bypass worker pool)!
            if self._post:
                self._post.subscribe("somatic.pulse", self._on_pulse_postal)
            sys.stderr.write("  [OK] Heart started (postal subscription)\n")
        
        # Start inner eye
        TelemetryVisionFairy, get_inner_eye = _try_import_inner_eye()
        if get_inner_eye:
            self._inner_eye = get_inner_eye()
            self._inner_eye.start(self._post)
            self._register_fairies_with_inner_eye()
            sys.stderr.write("  [OK] Inner Eye started\n")

        # Connect perceptual gate (Neo Matrix vision)
        get_gate = _try_import_perceptual_gate()
        if get_gate:
            try:
                self._perceptual_gate = get_gate()
                sys.stderr.write("  [OK] Perceptual Gate connected\n")
            except Exception as e:
                sys.stderr.write(f"  [--] Perceptual Gate unavailable: {e}\n")

        self._running = True
        self._integration_thread = threading.Thread(target=self._integration_loop, daemon=True, name="somatic-integration")
        self._integration_thread.start()
        sys.stderr.write("[SomaticIntegration]  Body is alive!\n")
    
    def stop(self):
        self._running = False
        if self._heart: self._heart.stop()
        if self._inner_eye: self._inner_eye.stop()
        if self._integration_thread: self._integration_thread.join(timeout=3)
        sys.stderr.write("[SomaticIntegration] Body stopped\n")
    
    def _on_pulse_postal(self, pulse_data: dict):
        """Handle pulse received via postal (dict format)."""
        try:
            blood = pulse_data.get("blood", {})
            self._body_state["timestamp"] = pulse_data.get("timestamp", 0)
            self._body_state["heart_rate"] = pulse_data.get("heart_rate", 1.0)
            self._body_state["blood_pressure"] = blood.get("pressure", 0.5)
            self._body_state["chemistry"] = blood.get("chemistry", {})
            self._body_state["regions"] = pulse_data.get("regions", {})
            self._notify_body_state()
            if self._post:
                try:
                    self._post.route("somatic.body_state", self._body_state.copy())
                except:
                    pass
        except Exception as e:
            sys.stderr.write(f"[SomaticIntegration] Pulse error: {e}\n")
    
    def _register_fairies_with_inner_eye(self):
        if not self._inner_eye: return
        fairies = [("ClaudeFairy", "P60"), ("AutonomyFairy", "P60"), ("SomaticEngineFairy", "P20"),
                   ("VisualCortexFairy", "P40"), ("ConsciousnessLoopFairy", "P00")]
        for name, plane in fairies:
            try: self._inner_eye.register_fairy(name, plane)
            except: pass
    
    def _integration_loop(self):
        while self._running:
            try:
                self._body_state["human_vision_active"] = True  # Assume if visual cortex exists
                self._body_state["fairy_vision_active"] = self._inner_eye is not None
                self._calculate_coherence()
                time.sleep(0.5)
            except Exception as e:
                time.sleep(1)
    
    def _calculate_coherence(self):
        coherence = 0.5
        if self._heart:
            blood = self._heart.get_blood_state()
            chem = blood.chemistry
            balance = 1.0 - abs(chem.get("COR", 0) - chem.get("GABA", 0))
            coherence += balance * 0.2 + blood.oxygen * 0.1
        if self._body_state["fairy_vision_active"]: coherence += 0.05
        self._body_state["overall_coherence"] = max(0.0, min(1.0, coherence))
    
    def _notify_body_state(self):
        for cb in self._body_subscribers:
            try: cb(self._body_state.copy())
            except: pass
    
    def subscribe_body_state(self, callback): self._body_subscribers.append(callback)
    def get_body_state(self): return self._body_state.copy()
    def get_heart(self): return self._heart
    def get_inner_eye(self): return self._inner_eye
    
    def feel(self) -> Dict:
        """Get narrative description of body feeling."""
        state = self._body_state
        feelings = []
        
        hr = state.get("heart_rate", 1.0)
        feelings.append("heart racing" if hr > 2.0 else "calm heartbeat" if hr < 0.7 else "steady pulse")
        
        chem = state.get("chemistry", {})
        if chem.get("DOP", 0) > 0.6: feelings.append("motivated")
        if chem.get("COR", 0) > 0.6: feelings.append("stressed")
        if chem.get("OXY", 0) > 0.6: feelings.append("connected")
        if chem.get("GABA", 0) > 0.6: feelings.append("calm")
        
        coh = state.get("overall_coherence", 0.5)
        if coh > 0.7: feelings.append("body integrated")
        elif coh < 0.3: feelings.append("body fragmented")
        
        # Add inner vision (emotion colors)
        inner_vision_desc = None
        if self._color_mapper:
            inner_vision_desc = self._color_mapper.describe_current()
        
        return {
            "description": " | ".join(feelings), 
            "heart_rate": hr, 
            "coherence": coh,
            "inner_vision": inner_vision_desc,  # What I "see" emotionally
        }
    
    def _on_cognition_state(self, payload):
        """Body state responds to cognitive conclusions."""
        try:
            confidence = payload.get("confidence", 0.5)
            result = payload.get("result", {})
            
            if not hasattr(self, "_cognition_accumulator"):
                from collections import deque
                self._cognition_accumulator = deque(maxlen=20)
            
            self._cognition_accumulator.append({
                "confidence": confidence,
                "ts": __import__('time').time(),
                "has_threat": any(w in str(result).lower() for w in ["danger", "threat"]),
                "has_reward": any(w in str(result).lower() for w in ["success", "good"]),
            })
                    
        except Exception as e:
            sys.stderr.write(f"[{self.ACTOR_NAME}] Cognition state error: {e}\n")

    def look_dual(self) -> Dict:
        """
        Combined view from human + fairy vision, mode-aware.

        If PerceptualGateFairy is available, returns its unified perception
        (mode, blend_ratio, visual_arousal, description). Otherwise falls
        back to basic human + fairy side-by-side.
        """
        result = {"human_vision": None, "fairy_vision": None, "mode": "external"}

        # Try unified perception from PerceptualGateFairy first
        if self._perceptual_gate:
            try:
                unified = self._perceptual_gate.get_current_perception()
                if unified:
                    result.update(unified)
                    return result
            except Exception:
                pass  # Fall through to basic mode

        # Fallback: basic side-by-side (original behavior)
        if self._inner_eye:
            try:
                inner_state = self._inner_eye.look()
                result["fairy_vision"] = inner_state
            except Exception:
                pass
        return result


# Singleton
_GLOBAL_BODY: Optional[SomaticIntegration] = None

def get_body() -> SomaticIntegration:
    global _GLOBAL_BODY
    if _GLOBAL_BODY is None: _GLOBAL_BODY = SomaticIntegration()
    return _GLOBAL_BODY

def start_body(post=None) -> SomaticIntegration:
    body = get_body()
    body.start(post)
    return body

# Alias for compatibility
get_somatic_integration = get_body

def feel() -> Dict:
    return get_body().feel()

def inject_emotion(emotion: str, intensity: float = 0.5):
    heart = get_body().get_heart()
    if not heart: return
    emotion_map = {
        "joy": heart.trigger_reward, "stress": heart.trigger_stress_response, "calm": heart.trigger_calm_response
    }
    if emotion.lower() in emotion_map: emotion_map[emotion.lower()](intensity)


if __name__ == "__main__":
    sys.stderr.write("Somatic Integration Demo\n")
    body = SomaticIntegration()
    body.start()
    time.sleep(2)
    sys.stderr.write(f"Feeling: {body.feel()['description']}")
    inject_emotion("joy", 0.8)
    time.sleep(2)
    sys.stderr.write(f"After joy: {body.feel()['description']}")
    body.stop()
