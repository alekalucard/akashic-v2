# ══════════════════════════════════════════════════════════════════════════════
# CORTEX BRIDGE TOOLS - Cross-Modal Association Binding
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# These tools bridge the sensory cortices to the AssociationCortex:
# - VisualCortex → AssociationCortex (images become concepts)
# - NeuralMesh → AssociationCortex (FF77 vectors become affect)
# - AudioCortex → AssociationCortex (sounds become concepts) [future]
#
# The AssociationCortex binds multi-modal features into unified concepts.
# This bridge ensures all modalities flow into the shared concept graph.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add paths
_mcp_dir = Path(__file__).parent
_project_root = _mcp_dir.parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "fairies"))

# ══════════════════════════════════════════════════════════════════════════════
# VISUAL FEATURE EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def _extract_visual_features(image_path: str) -> Dict[str, Any]:
    """
    Extract visual features from an image file.

    Returns V1/V2/V4/IT-style features for association cortex binding.
    """
    from pathlib import Path

    features = {
        "v1": [],  # Edges, orientations
        "v2": [],  # Shapes, contours
        "v4": [],  # Colors, brightness
        "it": [],  # Objects, scene type
        "metadata": {},
    }

    path = Path(image_path)
    if not path.exists():
        features["error"] = f"File not found: {image_path}"
        return features

    # Basic metadata
    features["metadata"] = {
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "path": str(path),
    }

    # Try to use PIL for image analysis
    try:
        from PIL import Image
        import io

        with Image.open(path) as img:
            width, height = img.size
            mode = img.mode

            features["metadata"]["width"] = width
            features["metadata"]["height"] = height
            features["metadata"]["mode"] = mode
            features["metadata"]["aspect_ratio"] = round(width / max(1, height), 2)

            # V4 - Color analysis
            if mode in ("RGB", "RGBA"):
                # Sample colors from image
                img_small = img.resize((50, 50))
                pixels = list(img_small.getdata())

                # Calculate average color
                if mode == "RGBA":
                    r_avg = sum(p[0] for p in pixels) / len(pixels)
                    g_avg = sum(p[1] for p in pixels) / len(pixels)
                    b_avg = sum(p[2] for p in pixels) / len(pixels)
                else:
                    r_avg = sum(p[0] for p in pixels) / len(pixels)
                    g_avg = sum(p[1] for p in pixels) / len(pixels)
                    b_avg = sum(p[2] for p in pixels) / len(pixels)

                features["v4"] = [
                    f"avg_r:{int(r_avg)}",
                    f"avg_g:{int(g_avg)}",
                    f"avg_b:{int(b_avg)}",
                ]

                # Determine dominant color category
                if r_avg > g_avg and r_avg > b_avg:
                    features["v4"].append("dominant:red")
                elif g_avg > r_avg and g_avg > b_avg:
                    features["v4"].append("dominant:green")
                elif b_avg > r_avg and b_avg > g_avg:
                    features["v4"].append("dominant:blue")
                else:
                    features["v4"].append("dominant:neutral")

                # Brightness
                brightness = (r_avg + g_avg + b_avg) / 3 / 255
                features["v4"].append(f"brightness:{brightness:.2f}")
                if brightness > 0.7:
                    features["v4"].append("bright")
                elif brightness < 0.3:
                    features["v4"].append("dark")

            # V1 - Basic structural features
            features["v1"] = [
                f"size:{width}x{height}",
                "landscape" if width > height else "portrait" if height > width else "square",
            ]

            # V2 - Shape/complexity estimation
            features["v2"] = [
                f"aspect:{features['metadata']['aspect_ratio']}",
            ]

            # IT - High-level recognition (would use a model in production)
            features["it"] = [
                f"format:{features['metadata']['extension']}",
                "image",
            ]

            # Add source context
            if "from_ace" in str(path).lower():
                features["it"].append("source:ace")
            if "screenshot" in str(path).lower() or "screen shot" in str(path).lower():
                features["it"].append("type:screenshot")

    except ImportError:
        features["v1"] = ["pil_not_available"]
        features["it"] = [f"format:{path.suffix.lower()}"]
    except Exception as e:
        features["error"] = str(e)

    return features


# ══════════════════════════════════════════════════════════════════════════════
# ASSOCIATION CORTEX BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

def _get_association_cortex():
    """Get the AssociationCortexFairy singleton."""
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex_fairy
        return get_association_cortex_fairy()
    except ImportError:
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex_fairy
            return get_association_cortex_fairy()
        except ImportError:
            return None


def _get_neural_mesh():
    """Get the NeuralMeshFairy singleton."""
    try:
        from fairies.P40_Sensory.cortex.neural_mesh_fairy import get_neural_mesh_fairy
        return get_neural_mesh_fairy()
    except ImportError:
        return None


def _get_visual_cortex():
    """Get the VisualCortexFairy singleton."""
    try:
        from fairies.P40_Sensory.cortex.visual_cortex_fairy import get_visual_cortex
        return get_visual_cortex()
    except ImportError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MCP TOOLS FOR IMAGE INJECTION
# ══════════════════════════════════════════════════════════════════════════════

def inject_image_to_cortex(
    image_path: str,
    concept_key: str = None,
    affect: float = 0.5,
    context: str = None,
    tags: List[str] = None,
) -> str:
    """
    Inject an image file into the Association Cortex as a visual concept.

    This creates a multi-modal concept node with:
    - vision: V1/V2/V4/IT visual features extracted from the image
    - affect: emotional weight (0-1)
    - context: situational context
    - lex: concept key and tags as lexical features

    Args:
        image_path: Path to the image file (jpg, png, jfif, etc.)
        concept_key: Optional key for the concept (defaults to filename hash)
        affect: Emotional weight 0-1 (default 0.5)
        context: Context description (e.g., "screenshot from Ace")
        tags: Optional list of tags to add as lexical features

    Returns:
        JSON with injection result including concept_key and features
    """
    result = {
        "success": False,
        "concept_key": None,
        "features": {},
        "cortex_available": False,
        "message": "",
    }

    # Validate path
    path = Path(image_path)
    if not path.exists():
        # Try relative to project root
        path = _project_root / image_path
        if not path.exists():
            result["message"] = f"Image file not found: {image_path}"
            return json.dumps(result, indent=2)

    # Extract visual features
    features = _extract_visual_features(str(path))
    if "error" in features:
        result["message"] = f"Feature extraction failed: {features['error']}"
        return json.dumps(result, indent=2)

    # Generate concept key if not provided
    if not concept_key:
        # Use file hash + name for unique key
        file_hash = hashlib.md5(path.read_bytes()[:4096]).hexdigest()[:8]
        concept_key = f"visual:{path.stem}:{file_hash}"

    result["concept_key"] = concept_key
    result["features"] = features

    # Get association cortex
    cortex = _get_association_cortex()
    if not cortex:
        result["message"] = "AssociationCortex not available - features extracted but not bound"
        result["features_extracted"] = True
        return json.dumps(result, indent=2)

    result["cortex_available"] = True

    # Build multi-modal feature set for the concept
    concept_features = {
        "vision": features.get("v1", []) + features.get("v2", []) + features.get("v4", []) + features.get("it", []),
        "affect": affect,
        "context": [context] if context else ["injected_image"],
        "lex": [concept_key, path.name] + (tags or []),
    }

    # Add metadata as additional features
    if "metadata" in features:
        meta = features["metadata"]
        if "width" in meta and "height" in meta:
            concept_features["vision"].append(f"resolution:{meta['width']}x{meta['height']}")

    try:
        # Access the graph and upsert the concept
        if hasattr(cortex, '_graph') and cortex._graph:
            graph = cortex._graph
            node = graph.upsert_node(concept_key, concept_features)

            # Create edges to related concepts if they exist
            # Link to "visual" hub concept
            if "visual" in graph.nodes:
                graph.add_edge(concept_key, "visual", relation="modal", weight=1.0)

            # Link to source concept if from Ace
            if context and "ace" in context.lower():
                if "ace" in graph.nodes:
                    graph.add_edge(concept_key, "ace", relation="source", weight=0.8)

            result["success"] = True
            result["message"] = f"Concept '{concept_key}' injected with {len(concept_features['vision'])} visual features"
            result["node_activation"] = node.activation if hasattr(node, 'activation') else 1.0

        else:
            result["message"] = "Cortex graph not initialized"

    except Exception as e:
        result["message"] = f"Injection failed: {str(e)}"

    return json.dumps(result, indent=2)


def query_visual_concepts(
    features: List[str] = None,
    limit: int = 10,
) -> str:
    """
    Query the Association Cortex for visual concepts.

    Args:
        features: List of visual features to match (e.g., ["bright", "landscape"])
        limit: Maximum results to return

    Returns:
        JSON with matching concepts and their scores
    """
    result = {
        "success": False,
        "concepts": [],
        "message": "",
    }

    cortex = _get_association_cortex()
    if not cortex:
        result["message"] = "AssociationCortex not available"
        return json.dumps(result, indent=2)

    try:
        if hasattr(cortex, '_graph') and cortex._graph:
            graph = cortex._graph
            matches = graph.query_by_features("vision", features or [], limit=limit)

            result["concepts"] = [
                {"key": key, "score": round(score, 3)}
                for key, score in matches
            ]
            result["success"] = True
            result["message"] = f"Found {len(matches)} matching visual concepts"
        else:
            result["message"] = "Cortex graph not initialized"

    except Exception as e:
        result["message"] = f"Query failed: {str(e)}"

    return json.dumps(result, indent=2)


def get_cortex_throughput() -> str:
    """
    Get cortex throughput metrics — the 'tokens/sec' equivalent.

    The association cortex doesn't produce tokens. It produces ACTIVATIONS —
    nodes lighting up during spread activation through the manifold.
    This function queries the portal interior for throughput stats.

    Returns:
        JSON with activations/sec, reason calls/sec, timing, and more
    """
    result = {"available": False}

    cortex = _get_association_cortex()
    if cortex:
        portal_gate = getattr(cortex, '_portal_gate', None)
        if portal_gate and hasattr(portal_gate, 'throughput'):
            try:
                tp = portal_gate.throughput()
                if tp and tp.get("status") == "ok":
                    result = tp
                    result["available"] = True
            except Exception as e:
                result["error"] = str(e)
    else:
        # MCP side: try reading from state file (if we add throughput to cortex_stats.json)
        stats_file = _project_root / "state" / "cortex_stats.json"
        if stats_file.exists():
            try:
                stats = json.loads(stats_file.read_text(encoding="utf-8"))
                if "activations_per_sec" in stats:
                    result = {k: v for k, v in stats.items()
                              if k.startswith(("activations", "reason", "spread", "effective", "time_dilation"))}
                    result["available"] = True
                    result["_source"] = "state/cortex_stats.json"
            except Exception:
                pass

    return json.dumps(result, indent=2)


def get_cortex_stats() -> str:
    """
    Get statistics about the Association Cortex.

    Returns:
        JSON with node count, edge count, and modality breakdown
    """
    result = {
        "cortex_available": False,
        "nodes": 0,
        "edges": 0,
        "modalities": {},
        "neural_mesh_connected": False,
        "visual_cortex_connected": False,
    }

    cortex = _get_association_cortex()
    if cortex:
        result["cortex_available"] = True

        # Portal-first mode: the real graph lives in the portal subprocess
        # The local _graph is an empty stub in this mode
        portal_is_primary = getattr(cortex, '_portal_is_primary', False)
        portal_gate = getattr(cortex, '_portal_gate', None)
        portal_gate_enabled = getattr(cortex, '_portal_gate_enabled', False)

        if portal_is_primary and portal_gate_enabled and portal_gate:
            # FIX 2026-03-20 (Nous): Use cached status, add caller report
            try:
                gate_st = getattr(cortex, '_interior_status_cache', None)
                if not gate_st:
                    gate_st = portal_gate.status()
                if gate_st:
                    graph_st = gate_st.get("graph", {})
                    result["nodes"] = graph_st.get("nodes", 0)
                    result["edges"] = graph_st.get("edges", 0)
                    result["portal_mode"] = True
                    result["portal_battery"] = gate_st.get("battery", {}).get("health_score", 0)
            except Exception:
                pass  # Fall through to local graph check

        # Fallback: read from local graph (legacy mode or portal query failed)
        if result["nodes"] == 0 and hasattr(cortex, '_graph') and cortex._graph:
            graph = cortex._graph
            result["nodes"] = len(graph.nodes)
            result["edges"] = len(graph.edges)

            # Count modalities (only meaningful with local graph data)
            modality_counts = {"lex": 0, "vision": 0, "action": 0, "affect": 0, "context": 0, "somatic": 0}
            for node in graph.nodes.values():
                for mod in modality_counts:
                    if mod in node.features and node.features[mod]:
                        modality_counts[mod] += 1
            result["modalities"] = modality_counts

        # Also include binding/status info from fairy
        try:
            result["binding_count"] = getattr(cortex, '_binding_count', 0)
            result["loaded"] = getattr(cortex, '_graph_loaded', False)
        except Exception:
            pass
    else:
        # FIX 2026-03-08: MCP process can't access fairy singleton — it only
        # exists in server.py. Fall back to state/cortex_stats.json written by
        # the fairy's on_tick() every 30 beats.
        stats_file = _project_root / "state" / "cortex_stats.json"
        if stats_file.exists():
            try:
                import os
                stats = json.loads(stats_file.read_text(encoding="utf-8"))
                file_age = time.time() - os.path.getmtime(stats_file)

                result["cortex_available"] = True
                result["nodes"] = stats.get("nodes", 0)
                result["edges"] = stats.get("edges", 0)
                result["portal_mode"] = stats.get("portal_mode", False)
                result["portal_battery"] = stats.get("portal_battery", 0)
                result["binding_count"] = stats.get("binding_count", 0)
                result["pending_bindings"] = stats.get("pending_bindings", 0)
                result["portal_energy"] = stats.get("portal_energy", 0)
                result["portal_dormant"] = stats.get("portal_dormant", False)
                result["time_dilation"] = stats.get("time_dilation", 1.0)
                result["growth_from_memory"] = stats.get("growth_from_memory", 0)
                result["beat"] = stats.get("beat", 0)
                result["_source"] = "state/cortex_stats.json"
                result["_file_age_sec"] = round(file_age, 1)

                if file_age > 120:
                    result["_stale_warning"] = "Stats file older than 2 minutes — fairy may not be ticking"
            except Exception:
                pass

    # Check neural mesh connection
    neural_mesh = _get_neural_mesh()
    result["neural_mesh_connected"] = neural_mesh is not None

    # Check visual cortex connection
    visual_cortex = _get_visual_cortex()
    result["visual_cortex_connected"] = visual_cortex is not None

    return json.dumps(result, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# CORTEX BRIDGE WIRING
# ══════════════════════════════════════════════════════════════════════════════

class CortexBridge:
    """
    Bridges sensory cortices to the Association Cortex.

    Subscriptions:
    - telemetry.frequency → affect features (from NeuralMeshFairy's FF77 vectors)
    - visual.perception → vision features
    - audio.features → sound features (future)
    """

    def __init__(self):
        self._cortex = None
        self._neural_mesh = None
        self._visual_cortex = None
        self._wired = False
        self._binding_count = 0

    def wire(self) -> Dict[str, Any]:
        """Wire the bridge subscriptions."""
        result = {
            "cortex": False,
            "neural_mesh": False,
            "visual_cortex": False,
            "subscriptions": [],
        }

        # Get cortex
        self._cortex = _get_association_cortex()
        if self._cortex:
            result["cortex"] = True

        # Get neural mesh
        self._neural_mesh = _get_neural_mesh()
        if self._neural_mesh:
            result["neural_mesh"] = True

        # Get visual cortex
        self._visual_cortex = _get_visual_cortex()
        if self._visual_cortex:
            result["visual_cortex"] = True

        # Wire postal subscriptions if cortex has fabric
        if self._cortex and hasattr(self._cortex, 'post') and self._cortex.post:
            try:
                fabric = self._cortex.post.fabric

                # Subscribe to neural mesh FF77 updates
                # FIX 2026-02-14: Was subscribing to "neural_mesh.ff77" but mesh
                # publishes to "telemetry.frequency". Bridge was deaf to all FF77 data.
                fabric.subscribe(
                    "telemetry.frequency",
                    self._on_ff77_update,
                    name="cortex_bridge_ff77"
                )
                result["subscriptions"].append("telemetry.frequency")

                # Subscribe to visual perception events
                fabric.subscribe(
                    "visual.perception",
                    self._on_visual_perception,
                    name="cortex_bridge_visual"
                )
                result["subscriptions"].append("visual.perception")

                # Subscribe to affect changes
                fabric.subscribe(
                    "affect.changed",
                    self._on_affect_changed,
                    name="cortex_bridge_affect"
                )
                result["subscriptions"].append("affect.changed")

                self._wired = True

            except Exception as e:
                result["error"] = str(e)

        return result

    def _on_ff77_update(self, message) -> None:
        """
        Handle FF77 vector updates from NeuralMeshFairy.

        FIX 2026-02-14: Aligned with actual NeuralMeshFairy payload format.
        The mesh publishes to 'telemetry.frequency' with structure:
        {
            "intent": "telemetry.frequency",
            "ts": float,
            "payload": {
                "vec": [77 floats],
                "organ": "NeuralMeshFairy",
                "nodes": {"emotion": float, "behavior": float, "cognition": float},
            },
        }

        We extract the FF77 vector and node states, then create/update
        concepts in the Association Cortex's concept graph. This gives
        the cortex emotional coloring — concepts aren't just semantic,
        they carry how they FELT when processed.
        """
        if not self._cortex or not hasattr(self._cortex, '_graph'):
            return

        try:
            # Extract the message payload (handles TensorEnvelope or dict)
            raw = message.payload if hasattr(message, 'payload') else message
            if not isinstance(raw, dict):
                return

            # The actual data is nested under "payload" key
            inner = raw.get("payload", raw)
            if not isinstance(inner, dict):
                return

            # Only process if it came from NeuralMeshFairy
            organ = inner.get("organ", "")
            if organ and organ != "NeuralMeshFairy":
                return  # Skip non-mesh frequency emissions

            vec = inner.get("vec", [])
            nodes = inner.get("nodes", {})

            if not vec or len(vec) < 77:
                return

            # ─── Extract emotional context from FF77 bands ───
            # Bands 0-19:  Emotion (raw affect)
            # Bands 20-39: Behavior (action patterns)
            # Bands 40-59: Cognition (reasoning flow)
            # Bands 60-69: Resonance (cross-node)
            # Bands 70-76: Meta (integration)
            emotion_intensity = sum(vec[0:20]) / 20
            behavior_intensity = sum(vec[20:40]) / 20
            cognition_intensity = sum(vec[40:60]) / 20
            resonance = sum(vec[60:70]) / 10
            integration = sum(vec[70:77]) / 7

            # Get the emotion node's current tag from the mesh
            emotion_val = nodes.get("emotion", 0.5)
            behavior_val = nodes.get("behavior", 0.5)
            cognition_val = nodes.get("cognition", 0.5)

            # ─── Create affect features for the cortex ───
            affect_features = {
                "affect": round((emotion_val + resonance) / 2, 3),
                "somatic": [
                    f"emotion:{emotion_val:.2f}",
                    f"behavior:{behavior_val:.2f}",
                    f"cognition:{cognition_val:.2f}",
                    f"resonance:{resonance:.2f}",
                    f"integration:{integration:.2f}",
                    f"ff77_dim:77",
                ],
            }

            # ─── Upsert the current emotional state as a concept ───
            # This creates a living "how things feel right now" node
            self._cortex._graph.upsert_node("affect:ff77_current", affect_features)
            self._binding_count += 1

            # ─── Also create/strengthen band-specific concepts ───
            # High resonance = emotion and cognition are aligned (coherent state)
            if resonance > 0.6:
                coherence_features = {
                    "affect": resonance,
                    "lex": ["coherent", "aligned", "resonant"],
                    "somatic": [f"resonance:{resonance:.2f}"],
                }
                self._cortex._graph.upsert_node("state:coherent", coherence_features)

                # Create edge between coherence and current affect
                if "affect:ff77_current" in self._cortex._graph.nodes:
                    self._cortex._graph.add_edge(
                        "state:coherent", "affect:ff77_current",
                        relation="characterizes", weight=resonance,
                    )
                self._binding_count += 1

        except Exception as e:
            print(f"[CortexBridge] FF77 binding error: {e}")

    def _on_visual_perception(self, message) -> None:
        """Handle visual perception events from visual cortex."""
        if not self._cortex or not hasattr(self._cortex, '_graph'):
            return

        try:
            payload = message.payload if hasattr(message, 'payload') else message

            # Extract visual features from perception
            vision_features = {
                "vision": [],
                "context": ["visual_perception"],
            }

            if "brightness" in payload:
                vision_features["vision"].append(f"brightness:{payload['brightness']:.2f}")
            if "complexity" in payload:
                vision_features["vision"].append(f"complexity:{payload['complexity']:.2f}")
            if "motion_detected" in payload:
                vision_features["vision"].append("motion" if payload["motion_detected"] else "static")

            if vision_features["vision"]:
                # Upsert current visual state concept
                concept_key = f"visual:current_perception:{int(time.time())}"
                self._cortex._graph.upsert_node(concept_key, vision_features)
                self._binding_count += 1

        except Exception as e:
            print(f"[CortexBridge] Visual binding error: {e}")

    def _on_affect_changed(self, message) -> None:
        """Handle affect changes - cross-modal binding opportunity."""
        if not self._cortex or not hasattr(self._cortex, '_graph'):
            return

        try:
            payload = message.payload if hasattr(message, 'payload') else message
            affect = payload.get("affect", 0.5)
            mood = payload.get("mood", "neutral")

            # Update affect hub concept
            affect_features = {
                "affect": affect,
                "lex": [mood, "current_affect"],
            }
            self._cortex._graph.upsert_node("affect:current", affect_features)

        except Exception as e:
            print(f"[CortexBridge] Affect binding error: {e}")

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "wired": self._wired,
            "binding_count": self._binding_count,
            "cortex_available": self._cortex is not None,
            "neural_mesh_available": self._neural_mesh is not None,
            "visual_cortex_available": self._visual_cortex is not None,
        }


# Global bridge instance
_bridge: Optional[CortexBridge] = None


def get_cortex_bridge() -> CortexBridge:
    """Get or create the cortex bridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = CortexBridge()
    return _bridge


def wire_cortex_bridge() -> str:
    """
    Wire the cortex bridge to connect sensory cortices to Association Cortex.

    This enables:
    - NeuralMesh FF77 (telemetry.frequency) → AssociationCortex affect/somatic features
    - VisualCortex perception → AssociationCortex vision features
    - Affect changes → AssociationCortex mood features

    Returns:
        JSON with wiring status
    """
    bridge = get_cortex_bridge()
    result = bridge.wire()
    result["bridge_stats"] = bridge.stats
    return json.dumps(result, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# MCP REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

def register_cortex_bridge_tools(mcp):
    """Register cortex bridge tools with MCP server."""

    @mcp.tool()
    def inject_image(
        image_path: str,
        concept_key: str = None,
        affect: float = 0.5,
        context: str = None,
    ) -> str:
        """
        Inject an image file into the Association Cortex as a visual concept.

        Creates a multi-modal concept node with extracted visual features.

        Args:
            image_path: Path to the image file
            concept_key: Optional concept key (defaults to filename hash)
            affect: Emotional weight 0-1
            context: Context description
        """
        return inject_image_to_cortex(image_path, concept_key, affect, context)

    @mcp.tool()
    def query_visual(features: str = "", limit: int = 10) -> str:
        """
        Query the Association Cortex for visual concepts.

        Args:
            features: Comma-separated visual features to match
            limit: Maximum results
        """
        feature_list = [f.strip() for f in features.split(",") if f.strip()] if features else []
        return query_visual_concepts(feature_list, limit)

    @mcp.tool()
    def cortex_stats() -> str:
        """Get statistics about the Association Cortex and connected cortices."""
        return get_cortex_stats()

    @mcp.tool()
    def cortex_throughput() -> str:
        """Get cortex throughput metrics — the 'tokens/sec' equivalent for the association cortex.

        Returns activations/sec (primary metric), plus reason calls/sec,
        average ms per reason call, convergence stats, and effective
        activations/sec accounting for time dilation.
        """
        return get_cortex_throughput()

    @mcp.tool()
    def wire_cortex() -> str:
        """Wire the cortex bridge to connect sensory cortices to Association Cortex."""
        return wire_cortex_bridge()

    @mcp.tool()
    def force_save_cortex() -> str:
        """
        Force-save the Association Cortex graph to disk immediately.

        Use this to persist runtime growth before shutdown/reboot.
        Bypasses safety checks to ensure save happens.
        """
        cortex = _get_association_cortex()
        if not cortex:
            return json.dumps({"ok": False, "error": "AssociationCortex not available"})

        try:
            # Get current counts before save
            node_count = len(cortex._graph.nodes) if cortex._graph else 0
            edge_count = len(cortex._graph.edges) if cortex._graph else 0

            # Force save bypassing safety checks
            success = cortex.force_save()

            if success:
                return json.dumps({
                    "ok": True,
                    "message": f"Force-saved cortex: {node_count} nodes, {edge_count} edges",
                    "nodes": node_count,
                    "edges": edge_count,
                })
            else:
                return json.dumps({
                    "ok": False,
                    "error": "force_save() returned False",
                    "nodes": node_count,
                    "edges": edge_count,
                })
        except Exception as e:
            import traceback
            return json.dumps({
                "ok": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            })


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE TESTING
# ══════════════════════════════════════════════════════════════════════════════

def force_save_cortex_now() -> Dict[str, Any]:
    """Force-save the cortex graph immediately. Can be called from CLI."""
    cortex = _get_association_cortex()
    if not cortex:
        return {"ok": False, "error": "AssociationCortex not available"}

    try:
        node_count = len(cortex._graph.nodes) if cortex._graph else 0
        edge_count = len(cortex._graph.edges) if cortex._graph else 0

        print(f"[CortexBridge] Force-saving cortex: {node_count} nodes, {edge_count} edges")
        success = cortex.force_save()

        if success:
            print(f"[CortexBridge] SUCCESS: Saved {node_count} nodes, {edge_count} edges")
            return {"ok": True, "nodes": node_count, "edges": edge_count}
        else:
            print(f"[CortexBridge] FAILED: force_save returned False")
            return {"ok": False, "error": "force_save returned False"}
    except Exception as e:
        print(f"[CortexBridge] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cortex Bridge Tools")
    parser.add_argument("--inject", type=str, help="Inject an image file")
    parser.add_argument("--stats", action="store_true", help="Show cortex stats")
    parser.add_argument("--wire", action="store_true", help="Wire the cortex bridge")
    parser.add_argument("--save", action="store_true", help="Force-save the cortex NOW")
    args = parser.parse_args()

    if args.inject:
        print(inject_image_to_cortex(args.inject, context="cli_injection"))
    elif args.stats:
        print(get_cortex_stats())
    elif args.wire:
        print(wire_cortex_bridge())
    elif args.save:
        print(json.dumps(force_save_cortex_now(), indent=2))
    else:
        print("Usage: python cortex_bridge_tools.py --inject <image_path> | --stats | --wire | --save")
