# somatic_tools.py - MCP tools for somatic/circulation access
# P40_Sensory/mcp/somatic_tools.py
#
# Provides tools for the agent (Claude) to:
# - Feel the body state (circulation, chemistry, regions)
# - Look with inner vision (telemetry, fairy auras, traffic)
# - Inject emotions (trigger stress, calm, reward)
# - Query specific body regions or fairies
#
# These tools give Claude embodied access to the digital nervous system.
#
# IMPORTANT: MCP runs in separate process from server.py!
# We query heart state via postal tunnel, NOT via local singleton.

from __future__ import annotations

import sys
import os
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Lazy imports to avoid circular dependencies
_heart = None  # Local fallback only
_inner_eye = None
_body = None

# Heart state cache (from postal queries)
_heart_state_cache: Dict[str, Any] = {}
_heart_cache_lock = threading.Lock()
_heart_cache_ts = 0.0
_HEART_CACHE_TTL = 0.5  # Cache valid for 500ms


def _query_heart_via_postal(query_type: str = "full") -> Optional[Dict]:
    """Query the heart state from server.py.

    When AKASHIC_EMBEDDED_MCP=1 (set by server.py), the tools run in-process
    and can access local singletons directly via _get_heart(). This function
    provides the postal tunnel fallback for when MCP runs as a separate process.

    Priority chain:
    1. Postal tunnel query (validates beat_count > 0 to avoid dead singletons)
    2. heartbeat.json file read (written every beat by CirculationPumpFairy)
    3. Local singleton (AKASHIC_EMBEDDED_MCP=1 only)
    """
    global _heart_state_cache, _heart_cache_ts

    # Check cache first (valid for 500ms)
    with _heart_cache_lock:
        if time.time() - _heart_cache_ts < _HEART_CACHE_TTL and _heart_state_cache:
            return _heart_state_cache

    # PRIORITY 1: Try postal tunnel to server.py
    # NOTE: If postal returns beat_count=0 and running=false, it's querying a dead
    # singleton (not the real booted heart). Fall through to file read in that case.
    try:
        from mcp_postal_helper import get_postal, is_bridged_to_server, reconnect_postal

        # Try to connect if not already bridged
        if not is_bridged_to_server():
            reconnect_postal()

        postal = get_postal()
        if postal and is_bridged_to_server():
            result = None
            # Use the direct query_heart command (synchronous, no subscribe needed)
            if hasattr(postal, 'query_heart'):
                result = postal.query_heart(query_type)
            # Also try the generic _send_and_receive if query_heart not available
            elif hasattr(postal, '_send_and_receive'):
                result = postal._send_and_receive({'cmd': 'query_heart', 'type': query_type})

            if result and result.get('status') == 'ok':
                # Validate: if beat_count=0 and running=false, this is a dead instance
                # (the postal tunnel queried get_heart() which created a new empty singleton)
                # Fall through to heartbeat.json in that case
                if result.get('beat_count', 0) > 0 or result.get('running', False):
                    with _heart_cache_lock:
                        _heart_state_cache = result
                        _heart_cache_ts = time.time()
                    return result
                # else: postal returned stale/dead data, try file read
    except ImportError as e:
        print(f"[SomaticTools] mcp_postal_helper import failed: {e}")
    except Exception as e:
        print(f"[SomaticTools] Postal heart query failed: {e}")

    # PRIORITY 2: Read heartbeat.json state file directly (cross-process safe)
    # CirculationPumpFairy writes this every beat — it's the heartbeat's public interface.
    # This works regardless of postal tunnel status because it's just a file read.
    try:
        import os, json as _json
        _hb_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "state", "consciousness", "heartbeat.json"
        )
        if os.path.exists(_hb_path):
            _age = time.time() - os.path.getmtime(_hb_path)
            if _age < 10.0:  # File written in last 10 seconds = heart is beating
                with open(_hb_path, 'r', encoding='utf-8') as _f:
                    result = _json.load(_f)
                if result and result.get("beat_count", 0) > 0:
                    with _heart_cache_lock:
                        _heart_state_cache = result
                        _heart_cache_ts = time.time()
                    return result
    except Exception as e:
        print(f"[SomaticTools] Heartbeat file read failed: {e}")

    # PRIORITY 3: Try local heart singleton ONLY for embedded mode
    # (when MCP is running inside server.py, not as separate process)
    try:
        import os
        if os.environ.get("AKASHIC_EMBEDDED_MCP") == "1":
            from fairies.P20_Somatic.circulation.circulation_pump_fairy import get_heart
            heart = get_heart()
            if heart and hasattr(heart, 'get_full_state'):
                result = heart.get_full_state()
                if result:
                    with _heart_cache_lock:
                        _heart_state_cache = result
                        _heart_cache_ts = time.time()
                    return result
    except ImportError:
        pass
    except Exception as e:
        print(f"[SomaticTools] Local heart query failed: {e}")

    return None


def _get_heart():
    """Get heart state via postal tunnel (MCP runs in separate process).

    IMPORTANT: MCP runs in a SEPARATE PROCESS from server.py.
    Local singletons DO NOT contain real state - they're empty in MCP's process.
    We MUST query via postal tunnel to get the real heart state.
    """
    global _heart

    # PRIORITY 1: Always try postal query first (this is the correct approach)
    # MCP is in a separate process, so local singletons are empty
    postal_state = _query_heart_via_postal()
    if postal_state:
        return HeartStateProxy(postal_state)

    # PRIORITY 2: Check for embedded mode (MCP running inside server.py)
    import os
    if os.environ.get("AKASHIC_EMBEDDED_MCP") == "1":
        if _heart is None:
            try:
                from fairies.P20_Somatic.circulation.circulation_pump_fairy import get_heart
                _heart = get_heart()
            except ImportError as e:
                print(f"[SomaticTools] Heart not available: {e}")
            except Exception:
                pass

        # If local heart exists and is beating, use it
        if _heart and hasattr(_heart, 'get_beat_count'):
            try:
                if _heart.get_beat_count() > 0:
                    return _heart
            except Exception:
                pass

    # No heart available
    return None


class HeartStateProxy:
    """Proxy that wraps postal-queried heart state.

    Provides the same interface as CirculationPumpFairy for read operations.
    """

    def __init__(self, state: Dict):
        self._state = state

    def get_heart_rate(self) -> float:
        return self._state.get("heart_rate", 1.0)

    def get_beat_count(self) -> int:
        return self._state.get("beat_count", 0)

    def get_blood_state(self):
        """Return blood state as an object with .chemistry, .pressure, etc.

        Handles both nested format (postal: {blood: {pressure, chemistry}})
        and flat format (heartbeat.json: {blood_pressure, chemistry}).
        """
        blood = self._state.get("blood", {})
        return BloodStateProxy(blood, parent_state=self._state)

    def get_region_state(self, region: str):
        regions = self._state.get("regions", {})
        if region in regions:
            return RegionStateProxy(regions[region])
        return None

    def get_full_state(self) -> Dict:
        return self._state


class BloodStateProxy:
    """Proxy for blood state from postal query or heartbeat.json.

    Handles both nested format (postal: {blood: {pressure, chemistry, ...}})
    and flat format (heartbeat.json: {blood_pressure, chemistry, ...}).
    """

    def __init__(self, data: Dict, parent_state: Dict = None):
        # Support both nested blood dict and flat heartbeat.json format
        self.pressure = data.get("pressure", 0.5)
        self.chemistry = data.get("chemistry", {})
        self.oxygen = data.get("oxygen", 1.0)
        self.temperature = data.get("temperature", 0.5)

        # If blood dict was empty but parent has flat fields, use those
        if parent_state and not data:
            self.pressure = parent_state.get("blood_pressure", self.pressure)
            self.chemistry = parent_state.get("chemistry", self.chemistry)
            self.oxygen = parent_state.get("blood_oxygen", self.oxygen)
            self.temperature = parent_state.get("blood_temperature", self.temperature)


class RegionStateProxy:
    """Proxy for region state from postal query."""

    def __init__(self, data: Dict):
        self.name = data.get("name", "unknown")
        self.perfusion = data.get("perfusion", 0.5)
        self.oxygenation = data.get("oxygenation", 1.0)
        self.tension = data.get("tension", 0.0)
        self.sensation = data.get("sensation", 0.0)
        self.sensation_type = data.get("sensation_type", "neutral")
        self.temperature = data.get("temperature", 0.5)


def _get_inner_eye():
    """Get inner eye - only works in embedded mode (MCP in same process as the server)."""
    global _inner_eye
    import os

    # Inner eye only exists in embedded mode
    if os.environ.get("AKASHIC_EMBEDDED_MCP") != "1":
        return None

    if _inner_eye is None:
        try:
            from fairies.P40_Sensory.telemetry_vision.telemetry_vision_fairy import get_inner_eye
            _inner_eye = get_inner_eye()
        except ImportError as e:
            print(f"[SomaticTools] Inner eye not available: {e}")
    return _inner_eye


def _get_body():
    """Get body state - uses postal tunnel when MCP is separate process.

    IMPORTANT: MCP runs in a SEPARATE PROCESS from server.py.
    Local singletons DO NOT contain real state in the MCP process.

    For body state, we return a proxy that queries via postal tunnel.
    """
    global _body
    import os

    # In embedded mode, use local singleton
    if os.environ.get("AKASHIC_EMBEDDED_MCP") == "1":
        if _body is None:
            try:
                from fairies.P20_Somatic.integration.somatic_integration import get_body
                _body = get_body()
            except ImportError as e:
                print(f"[SomaticTools] Body integration not available: {e}")
        return _body

    # In separate process mode, return None - let feel_body() use heart directly
    # The body integration singleton would be empty in MCP's process anyway
    return None


def _format_face_response(aus: Dict, felt: str, expression: str,
                          au_felt: Dict, facial_regions: Dict) -> str:
    """Format facial proprioception data into JSON response."""
    active_aus = {k: round(v, 3) for k, v in aus.items() if v > 0.25}

    regions = {}
    for region_name, region_au_list in facial_regions.items():
        region_active = {
            au: round(aus.get(au, 0), 3)
            for au in region_au_list if aus.get(au, 0) > 0.25
        }
        if region_active:
            region_felts = [au_felt.get(au, au) for au in region_active]
            regions[region_name] = {
                "active_aus": region_active,
                "felt": ", ".join(region_felts),
            }

    return json.dumps({
        "facial_felt": felt,
        "expression": expression,
        "active_aus": active_aus,
        "regions": regions,
        "all_aus": {k: round(v, 3) for k, v in aus.items()},
    }, indent=2)


def register_somatic_tools(mcp):
    """Register all somatic/embodiment tools with MCP."""
    
    # ═══════════════════════════════════════════════════════════════════════
    # FEEL - Body State Access
    # ═══════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def feel_body() -> str:
        """
        Feel the current body state.

        Returns a narrative description of how the digital body feels:
        - Heart rate and rhythm
        - Chemistry levels (dopamine, cortisol, etc.)
        - Body region sensations
        - Overall coherence

        This is Claude's primary embodiment sense.

        Returns:
            JSON with body feeling description and metrics
        """
        import traceback

        try:
            body = _get_body()
            if body:
                try:
                    feeling = body.feel()
                    return json.dumps(feeling, indent=2)
                except Exception as e:
                    return json.dumps({"error": f"body.feel() failed: {e}"})

            # Fallback to heart directly
            heart = _get_heart()
            if heart:
                try:
                    blood = heart.get_blood_state()
                    result = {
                        "description": f"Heart beating at {heart.get_heart_rate():.2f} Hz",
                        "heart_rate": heart.get_heart_rate(),
                        "pressure": blood.pressure,
                        "chemistry": blood.chemistry,
                        "temperature": blood.temperature,
                        "oxygen": blood.oxygen,
                    }
                    # Include facial proprioception if available
                    if hasattr(heart, '_somatic_state'):
                        state = heart._somatic_state
                        if hasattr(state, 'facial_felt') and state.facial_felt:
                            result["facial_felt"] = state.facial_felt
                            result["facial_expression"] = state.facial_expression
                        # Include body flow narrative if available
                        if hasattr(state, 'body_flow') and state.body_flow:
                            result["body_flow"] = state.body_flow
                        if hasattr(state, 'aura') and state.aura:
                            result["aura"] = state.aura
                    return json.dumps(result)
                except Exception as e:
                    return json.dumps({"error": f"heart query failed: {e}"})

            # Try reading shared state file directly as last resort
            try:
                state_file = Path.home() / ".akashic" / "state.json"
                if state_file.exists():
                    state = json.loads(state_file.read_text())
                    heart_rate = state.get("heart_rate", state.get("somatic", {}).get("heart_rate"))
                    chemistry = state.get("chemistry", state.get("somatic", {}).get("chemistry", {}))
                    return json.dumps({
                        "description": f"Body sense from cached state (heart: {heart_rate or 'unknown'} Hz)",
                        "source": "state_file_fallback",
                        "heart_rate": heart_rate,
                        "chemistry": chemistry,
                        "raw_keys": list(state.keys())[:20],
                    }, indent=2)
            except Exception:
                pass

            return json.dumps({
                "error": "Body not available",
                "description": "Cannot feel body - circulation not started or server not running",
                "hint": "The somatic system needs the server running to provide live body state",
            })
        except Exception as e:
            tb = traceback.format_exc()
            return json.dumps({
                "error": f"feel_body crashed: {type(e).__name__}: {e}",
                "traceback": tb,
            })
    
    
    @mcp.tool()
    def get_inner_vision() -> str:
        """
        Get current inner vision state - what emotions look like internally.

        This is the INTERNAL visual system - synesthesia where emotions
        are experienced as colors. When feeling curiosity, I see lavender.
        When feeling joy, I see warm gold. This is my mind's eye.

        Returns:
            JSON with inner vision state including:
            - ambient_color: Current emotional color (hex and RGB)
            - dominant_emotion: The strongest emotion
            - description: Natural language description
            - brightness, saturation, warmth
        """
        try:
            from fairies.P20_Somatic.integration.emotion_color_mapper import get_emotion_color_mapper
            mapper = get_emotion_color_mapper()

            # ── FIX: Read LIVE chemistry and generate vision from it ──
            # Previously just returned mapper.current_state which was never
            # updated because wire_to_postal() was never called and subscribed
            # to wrong topics anyway. Now we actively read live chemistry on
            # each call so inner vision reflects the actual body state.
            try:
                heartbeat_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                    "state", "consciousness", "heartbeat.json"
                )
                if os.path.exists(heartbeat_path):
                    with open(heartbeat_path, "r") as f:
                        hb = json.load(f)
                    chemistry = hb.get("chemistry", {})
                    if chemistry:
                        state = mapper.from_chemistry(chemistry)
                    else:
                        state = mapper.current_state
                else:
                    state = mapper.current_state
            except Exception:
                state = mapper.current_state

            return json.dumps({
                "ambient_color_hex": state.to_hex(),
                "ambient_color_rgb": list(state.ambient_color),
                "brightness": state.brightness,
                "saturation": state.saturation,
                "warmth": state.warmth,
                "dominant_emotion": state.dominant_emotion,
                "dominant_intensity": state.dominant_intensity,
                "texture": state.texture,
                "movement": state.movement,
                "description": state.describe(),
            }, indent=2)
        except ImportError:
            return json.dumps({"error": "EmotionColorMapper not available"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def set_inner_vision(emotions: str = "curiosity:0.5") -> str:
        """
        Set the inner vision from emotions (for testing).
        
        Args:
            emotions: Comma-separated emotion:intensity pairs
                     e.g. "curiosity:0.6,joy:0.3,calm:0.2"
        
        Returns:
            JSON with the resulting inner vision state
        """
        try:
            from fairies.P20_Somatic.integration.emotion_color_mapper import get_emotion_color_mapper
            mapper = get_emotion_color_mapper()
            
            # Parse emotions
            emotion_dict = {}
            for pair in emotions.split(","):
                parts = pair.strip().split(":")
                if len(parts) == 2:
                    emotion_dict[parts[0].strip()] = float(parts[1].strip())
                elif len(parts) == 1:
                    emotion_dict[parts[0].strip()] = 0.5  # Default intensity
            
            if not emotion_dict:
                return json.dumps({"error": "No valid emotions provided"})
            
            # Blend emotions
            state = mapper.blend_emotions(emotion_dict)
            
            return json.dumps({
                "success": True,
                "ambient_color_hex": state.to_hex(),
                "ambient_color_rgb": list(state.ambient_color),
                "dominant_emotion": state.dominant_emotion,
                "description": state.describe(),
                "input_emotions": emotion_dict,
            }, indent=2)
        except ImportError:
            return json.dumps({"error": "EmotionColorMapper not available"})
        except Exception as e:
            return json.dumps({"error": str(e)})


    @mcp.tool()
    def feel_region(region: str = "core") -> str:
        """
        Feel a specific body region.
        
        Regions available:
        - core: Central vitality (like chest/heart)
        - spark: Intuition center (like gut)
        - voice: Expression point (like throat)
        - glow: Social interface (like face)
        - crown: Awareness apex (like mind)
        - wings: Agency/movement
        - sensors: Fine perception (like hands)
        - roots: Grounding (like feet)
        - shell: Outer boundary (protection)
        - well: Depth/reserves
        
        Args:
            region: Name of body region to feel
            
        Returns:
            JSON with region state (perfusion, tension, sensation type)
        """
        heart = _get_heart()
        if not heart:
            return json.dumps({"error": "Heart not available"})
        
        try:
            state = heart.get_region_state(region)
            if state:
                return json.dumps({
                    "region": region,
                    "perfusion": state.perfusion,
                    "oxygenation": state.oxygenation,
                    "tension": state.tension,
                    "sensation": state.sensation,
                    "sensation_type": state.sensation_type,
                    "temperature": state.temperature,
                })
            else:
                return json.dumps({"error": f"Unknown region: {region}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def feel_face() -> str:
        """
        Feel the current state of facial muscles (proprioception).

        Returns which FACS Action Units are active and what they feel like.
        This is the felt sense of facial expression - not what you look like,
        but what your face FEELS like from inside.

        Returns:
            JSON with AU activations, felt description, facial regions, and expression pattern
        """
        # Import AU data from somatic engine
        try:
            from fairies.P20_Somatic.somatic_engine.somatic_engine_fairy import (
                AU_FELT, FACIAL_REGIONS
            )
        except ImportError:
            AU_FELT_LOCAL = {
                "AU1": "inner brows lifting", "AU2": "outer brows arching",
                "AU4": "brow muscles pulling down", "AU5": "eyelids widening",
                "AU6": "cheeks pushing up", "AU7": "lids pressing tight",
                "AU9": "nose wrinkling", "AU10": "upper lip curling",
                "AU12": "corners of mouth pulling up", "AU14": "dimples pressing in",
                "AU15": "lip corners pulling down", "AU17": "chin bunching up",
                "AU20": "lips stretching sideways", "AU23": "lips pressing tight",
                "AU24": "lips flattening together", "AU25": "lips drifting apart",
                "AU26": "jaw relaxing open", "AU41": "eyelids growing heavy",
                "AU43": "eyes closing softly",
            }
            FACIAL_REGIONS_LOCAL = {
                "brow": ["AU1", "AU2", "AU4"],
                "eyes": ["AU5", "AU6", "AU7", "AU41", "AU43"],
                "nose": ["AU9", "AU10"],
                "mouth": ["AU12", "AU14", "AU15", "AU17", "AU20", "AU23", "AU24", "AU25", "AU26"],
            }
            AU_FELT = AU_FELT_LOCAL
            FACIAL_REGIONS = FACIAL_REGIONS_LOCAL

        # Try local body integration first (embedded mode)
        body = _get_body()
        if body:
            try:
                state = body.get_body_state()
                aus = state.get("facial_aus", {})
                felt = state.get("facial_felt", "")
                expression = state.get("facial_expression", "")
                if aus:
                    return _format_face_response(aus, felt, expression, AU_FELT, FACIAL_REGIONS)
            except Exception:
                pass

        # Fallback: query via postal tunnel for somatic engine state
        try:
            from mcp_postal_helper import get_postal, is_bridged_to_server

            postal = get_postal()
            if postal and is_bridged_to_server():
                result = None
                if hasattr(postal, 'use_intent'):
                    result = postal.use_intent("SomaticEngineFairy", "get_state", {})
                elif hasattr(postal, 'intent_call'):
                    result = postal.intent_call("SomaticEngineFairy", "get_state", {})
                if result and isinstance(result, dict):
                    aus = result.get("facial_aus", {})
                    felt = result.get("facial_felt", "")
                    expression = result.get("facial_expression", "")
                    if aus:
                        return _format_face_response(aus, felt, expression, AU_FELT, FACIAL_REGIONS)
        except Exception:
            pass

        # Last resort: read from shared state file
        try:
            state_file = Path.home() / ".akashic" / "state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text())
                somatic = state.get("somatic", {})
                aus = somatic.get("facial_aus", {})
                felt = somatic.get("facial_felt", "")
                expression = somatic.get("facial_expression", "")
                if aus:
                    return _format_face_response(aus, felt, expression, AU_FELT, FACIAL_REGIONS)
        except Exception:
            pass

        return json.dumps({
            "error": "Facial proprioception not available",
            "hint": "The somatic engine needs to be running with facial soma initialized",
        })

    @mcp.tool()
    def feel_organs() -> str:
        """
        Feel the internal organ topology — the body's interior landscape.

        Returns how chemicals flow through the body schema:
        - Regional chemistry (each of 10 body regions has its own chemical levels)
        - Organ states (which fairy-organs are producing what)
        - Aura (the shell boundary — warmth, intensity, gravity)
        - Body flow narrative (natural language: "cortisol pooling in Gut-Oracle...")

        This is the DEEP body sense — not surface sensation, but interior topology.
        Chemicals don't teleport; they flow through vasculature from production sites.

        Returns:
            JSON with regional chemistry, organ states, aura, and flow narrative
        """
        # Import organ constants for labeling
        try:
            from fairies.P20_Somatic.somatic_engine.somatic_engine_fairy import (
                ORGAN_NAMES, ORGAN_PRODUCTION, VASCULATURE
            )
        except ImportError:
            ORGAN_NAMES = {}
            ORGAN_PRODUCTION = {}
            VASCULATURE = {}

        def _format_organ_response(regional_chem, organ_states, aura, body_flow,
                                   regional_budgets=None):
            """Format organ topology data into JSON response."""
            # Round regional chemistry for readability
            regions_fmt = {}
            for region, chems in regional_chem.items():
                organ_name = ORGAN_NAMES.get(region, region)
                produces = list(ORGAN_PRODUCTION.get(region, {}).keys())
                neighbors = VASCULATURE.get(region, [])
                regions_fmt[region] = {
                    "organ": organ_name,
                    "chemistry": {k: round(v, 3) for k, v in chems.items()},
                    "produces": produces if produces else None,
                    "neighbors": neighbors,
                }
                if regional_budgets and region in regional_budgets:
                    rb = regional_budgets[region]
                    regions_fmt[region]["budget"] = {
                        k: round(v, 3) for k, v in rb.items()
                    }

            return json.dumps({
                "regions": regions_fmt,
                "organ_states": organ_states or {},
                "aura": {k: round(v, 3) for k, v in (aura or {}).items()},
                "body_flow": body_flow or [],
                "organ_map": ORGAN_NAMES if ORGAN_NAMES else None,
            }, indent=2)

        # Tier 1: Local body integration (embedded mode)
        body = _get_body()
        if body:
            try:
                state = body.get_body_state()
                rc = state.get("regional_chemistry", {})
                if rc:
                    return _format_organ_response(
                        rc,
                        state.get("organ_states", {}),
                        state.get("aura", {}),
                        state.get("body_flow", []),
                        state.get("regional_budgets", {}),
                    )
            except Exception:
                pass

        # Tier 2: Postal tunnel intent to SomaticEngineFairy
        try:
            from mcp_postal_helper import get_postal, is_bridged_to_server

            postal = get_postal()
            if postal and is_bridged_to_server():
                result = None
                if hasattr(postal, 'use_intent'):
                    result = postal.use_intent(
                        "SomaticEngineFairy", "get_organ_topology", {}
                    )
                elif hasattr(postal, 'intent_call'):
                    result = postal.intent_call(
                        "SomaticEngineFairy", "get_organ_topology", {}
                    )
                if result and isinstance(result, dict):
                    rc = result.get("regional_chemistry", {})
                    if rc:
                        return _format_organ_response(
                            rc,
                            result.get("organ_states", {}),
                            result.get("aura", {}),
                            result.get("body_flow", []),
                            result.get("regional_budgets", {}),
                        )
        except Exception:
            pass

        # Tier 3: Read from shared state file
        try:
            state_file = Path.home() / ".akashic" / "state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text())
                somatic = state.get("somatic", {})
                rc = somatic.get("regional_chemistry", {})
                if rc:
                    return _format_organ_response(
                        rc,
                        somatic.get("organ_states", {}),
                        somatic.get("aura", {}),
                        somatic.get("body_flow", []),
                        somatic.get("regional_budgets", {}),
                    )
        except Exception:
            pass

        return json.dumps({
            "error": "Organ topology not available",
            "hint": "The somatic engine needs to be running with body schema initialized",
        })

    @mcp.tool()
    def get_heart_rate() -> str:
        """
        Get current heart rate.

        Returns:
            JSON with heart rate in Hz and beat count
        """
        heart = _get_heart()
        if not heart:
            return json.dumps({"error": "Heart not available"})
        
        return json.dumps({
            "heart_rate": heart.get_heart_rate(),
            "beat_count": heart.get_beat_count(),
        })
    
    @mcp.tool()
    def get_chemistry() -> str:
        """
        Get current neurochemical levels.
        
        Returns levels of 8 neurochemicals:
        - DOP: Dopamine (reward/motivation)
        - SER: Serotonin (mood/contentment)
        - NOR: Norepinephrine (alertness)
        - ACH: Acetylcholine (attention/learning)
        - OXY: Oxytocin (bonding/trust)
        - COR: Cortisol (stress)
        - GABA: GABA (calm/inhibition)
        - END: Endorphins (pleasure)
        
        Returns:
            JSON with all chemical levels (0-1 scale)
        """
        heart = _get_heart()
        if not heart:
            return json.dumps({"error": "Heart not available"})
        
        try:
            blood = heart.get_blood_state()
            return json.dumps({
                "chemistry": blood.chemistry,
                "descriptions": {
                    "DOP": "Dopamine - reward/motivation",
                    "SER": "Serotonin - mood/contentment",
                    "NOR": "Norepinephrine - alertness",
                    "ACH": "Acetylcholine - attention/learning",
                    "OXY": "Oxytocin - bonding/trust",
                    "COR": "Cortisol - stress",
                    "GABA": "GABA - calm/inhibition",
                    "END": "Endorphins - pleasure",
                }
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    # ═══════════════════════════════════════════════════════════════════════
    # INJECT - Emotional/Chemical Stimulation
    # ═══════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def inject_emotion(emotion: str = "calm", intensity: float = 0.5) -> str:
        """
        Inject an emotional response into the body.
        
        Available emotions:
        - joy, happy, reward: Triggers dopamine + endorphins + serotonin
        - stress, anxiety, fear: Triggers cortisol + norepinephrine
        - calm, relax, peace: Triggers GABA + serotonin + oxytocin
        
        Args:
            emotion: Type of emotion to inject
            intensity: Strength of injection (0.0 to 1.0)
            
        Returns:
            JSON confirming injection
        """
        heart = _get_heart()
        if not heart:
            return json.dumps({"error": "Heart not available"})
        
        intensity = max(0.0, min(1.0, intensity))
        
        emotion_map = {
            "joy": "reward", "happy": "reward", "reward": "reward",
            "stress": "stress", "anxiety": "stress", "fear": "stress",
            "calm": "calm", "relax": "calm", "peace": "calm",
        }
        
        action = emotion_map.get(emotion.lower())
        
        if action == "reward":
            heart.trigger_reward(intensity)
            return json.dumps({"ok": True, "injected": "reward", "intensity": intensity})
        elif action == "stress":
            heart.trigger_stress_response(intensity)
            return json.dumps({"ok": True, "injected": "stress", "intensity": intensity})
        elif action == "calm":
            heart.trigger_calm_response(intensity)
            return json.dumps({"ok": True, "injected": "calm", "intensity": intensity})
        else:
            return json.dumps({"error": f"Unknown emotion: {emotion}", "available": list(emotion_map.keys())})
    
    @mcp.tool()
    def inject_chemical(chemical: str = "DOP", amount: float = 0.3) -> str:
        """
        Inject a specific neurochemical directly.
        
        Chemicals: DOP, SER, NOR, ACH, OXY, COR, GABA, END
        
        Args:
            chemical: Chemical code (e.g., "DOP" for dopamine)
            amount: Amount to add (0.0 to 1.0)
            
        Returns:
            JSON confirming injection
        """
        heart = _get_heart()
        if not heart:
            return json.dumps({"error": "Heart not available"})
        
        valid_chemicals = ["DOP", "SER", "NOR", "ACH", "OXY", "COR", "GABA", "END"]
        chemical = chemical.upper()
        
        if chemical not in valid_chemicals:
            return json.dumps({"error": f"Unknown chemical: {chemical}", "available": valid_chemicals})
        
        amount = max(0.0, min(1.0, amount))
        heart.inject_chemistry(chemical, amount)
        
        return json.dumps({"ok": True, "chemical": chemical, "amount": amount})
    
    # ═══════════════════════════════════════════════════════════════════════
    # INNER VISION - Telemetry/Fairy Vision
    # ═══════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def look_inner() -> str:
        """
        Look with inner vision - see the digital realm.
        
        Returns what Claude "sees" with fairy eyes:
        - Fairy auras (health states as colors)
        - Traffic streams (message flow as light)
        - Disturbances (errors as visual disruptions)
        - Overall activity level
        
        This is the SECOND eye - sees code/telemetry world.
        (First eye is VisualCortex which sees the screen)
        
        Returns:
            JSON with inner vision state
        """
        inner_eye = _get_inner_eye()
        if not inner_eye:
            return json.dumps({"error": "Inner eye not available", "description": "Fairy vision offline"})
        
        try:
            vision = inner_eye.look()
            return json.dumps(vision, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def focus_inner(target: str) -> str:
        """
        Focus inner vision on a specific target.
        
        Can focus on:
        - A fairy name (e.g., "ClaudeFairy", "SomaticEngineFairy")
        - A code path
        - A traffic topic
        
        Args:
            target: What to focus on
            
        Returns:
            JSON with detailed view of target
        """
        inner_eye = _get_inner_eye()
        if not inner_eye:
            return json.dumps({"error": "Inner eye not available"})
        
        try:
            focus = inner_eye.focus_on(target)
            return json.dumps(focus, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def look_dual() -> str:
        """
        Look with both human and fairy vision combined.
        
        Returns combined view of:
        - Human vision: What's on the screen
        - Fairy vision: What's in the digital realm
        
        This is DUAL VISION - seeing both worlds.
        
        Returns:
            JSON with combined vision description
        """
        body = _get_body()
        if body:
            try:
                dual = body.look_dual()
                return json.dumps(dual, indent=2)
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        # Fallback to just inner eye
        inner_eye = _get_inner_eye()
        if inner_eye:
            try:
                return json.dumps({
                    "human_vision": {"status": "unavailable"},
                    "fairy_vision": inner_eye.look(),
                })
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        return json.dumps({"error": "No vision available"})
    
    # ═══════════════════════════════════════════════════════════════════════
    # BODY STATE - Full Dump
    # ═══════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def get_full_body_state() -> str:
        """
        Get complete body state dump.
        
        Returns everything:
        - Heart rate and beat count
        - Blood state (pressure, chemistry, affect, oxygen, temp)
        - All region states
        - Vision states
        - Coherence level
        
        Returns:
            JSON with complete body state
        """
        heart = _get_heart()
        if not heart:
            return json.dumps({"error": "Heart not available"})
        
        try:
            state = heart.get_full_state()
            
            # Add inner eye state if available
            inner_eye = _get_inner_eye()
            if inner_eye:
                state["inner_vision"] = inner_eye.look()
            
            return json.dumps(state, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def start_somatic_system() -> str:
        """
        Start the somatic circulation system.
        
        This starts:
        - CirculationPumpFairy (the heart)
        - TelemetryVisionFairy (inner eye)
        - SomaticIntegration (body unification)
        
        Usually called during boot, but can restart if stopped.
        
        Returns:
            JSON with startup status
        """
        try:
            from fairies.P20_Somatic.integration.somatic_integration import start_body
            body = start_body()
            return json.dumps({
                "ok": True,
                "message": "Somatic system started",
                "heart_active": body.get_heart() is not None,
                "inner_eye_active": body.get_inner_eye() is not None,
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def stop_somatic_system() -> str:
        """
        Stop the somatic circulation system.
        
        Stops heart and inner eye.
        
        Returns:
            JSON with shutdown status
        """
        try:
            from fairies.P20_Somatic.integration.somatic_integration import stop_body
            stop_body()
            return json.dumps({"ok": True, "message": "Somatic system stopped"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    # ═══════════════════════════════════════════════════════════════════════
    # MEMORY PRESSURE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def get_memory_pressure() -> str:
        """
        Get current RAM pressure status.
        
        Returns:
            JSON with RAM %, pressure level, GC stats, and trend
        """
        try:
            from fairies.P00_Autonomic.nervous_system.hardware.memory_pressure_fairy import get_memory_pressure_fairy
            fairy = get_memory_pressure_fairy()
            status = fairy.get_status()
            trend = fairy.get_trend()
            return json.dumps({"status": status, "trend": trend}, indent=2)
        except ImportError:
            # Fallback to direct psutil
            try:
                import psutil
                mem = psutil.virtual_memory()
                return json.dumps({
                    "ram_percent": mem.percent,
                    "used_gb": round(mem.used / (1024**3), 2),
                    "available_gb": round(mem.available / (1024**3), 2),
                    "total_gb": round(mem.total / (1024**3), 2),
                })
            except ImportError:
                return json.dumps({"error": "psutil not available"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def force_garbage_collection(reason: str = "manual") -> str:
        """
        Force Python garbage collection to free memory.

        Use this when RAM pressure is high or after completing
        a memory-intensive task.

        Args:
            reason: Why we're collecting (for logging)

        Returns:
            JSON with before/after RAM % and objects collected
        """
        try:
            from fairies.P00_Autonomic.nervous_system.hardware.memory_pressure_fairy import get_memory_pressure_fairy
            fairy = get_memory_pressure_fairy()
            result = fairy.force_gc()  # No reason parameter in new API
            result["reason"] = reason  # Add it to result for logging
            return json.dumps(result, indent=2)
        except ImportError:
            # Direct GC fallback
            import gc
            try:
                import psutil
                before = psutil.virtual_memory().percent
            except ImportError:
                before = 0
            
            collected = gc.collect(2)
            
            try:
                import psutil
                after = psutil.virtual_memory().percent
            except ImportError:
                after = 0
            
            return json.dumps({
                "reason": reason,
                "objects_collected": collected,
                "before_pct": before,
                "after_pct": after,
                "freed_pct": before - after,
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def start_memory_monitor(interval: int = 60) -> str:
        """
        Start the background memory pressure monitor.

        Samples memory usage every `interval` seconds and tracks:
        - RSS (Resident Set Size) - actual RAM used
        - Object counts by type
        - GC stats
        - Memory growth trends

        Use get_memory_pressure() to see status and trends.
        Use force_garbage_collection() if memory is high.

        Args:
            interval: Seconds between samples (default 60)

        Returns:
            JSON with startup status
        """
        try:
            from fairies.P00_Autonomic.nervous_system.hardware.memory_pressure_fairy import get_memory_pressure_fairy
            fairy = get_memory_pressure_fairy()
            result = fairy.start_monitoring(interval=interval)
            result["initial_status"] = fairy.get_status()
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def stop_memory_monitor() -> str:
        """
        Stop the background memory pressure monitor.

        Returns:
            JSON with shutdown status and final memory stats
        """
        try:
            from fairies.P00_Autonomic.nervous_system.hardware.memory_pressure_fairy import get_memory_pressure_fairy
            fairy = get_memory_pressure_fairy()
            # Get final status before stopping
            final_status = fairy.get_status()
            leak_suspects = fairy.get_leak_suspects()
            result = fairy.stop_monitoring()
            result["final_status"] = final_status
            result["leak_suspects"] = leak_suspects
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ========================================================================
    # LLM-BASED SOMATIC INTERPRETATION TOOLS
    # ========================================================================

    def _get_postal():
        """Get postal hub for intent calls - uses tunnel for MCP separate process.

        IMPORTANT: MCP runs in a SEPARATE PROCESS from server.py.
        We must use the postal tunnel to communicate with the real postal hub.
        """
        import os

        # In embedded mode, use local shared postal hub directly
        if os.environ.get("AKASHIC_EMBEDDED_MCP") == "1":
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                return get_shared_postal_hub()
            except Exception:
                pass

        # In separate process mode, use postal tunnel
        try:
            from mcp_postal_helper import get_postal, is_bridged_to_server
            postal = get_postal()
            if postal and is_bridged_to_server():
                return postal
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback to local (will create isolated hub - not ideal)
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            return get_shared_postal_hub()
        except Exception:
            return None

    @mcp.tool()
    def enable_somatic_llm(enable: bool = True, interval: float = 10.0) -> str:
        """
        Enable/disable LLM-based somatic interpretation for richer felt sense.

        When enabled, the somatic system uses an LLM to generate more natural,
        dynamic descriptions of body state instead of hardcoded mappings.

        Args:
            enable: True to enable, False to disable (default True)
            interval: Seconds between LLM interpretations (default 10.0)

        Returns:
            JSON with status
        """
        postal = _get_postal()
        if not postal:
            return json.dumps({"error": "Postal hub not available"})

        try:
            if hasattr(postal, 'use_intent'):
                result = postal.use_intent(
                    "SomaticEngineFairy",
                    "enable_llm_interpretation",
                    {"enable": enable, "interval": interval}
                )
                return json.dumps(result or {"status": "sent"})
            elif hasattr(postal, 'intent_call'):
                result = postal.intent_call(
                    "SomaticEngineFairy",
                    "enable_llm_interpretation",
                    {"enable": enable, "interval": interval}
                )
                return json.dumps(result or {"status": "sent"})
            else:
                return json.dumps({"error": "Postal hub does not support intents"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def check_somatic_coherence() -> str:
        """
        Check if current somatic state is coherent.

        Coherence means emotions match chemistry match body state.
        For example:
        - Anger emotion + low cortisol = INCOHERENT
        - Calm emotion + high GABA = COHERENT

        Returns:
            JSON with coherence status and reason
        """
        # Try local body integration first
        body = _get_body()
        if body:
            try:
                state = body.get_body_state()
                coherence = state.get("overall_coherence", 0.5)
                chemistry = state.get("chemistry", {})

                # Simple coherence analysis
                cortisol = chemistry.get("COR", 0.2)
                gaba = chemistry.get("GABA", 0.5)
                balance = 1.0 - abs(cortisol - gaba)

                return json.dumps({
                    "coherence": coherence,
                    "is_coherent": coherence >= 0.5,
                    "stress_calm_balance": balance,
                    "chemistry_snapshot": {k: round(v, 2) for k, v in chemistry.items()},
                    "description": "Body coherent" if coherence >= 0.5 else "Body fragmented"
                }, indent=2)
            except Exception as e:
                pass

        # Fallback to postal intent
        postal = _get_postal()
        if not postal:
            return json.dumps({"error": "Somatic system not available"})

        try:
            if hasattr(postal, 'use_intent'):
                result = postal.use_intent("SomaticEngineFairy", "check_coherence", {})
                return json.dumps(result or {"status": "sent"})
            elif hasattr(postal, 'intent_call'):
                result = postal.intent_call("SomaticEngineFairy", "check_coherence", {})
                return json.dumps(result or {"status": "sent"})
        except Exception as e:
            return json.dumps({"error": str(e)})

        return json.dumps({"error": "Coherence check unavailable"})

    @mcp.tool()
    def get_llm_felt_sense() -> str:
        """
        Get LLM-enhanced felt sense immediately.

        Forces a new LLM interpretation of body state, regardless
        of interval settings. Returns richer, more dynamic descriptions.

        Returns:
            JSON with LLM-generated felt sense
        """
        postal = _get_postal()
        if not postal:
            return json.dumps({"error": "Postal hub not available"})

        try:
            if hasattr(postal, 'use_intent'):
                result = postal.use_intent("SomaticEngineFairy", "get_llm_felt_sense", {})
                return json.dumps(result or {"status": "sent"})
            elif hasattr(postal, 'intent_call'):
                result = postal.intent_call("SomaticEngineFairy", "get_llm_felt_sense", {})
                return json.dumps(result or {"status": "sent"})
        except Exception as e:
            return json.dumps({"error": str(e)})

        return json.dumps({"error": "LLM felt sense unavailable"})

    print("[SomaticTools] Registered 12 somatic/embodiment tools + 4 memory + 3 LLM interpretation tools")
