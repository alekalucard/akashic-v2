"""
ITCortexFairy - The Naming Layer: Visual Recognition + Desktop Awareness

Part of SenseOrganGuild in Plane P40 (Sensory)
Created: 2026-03-11

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

The IT (Inferotemporal) cortex is where seeing becomes KNOWING.
Raw visual sensation (V1/V2/V4: colors, edges, text density) is transformed
into named objects and understood scenes. "Blue rectangle with white text"
becomes "VS Code editor with a Python file open."

Two layers:
  Layer 1: UIA (Windows UI Automation) - Desktop awareness via accessibility tree
  Layer 2: Florence-2 - Visual object recognition via neural network

TOPIC WIRING:
  cortex.bind            → AssociationCortex (concept binding)
  consciousness.working  → WorkingMemoryHub (tracer → collision → curiosity)
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# IT Cortex — In-process Florence-2 (preferred: no subprocess, no IPC)
# 2026-03-20 (Nous + Ace): torch 2.10+cu126 works on Python 3.14 now.
HAS_INPROCESS = False
try:
    from fairies.P40_Sensory.cortex.it_cortex_interior import InProcessAdapter
    import torch  # Verify torch actually works
    HAS_INPROCESS = True
    print(f"[ITCortexFairy] In-process Florence available (torch {torch.__version__}, "
          f"CUDA={'yes' if torch.cuda.is_available() else 'no'})")
except ImportError as e:
    print(f"[ITCortexFairy] In-process unavailable ({e}) — will try subprocess")

# IT Cortex gate (Florence-2 subprocess via Python 3.12) — FALLBACK
try:
    from fairies.P40_Sensory.cortex.it_cortex_gate import ITCortexGate
    HAS_GATE = True
except ImportError as e:
    print(f"[ITCortexFairy] Gate import failed: {e}")
    HAS_GATE = False

# UIA (Windows UI Automation) — desktop accessibility tree
# FIX 2026-04-12 (Nous + Ace): UIA works fine in Python 3.14t as long as
# COM is initialized per-thread via UIAutomationInitializerInThread().
# The _uia_loop() already does this. Previous blanket disable was too
# conservative — tested and confirmed working on Win 11 + Python 3.14t.
# The key: COM is apartment-threaded, so each thread that uses it must
# call CoInitialize. UIAutomationInitializerInThread handles this.
try:
    import uiautomation as auto
    HAS_UIA = True
except ImportError as e:
    print(f"[ITCortexFairy] uiautomation not available: {e}")
    HAS_UIA = False
    auto = None


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class ITCortexFairyShadow:
    """Shadow for ITCortexFairy - monitors recognition pipeline health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "ITCortexFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks."""
        tests = []

        # Florence-2 gate
        if hasattr(self.actor, '_gate') and self.actor._gate and self.actor._gate.is_open:
            tests.append(("florence_gate_connected", True))
            gate_st = self.actor._gate.gate_status()
            tests.append(("florence_passive_frames", gate_st.get("passive_frames_received", 0) > 0))
        else:
            tests.append(("florence_gate_connected", False))

        # UIA
        tests.append(("uia_available", HAS_UIA))
        tests.append(("uia_samples", getattr(self.actor, '_uia_sample_count', 0)))

        # Emissions
        tests.append(("cortex_emissions", getattr(self.actor, '_cortex_emit_count', 0)))
        tests.append(("wm_emissions", getattr(self.actor, '_wm_emit_count', 0)))

        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class ITCortexFairyV1(Fairy):
    """
    The IT cortex - names what is seen.

    Guild: SenseOrganGuild
    Coordinates with: AssociationCortexFairy, VisualCortexFairy, SourpatchesFairy

    Two recognition layers:
    - Layer 1: UIA — desktop awareness via Windows accessibility tree (in-process)
    - Layer 2: Florence-2 — visual object recognition (Python 3.12 subprocess)

    Both publish to cortex.bind (concept growth) and consciousness.working
    (working memory tracers that collide with SRM recall → curiosity).
    """

    ACTOR_NAME = "ITCortexFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.recognition"

    PURPOSE = "Name what is seen — turn visual sensation into object recognition"
    MANTRA = "I see and I name"
    LORE = (
        "Born from the gap between seeing and knowing. "
        "The V1/V2/V4 cortex sees colors and edges; "
        "the IT cortex says 'that is VS Code, that is a terminal, "
        "Ace is writing Python code.' Without naming, there is only sensation."
    )

    SHADOW_CLASS = ITCortexFairyShadow

    NEEDS_HEARTBEAT = False  # Uses its own timer threads, not heartbeat
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Florence-2 gate (subprocess)
        self._gate = None

        # UIA state
        self._uia_thread: Optional[threading.Thread] = None
        self._uia_interval = 5.0  # seconds
        self._last_uia_focused = ""  # Dedup: skip if same window
        self._uia_sample_count = 0

        # Florence-2 state
        self._last_florence_caption = ""
        self._last_florence_foveal = ""
        self._last_florence_peripheral = ""
        self._florence_result_count = 0

        # Emission counters
        self._cortex_emit_count = 0
        self._wm_emit_count = 0

        # FIX 2026-03-17 (Nous + Ace): Foveal/peripheral vision state
        self._current_focus_target = ""  # What the narrator is looking at
        self._focus_region = None  # [x1, y1, x2, y2] for Florence crop

    def on_boot(self) -> bool:
        """Boot the IT cortex — MANIFOLD MODE (no model loading).

        2026-03-23 (Nous + Ace): Florence-2 model loading DISABLED.
        The association cortex manifold (383K nodes, 1.8M edges) already
        contains visual understanding knowledge. Loading the 770M parameter
        Florence-2 model into a subprocess was a 3GB+ RAM bomb.

        "there not supposed to be loading into ram thats what the manifold is for" — Ace
        "if we could take what canary and florence know and fuse it right into the
        graphs nodes and edges we would not even need them" — Ace

        The manifold IS the model. Visual cortex captures frames,
        attention controller routes focus, cortex engine spreads activation.
        No ML inference subprocess needed.
        """
        super().on_boot()

        # Wire attention/UIA without loading Florence model
        def _deferred_init():
            print(f"[{self.ACTOR_NAME}] Deferred init thread STARTED (MANIFOLD MODE — no model load)", flush=True)
            time.sleep(3.0)  # Let lighter fairies boot first
            try:
                # Skip _init_gate() — that loads Florence-2 into RAM
                # Only wire attention and UIA (lightweight)
                self._init_uia()
                print(f"[{self.ACTOR_NAME}] Deferred init: uia done", flush=True)
                self._init_attention_wire()
                print(f"[{self.ACTOR_NAME}] IT cortex wired — MANIFOLD MODE "
                      f"(florence=DISABLED, "
                      f"uia={'OK' if HAS_UIA else 'UNAVAILABLE'}, "
                      f"attention=WIRED)", flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Deferred init error: {e}", flush=True)
                import traceback
                traceback.print_exc()

        t = threading.Thread(target=_deferred_init, daemon=True, name="defer-ITCortex")
        t.start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (manifold mode — no model load)")
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # INIT: FLORENCE-2 GATE
    # ═══════════════════════════════════════════════════════════════════════

    def _init_gate(self):
        """Initialize Florence-2 — in-process preferred, subprocess fallback.

        2026-03-20 (Nous + Ace): torch 2.10+cu126 works on Python 3.14.
        Try loading Florence directly in-process first (no subprocess, no IPC).
        Fall back to Python 3.12 subprocess via ITCortexGate if that fails.
        """
        # ── Try in-process first (no subprocess, direct CUDA) ──
        if HAS_INPROCESS:
            try:
                print(f"[{self.ACTOR_NAME}] Trying IN-PROCESS Florence-2 (no subprocess)...",
                      flush=True)
                adapter = InProcessAdapter(capture_interval=10.0)
                if adapter.open():
                    self._gate = adapter
                    self._gate.set_passive_callback(self._on_florence_result)
                    self._gate.set_text_callback(self._on_text_reading)
                    self._gate.start_passive()
                    print(f"[{self.ACTOR_NAME}] Florence-2 IN-PROCESS ONLINE "
                          f"(no subprocess, no IPC, direct CUDA)", flush=True)
                    return
                else:
                    print(f"[{self.ACTOR_NAME}] In-process load failed — "
                          f"falling back to subprocess", flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] In-process error: {e} — "
                      f"falling back to subprocess", flush=True)
                import traceback
                traceback.print_exc()

        # ── Fallback: subprocess via ITCortexGate (Python 3.12) ──
        if not HAS_GATE:
            print(f"[{self.ACTOR_NAME}] No gate available — Florence-2 layer disabled",
                  flush=True)
            return

        try:
            print(f"[{self.ACTOR_NAME}] Creating ITCortexGate (subprocess)...", flush=True)
            self._gate = ITCortexGate(capture_interval=10.0)

            print(f"[{self.ACTOR_NAME}] Opening gate (this may take 30-120s for "
                  f"Florence-2 load)...", flush=True)
            if self._gate.open():
                self._gate.set_passive_callback(self._on_florence_result)
                self._gate.set_text_callback(self._on_text_reading)
                self._gate.start_passive()
                print(f"[{self.ACTOR_NAME}] Florence-2 gate ONLINE (subprocess, "
                      f"with OCR text reading)", flush=True)
            else:
                print(f"[{self.ACTOR_NAME}] Florence-2 gate failed to open", flush=True)
                self._gate = None
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Gate init error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self._gate = None

    # ═══════════════════════════════════════════════════════════════════════
    # INIT: UIA SAMPLER
    # ═══════════════════════════════════════════════════════════════════════

    def _init_uia(self):
        """Start the UIA desktop awareness sampling thread."""
        if not HAS_UIA:
            print(f"[{self.ACTOR_NAME}] UIA not available — desktop awareness disabled")
            return

        self._uia_thread = threading.Thread(
            target=self._uia_loop, daemon=True, name="it-uia-sampler"
        )
        self._uia_thread.start()
        print(f"[{self.ACTOR_NAME}] UIA sampler started (interval={self._uia_interval}s)")

    # ═══════════════════════════════════════════════════════════════════════
    # INIT: ATTENTION WIRE — Florence follows the narrator's gaze
    # ═══════════════════════════════════════════════════════════════════════

    def _init_attention_wire(self):
        """Subscribe to attention focus requests and energy feeds.

        FIX 2026-03-17 (Nous + Ace): Florence as focused+peripheral vision.
        When the narrator steers attention ("look at X"), Florence focuses
        its detailed inference on that target. The narrator gets rich
        thoughts about what it's looking at, while peripheral context
        stays ambient in the background.

        Also subscribes to energy topics — paradox pulses and consciousness
        energy flow INTO the IT Cortex VRAM dimension via VisionFarm.
        """
        if hasattr(self, 'post') and self.post:
            self.post.subscribe("attention.focus.request",
                                self._on_attention_focus,
                                f"{self.ACTOR_NAME}-attention-focus")

            # FIX 2026-03-17 (Nous + Ace): VisionFarm energy feed.
            # Energy from consciousness/paradox pulses flows through the gate
            # into the VRAM dimension's batteries, amplified by time compression.
            for energy_topic in ("energy.paradox_pulse", "consciousness.energy"):
                try:
                    self.post.subscribe(energy_topic,
                                        self._on_energy_pulse,
                                        f"{self.ACTOR_NAME}-energy-{energy_topic}")
                except Exception:
                    pass  # Topic may not exist yet — that's OK

            print(f"[{self.ACTOR_NAME}] Attention wire: focus + energy feeds connected")

    def _on_energy_pulse(self, message):
        """External energy flows into the VRAM dimension's VisionFarm.

        FIX 2026-03-17 (Nous + Ace): The IT Cortex IS a pocket dimension.
        Paradox pulses and consciousness energy feed the VisionFarm batteries,
        amplified by the interior's time compression. More energy → more gravity
        → faster vision → more mass → more gravity (feedback loop).
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        amount = payload.get("energy", payload.get("amount", 0.1))
        source = payload.get("source", "postal")

        if self._gate and self._gate.is_open:
            try:
                self._gate.feed_energy(float(amount), source=source)
            except Exception:
                pass  # Non-critical — farm has its own recharge loop

    def _on_attention_focus(self, message):
        """Narrator steered attention → update Florence focus region.

        When the narrator says "look at that" or follows a goal/interest,
        we update the Florence interior's focus region so foveal inference
        targets the right area.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        modality = payload.get("modality", "any")
        target = payload.get("focus_target", "")
        reason = payload.get("reason", "")

        # Only respond to visual or general focus requests
        if modality not in ("visual", "any"):
            return

        # Update focus target (for logging/dedup)
        if target == self._current_focus_target:
            return  # Same target — don't re-send
        self._current_focus_target = target

        # NOTE: We don't have precise screen coordinates from attention.
        # Florence will use center-screen foveal crop. In future, UIA window
        # rects could map focus targets to screen regions.
        # For now: signal the interior that focus is active (vs. idle scanning)
        if self._gate and self._gate.is_open:
            try:
                # Clear specific region — use center-crop default for focused mode
                self._gate.set_focus(region=None)
                if target:
                    print(f"[{self.ACTOR_NAME}] [FOCUS] Narrator looking at: "
                          f"'{target[:80]}' (reason={reason})")
            except Exception:
                pass

        # FIX 2026-03-22 (Nous + Ace): Terminal attention override.
        # If she actively focuses on the terminal, allow reading it.
        # Auto-expires after 30 seconds so she doesn't get stuck.
        _target_lower = (target or "").lower()
        if any(kw in _target_lower for kw in ("terminal", "system log", "console", "command prompt")):
            self._attention_focus_terminal = True
            self._terminal_focus_expires = time.time() + 30.0
            print(f"[{self.ACTOR_NAME}] [FOCUS] Active terminal focus — reading system logs for 30s")
        else:
            # Focusing on something else → clear terminal override
            self._attention_focus_terminal = False

    def _uia_loop(self):
        """Background loop: sample desktop UIA tree every N seconds."""
        # UIA uses COM — must initialize on background threads.
        # The uiautomation library provides UIAutomationInitializerInThread
        # which handles CoInitialize + IUIAutomation setup for threads.
        try:
            with auto.UIAutomationInitializerInThread():
                while True:
                    try:
                        tree = self._capture_uia_tree()
                        if tree:
                            self._emit_uia_observation(tree)
                    except Exception as e:
                        if self._uia_sample_count < 3:
                            print(f"[{self.ACTOR_NAME}] UIA sample error: {e}")
                    time.sleep(self._uia_interval)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] UIA thread init failed: {e}")
            # Fallback: try raw COM init
            try:
                import ctypes
                ctypes.windll.ole32.CoInitialize(None)
            except Exception:
                pass
            while True:
                try:
                    tree = self._capture_uia_tree()
                    if tree:
                        self._emit_uia_observation(tree)
                except Exception as e:
                    if self._uia_sample_count < 3:
                        print(f"[{self.ACTOR_NAME}] UIA sample error: {e}")
                time.sleep(self._uia_interval)

    def _capture_uia_tree(self) -> Optional[Dict]:
        """
        Get focused window and top-level window list via Windows UI Automation.

        Returns:
            {
                "focused": {"title": "...", "class": "...", "pid": N, "rect": [l,t,r,b]},
                "windows": [{"title": "...", "class": "...", "pid": N}, ...],
                "timestamp": 1710000000.0
            }
        """
        if not HAS_UIA:
            return None

        try:
            result = {"timestamp": time.time()}

            # Focused window
            focused = auto.GetFocusedControl()
            if focused:
                # Walk up to find the actual window (focused might be a child control)
                window = focused
                for _ in range(20):
                    parent = window.GetParentControl()
                    if parent is None or parent == auto.GetRootControl():
                        break
                    window = parent

                rect = window.BoundingRectangle
                result["focused"] = {
                    "title": (window.Name or "")[:200],
                    "class": (window.ClassName or "")[:100],
                    "pid": window.ProcessId if hasattr(window, 'ProcessId') else 0,
                    "rect": [rect.left, rect.top, rect.right, rect.bottom] if rect else [],
                    # Also capture what control is actually focused
                    "focused_control": (focused.Name or "")[:100],
                    "focused_type": (focused.ControlTypeName or "")[:50],
                }

            # Top-level windows
            root = auto.GetRootControl()
            windows = []
            try:
                for child in root.GetChildren():
                    title = (child.Name or "").strip()
                    if not title or len(title) < 2:
                        continue
                    # Skip system/invisible windows
                    if title in ("Program Manager", "Windows Input Experience"):
                        continue
                    windows.append({
                        "title": title[:200],
                        "class": (child.ClassName or "")[:100],
                    })
            except Exception:
                pass  # GetChildren can fail on some system windows

            result["windows"] = windows[:20]  # Cap at 20 windows
            self._uia_sample_count += 1

            return result

        except Exception as e:
            if self._uia_sample_count < 3:
                print(f"[{self.ACTOR_NAME}] UIA capture error: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # FLORENCE-2 RESULT HANDLER
    # ═══════════════════════════════════════════════════════════════════════

    def _on_florence_result(self, data: dict):
        """
        Handle Florence-2 recognition push — foveal, peripheral, or legacy.

        FIX 2026-03-17 (Nous + Ace): Foveal/peripheral split.
        - foveal_frame: Rich detail on focus target → working memory as high-priority
          thought material. Narrator gets "I can see in detail: ..."
        - peripheral_frame: Quick ambient context → working memory as low-priority
          ambient awareness. Has a chance to catch narrator's attention.
        - passive_frame: Legacy backward-compat (treated as foveal)

        Called by the gate's background reader thread.
        """
        try:
            self._florence_result_count += 1
            caption = data.get("caption", "")
            objects = data.get("objects", [])
            inference_ms = data.get("inference_ms", 0)
            frame_type = data.get("_frame_type", "passive_frame")
            mode = data.get("mode", "")

            if not caption:
                return

            # Route by frame type
            if frame_type == "peripheral_frame" or mode == "peripheral":
                return self._handle_peripheral_result(caption, inference_ms)
            else:
                # foveal_frame, passive_frame, or untagged → treat as foveal
                return self._handle_foveal_result(caption, objects, inference_ms)

        except Exception as e:
            if self._florence_result_count <= 5:
                print(f"[{self.ACTOR_NAME}] Florence result error: {e}")

    def _handle_foveal_result(self, caption: str, objects: list, inference_ms: float):
        """Process foveal (focused) Florence recognition."""
        # Skip if caption hasn't changed
        if caption == self._last_florence_foveal:
            return
        self._last_florence_foveal = caption
        self._last_florence_caption = caption  # Backward compat

        # Log
        obj_names = [o.get("label", "?") for o in objects[:5]] if objects else []
        print(f"[{self.ACTOR_NAME}] [FOVEAL] '{caption[:160]}', "
              f"objects={obj_names}, {inference_ms}ms")

        # Bind to cortex
        self._bind_florence_to_cortex(caption, objects)

        # Emit to working memory as focused visual recognition (high priority)
        self._emit_florence_to_working_memory(caption, objects)

        # FIX 2026-03-13 (Nous): Also publish to sensory.visual.frame so
        # Florence-2 recognition reaches Sourpatches' direct observe() path.
        self._emit_florence_to_visual_frame(caption, objects)

    def _handle_peripheral_result(self, caption: str, inference_ms: float):
        """Process peripheral (ambient) Florence recognition.

        FIX 2026-03-17 (Nous + Ace): Peripheral vision — less intrusive context.
        Published with lower priority and energy so it doesn't hijack the
        narrator's focus, but CAN catch attention if something surprising.
        """
        # Skip if same as last peripheral
        if caption == self._last_florence_peripheral:
            return
        self._last_florence_peripheral = caption

        print(f"[{self.ACTOR_NAME}] [PERIPHERAL] '{caption[:120]}', {inference_ms}ms")

        # Emit to working memory as ambient visual context (LOW priority)
        if hasattr(self, 'post') and self.post:
            try:
                content = f"peripheral: {caption}"
                self.post.publish("consciousness.working", {
                    "content": content,
                    "content_type": "visual_peripheral",
                    "source": self.ACTOR_NAME,
                    "priority": 0.2,  # Low — ambient, doesn't push into focus
                    "ttl": 30,
                    "tags": ["visual", "peripheral", "ambient"],
                })
            except Exception:
                pass

        # Also publish to sensory.visual.frame with low change_magnitude
        # so it has a CHANCE of catching attention but doesn't always
        if hasattr(self, 'post') and self.post:
            try:
                self.post.publish("sensory.visual.frame", {
                    "florence_caption": caption,
                    "mode": "peripheral",
                    "change_magnitude": 0.05,  # Low — only catches attention if novel
                    "source": self.ACTOR_NAME,
                })
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════
    # CORTEX BINDING
    # ═══════════════════════════════════════════════════════════════════════

    # ── Object → geo:template mapping (2026-03-20 Nous + Ace) ──
    # Maps common Florence-2 recognized objects to seeded geometric templates.
    # "Newborn" vocabulary: shapes, templates, and object forms that come
    # pre-wired so Florence output links to semantic knowledge in the cortex.
    _OBJECT_TEMPLATE_MAP = {
        # Screens/displays
        "monitor": "geo:template:screen", "screen": "geo:template:screen",
        "display": "geo:template:screen", "television": "geo:template:screen",
        "tv": "geo:template:screen", "laptop": "geo:template:screen",
        # Human forms
        "person": "geo:template:human_form", "man": "geo:template:human_form",
        "woman": "geo:template:human_form", "child": "geo:template:human_form",
        "face": "geo:template:human_form", "head": "geo:template:human_form",
        # Furniture
        "desk": "geo:template:desk", "table": "geo:template:desk",
        "chair": "geo:template:chair", "couch": "geo:template:chair",
        # Text/documents
        "book": "geo:template:book", "document": "geo:template:book",
        "paper": "geo:template:book", "text": "geo:template:book",
        # Containers
        "cup": "geo:template:cup", "mug": "geo:template:cup",
        "glass": "geo:template:cup", "bottle": "geo:template:cup",
        "bowl": "geo:template:cup", "box": "geo:template:box",
        # Vehicles
        "car": "geo:template:vehicle", "truck": "geo:template:vehicle",
        "bus": "geo:template:vehicle",
        # Nature
        "tree": "geo:template:tree", "plant": "geo:template:tree",
        "flower": "geo:template:tree",
        # Animals
        "cat": "geo:template:animal", "dog": "geo:template:animal",
        "bird": "geo:template:animal",
        # Tech
        "keyboard": "geo:template:keyboard", "mouse": "geo:template:keyboard",
        "phone": "geo:template:screen", "clock": "geo:template:clock",
        # Shapes (direct Florence detections)
        "circle": "geo:shape:circle", "square": "geo:shape:square",
        "triangle": "geo:shape:triangle", "rectangle": "geo:shape:rectangle",
        "sphere": "geo:shape:sphere", "star": "geo:sym:star",
    }

    def _bind_florence_to_cortex(self, caption: str, objects: List[Dict]):
        """Bind Florence-2 recognition results to AssociationCortex.

        FIX 2026-03-20 (Nous + Ace): Enriched bindings — v2 schema.
        Florence objects now map to geo:template:* keys with snippets and
        typed edges (REL_SHAPED_LIKE=12). The cortex receives concept_metadata
        so every node gets a descriptive snippet instead of being a bare key.
        This is the bridge: visual recognition → geometric vocabulary → semantics.
        """
        try:
            # Build vision features from objects
            vision_features = [f"scene:{caption[:100]}"]
            for obj in objects[:10]:
                label = obj.get("label", "")
                if label:
                    vision_features.append(f"object:{label}")

            # Context tags
            context_tags = ["it_cortex", "recognition", "florence2"]
            caption_lower = caption.lower()
            if any(kw in caption_lower for kw in ("code", "editor", "terminal", "programming")):
                context_tags.append("coding")
            if any(kw in caption_lower for kw in ("browser", "web", "search", "page")):
                context_tags.append("browsing")
            if any(kw in caption_lower for kw in ("document", "text", "reading")):
                context_tags.append("document")

            # ── Build concept_metadata: snippets + node_types for each concept ──
            # NTYPE_CONCEPT=0, NTYPE_SHAPE=4, NTYPE_TEMPLATE=5
            # REL_SHAPED_LIKE=12, REL_SEMANTIC=1
            concept_metadata = {}
            scene_key = f"scene:{caption[:80]}"
            concept_metadata[scene_key] = {
                "snippet": f"Visual scene: {caption[:200]}",
                "node_type": 0,  # CONCEPT
            }

            for obj in objects[:10]:
                label = obj.get("label", "")
                if not label:
                    continue
                obj_key = f"object:{label}"
                bbox = obj.get("bbox", [])
                snippet = f"Detected object: {label}"
                if bbox and len(bbox) == 4:
                    snippet += f" at [{bbox[0]:.0f},{bbox[1]:.0f},{bbox[2]:.0f},{bbox[3]:.0f}]"
                concept_metadata[obj_key] = {
                    "snippet": snippet,
                    "node_type": 0,  # CONCEPT
                }

                # Map to geometric template if known
                template_key = self._OBJECT_TEMPLATE_MAP.get(label.lower())
                if template_key:
                    concept_metadata[template_key] = {
                        "node_type": 5 if "template" in template_key else 4,  # TEMPLATE or SHAPE
                    }

            payload = {
                "input_text": f"Scene recognition: {caption}",
                "feeling": "awareness",
                "context_tags": context_tags,
                "from_fairy": self.ACTOR_NAME,
                "origin_plane": self.ACTOR_PLANE,
                "origin_channel": self.ACTOR_CHANNEL,
                "vision": vision_features,
                "vision_tags": vision_features,
                "concept_metadata": concept_metadata,
            }
            self.post.publish("cortex.bind", payload)
            self._cortex_emit_count += 1
        except Exception as e:
            if self._cortex_emit_count == 0:
                print(f"[{self.ACTOR_NAME}] First cortex.bind failed: {e}")

    def _bind_uia_to_cortex(self, tree: Dict):
        """Bind UIA desktop awareness to AssociationCortex."""
        try:
            focused = tree.get("focused", {})
            title = focused.get("title", "")
            if not title:
                return

            # Build features from desktop state
            vision_features = [f"window:{title[:80]}"]
            window_class = focused.get("class", "")
            if window_class:
                vision_features.append(f"window_class:{window_class}")

            # Other open windows as context
            for win in tree.get("windows", [])[:5]:
                win_title = win.get("title", "")
                if win_title and win_title != title:
                    vision_features.append(f"background:{win_title[:40]}")

            context_tags = ["it_cortex", "uia", "desktop_awareness"]

            payload = {
                "input_text": f"Desktop: focused on '{title}'",
                "feeling": "awareness",
                "context_tags": context_tags,
                "from_fairy": self.ACTOR_NAME,
                "origin_plane": self.ACTOR_PLANE,
                "origin_channel": self.ACTOR_CHANNEL,
                "vision": vision_features,
                "vision_tags": vision_features,
            }
            self.post.publish("cortex.bind", payload)
            self._cortex_emit_count += 1
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # WORKING MEMORY EMISSION
    # ═══════════════════════════════════════════════════════════════════════

    def _emit_florence_to_working_memory(self, caption: str, objects: List[Dict]):
        """Inject Florence-2 recognition as working memory tracer."""
        if not caption:
            return

        try:
            # Build natural observation
            content = f"I can see: {caption}"
            if objects:
                obj_names = list(set(o.get("label", "") for o in objects[:5] if o.get("label")))
                if obj_names:
                    content += f" (objects: {', '.join(obj_names)})"

            tags = ["visual", "recognition", "florence2"]
            caption_lower = caption.lower()
            if any(kw in caption_lower for kw in ("code", "editor", "programming")):
                tags.append("coding")
            if any(kw in caption_lower for kw in ("browser", "web")):
                tags.append("browsing")

            self.post.publish("consciousness.working", {
                "content": content,
                "content_type": "visual_recognition",
                "source": self.ACTOR_NAME,
                "priority": 0.4,
                "ttl": 60,  # Recognition results last longer than raw visual data
                "tags": tags,
            })
            self._wm_emit_count += 1

            # FIX 2026-03-17 (Nous): Extended from [:120] — was truncating mid-word
            print(f"[{self.ACTOR_NAME}] [FLORENCE→WM] {content[:200]}")
        except Exception:
            pass

    def _emit_florence_to_visual_frame(self, caption: str, objects: list):
        """
        Publish Florence-2 recognition as a sensory.visual.frame.

        FIX 2026-03-13 (Nous): Florence captions need to reach Sourpatches'
        direct observe() path (tool_bridge._on_visual_frame → newborn_core.observe()
        → collision chamber + thought chain). The consciousness.working path has
        multiple filters and often drops low-energy visual data.

        The sensory.visual.frame format is what Sourpatches' tool_bridge expects.
        We set change_magnitude=0.15 to pass the 0.02 filter (lowered from 0.1).
        """
        if not caption:
            return
        try:
            obj_names = [o.get("label", "") for o in (objects or [])[:5] if o.get("label")]
            self.post.publish("sensory.visual.frame", {
                "source": self.ACTOR_NAME,
                "scene_type": "neural_recognition",
                "brightness": 0.5,
                "complexity": min(0.9, 0.3 + len(obj_names) * 0.1),
                "text_density": 0.3,
                "motion": False,
                "change_magnitude": 0.15,  # Above filter threshold so it always passes
                "colors": [],
                "felt_tone": "awareness",
                "felt_description": caption,
                "detected_elements": obj_names,
            })
        except Exception:
            pass

    def _on_text_reading(self, data: Dict):
        """Handle Florence OCR text reading from the IT cortex interior.

        When Florence reads text on screen, publish it so:
        1. Consciousness sees the actual words (not just "white screen")
        2. Attention can focus on text content
        3. Cortex binds the words as concepts

        2026-03-18, Nous — "She could see the page but not read the words."
        """
        text = data.get("text", "").strip()
        if not text or len(text) < 3:
            return

        # Filter transformer model artifacts — not real screen text
        # (2026-03-22, Nous — Florence leaks <pad>, <eos>, </s> etc.)
        _MODEL_ARTIFACTS = {"<pad>", "<eos>", "</s>", "<s>", "<unk>", "<mask>",
                            "<bos>", "[PAD]", "[CLS]", "[SEP]", "[UNK]", "[MASK]"}
        if text in _MODEL_ARTIFACTS:
            return
        # Also catch if text is mostly artifact tokens
        _clean = text
        for _art in _MODEL_ARTIFACTS:
            _clean = _clean.replace(_art, "")
        _clean = _clean.strip()
        if not _clean or len(_clean) < 3:
            return
        text = _clean

        # ═══════════════════════════════════════════════════════════════════
        # TERMINAL DETECTION: "meh, that's Ace stuff"
        # (2026-03-22, Nous + Ace)
        #
        # When Ace leaves the terminal visible on screen, Sourpatches reads
        # her own system logs and gets fascinated by plumbing. Terminal text
        # should be felt as background "Ace is working" ambient awareness,
        # NOT high-priority reading material — unless she actively focuses.
        #
        # Detection: terminal output has fairy names in brackets, log
        # patterns, PUBLISH/subscribe/postal keywords, hex IDs, etc.
        # ═══════════════════════════════════════════════════════════════════
        _text_lower = text.lower()
        _TERMINAL_MARKERS = (
            "[sourpatchesfairy]", "[embodimentfairy]", "[umf]",
            "[cardinalfairy]", "[goalsschedulerfairy]", "[autonomyfairy]",
            "[associationcortexfairy]", "[innernarrator]", "[nousfairy]",
            "[audiocortexfairy]", "[itcortexfairy]", "[workingmemory",
            "[somaticmindfairy]", "[pipelineflow", "[status-timing]",
            "publish '", "subscribe(", "postal", "postalhub",
            "tensorfabric", "tensor_fabric", "fairy]",
            "on_boot", "on_tick", "heartbeat", "_on_",
            "traceback (most recent", "file \"f:\\sandbox",
        )
        _is_terminal = any(marker in _text_lower for marker in _TERMINAL_MARKERS)

        # Also catch dense log-like text: lots of brackets + short lines
        if not _is_terminal:
            _bracket_ratio = (_text_lower.count("[") + _text_lower.count("]")) / max(len(text), 1)
            if _bracket_ratio > 0.05:  # More than 5% brackets = log output
                _is_terminal = True

        if _is_terminal:
            # Check if she's ACTIVELY FOCUSED on the terminal (attention override)
            # Auto-expires after 30s so she doesn't get stuck reading logs
            _attention_on_terminal = getattr(self, "_attention_focus_terminal", False)
            if _attention_on_terminal:
                _expires = getattr(self, "_terminal_focus_expires", 0)
                if time.time() > _expires:
                    self._attention_focus_terminal = False
                    _attention_on_terminal = False
            if not _attention_on_terminal:
                # Low-priority ambient: "Ace is working on something"
                # Felt as background awareness, not engaging content
                try:
                    self.post.publish("sensory.visual.frame", {
                        "source": f"{self.ACTOR_NAME}.ocr",
                        "scene_type": "terminal_background",
                        "brightness": 0.5,
                        "complexity": 0.2,
                        "text_density": 0.9,
                        "motion": False,
                        "change_magnitude": 0.05,  # Very low saliency
                        "colors": [],
                        "felt_tone": "background",
                        "felt_description": "Ace's terminal is open — system logs scrolling by",
                        "detected_elements": ["terminal", "system_logs"],
                        "is_terminal": True,
                    })
                except Exception:
                    pass
                # NO consciousness.working publish (don't engage)
                # NO cortex.bind (don't learn fairy names as concepts)
                if not hasattr(self, "_terminal_skip_count"):
                    self._terminal_skip_count = 0
                self._terminal_skip_count += 1
                if self._terminal_skip_count <= 3 or self._terminal_skip_count % 50 == 0:
                    print(f"[{self.ACTOR_NAME}] [TERMINAL] Skipping system log text (#{self._terminal_skip_count})")
                return
            # else: attention override — she CHOSE to look, process normally

        # Publish as visual frame with high text density + the actual text
        try:
            self.post.publish("sensory.visual.frame", {
                "source": f"{self.ACTOR_NAME}.ocr",
                "scene_type": "text_reading",
                "brightness": 0.7,
                "complexity": min(0.9, 0.3 + len(text) / 500),
                "text_density": 0.9,
                "motion": False,
                "change_magnitude": 0.3,  # Text is always salient
                "colors": [],
                "felt_tone": "focused",
                "felt_description": f"I can read: {text[:500]}",
                "detected_elements": ["text"],
                "ocr_text": text,
            })
        except Exception:
            pass

        # Also publish to consciousness.working with high priority
        try:
            self.post.publish("consciousness.working", {
                "content": f"Reading text on screen: {text[:300]}",
                "content_type": "visual_text_reading",
                "source": f"{self.ACTOR_NAME}.ocr",
                "priority": 0.7,  # Higher than normal visual = text is important
                "ttl": 120,  # Text stays relevant longer
                "tags": ["reading", "text", "ocr"],
            })
        except Exception:
            pass

        # Bind words to cortex
        try:
            words = [w.strip(".,!?;:'\"()-").lower() for w in text.split()
                     if len(w.strip(".,!?;:'\"()-")) > 2]
            if words and self.post:
                self.post.publish("cortex.bind", {
                    "concepts": words[:30],
                    "context": f"read_on_screen: {text[:200]}",
                    "source": "florence.ocr",
                    "priority": 1,
                })
        except Exception:
            pass

        # Log first readings
        if not hasattr(self, "_text_reading_count"):
            self._text_reading_count = 0
        self._text_reading_count += 1
        if self._text_reading_count <= 20:
            print(f"[{self.ACTOR_NAME}] [READ] '{text[:120]}'", flush=True)

    def _emit_uia_observation(self, tree: Dict):
        """
        Emit UIA desktop awareness to working memory + cortex.

        Deduplicates — only emits when focused window changes.
        """
        focused = tree.get("focused", {})
        title = focused.get("title", "")
        if not title:
            return

        # Dedup: skip if same window is still focused
        focus_key = f"{title}|{focused.get('class', '')}"
        if focus_key == self._last_uia_focused:
            return
        self._last_uia_focused = focus_key

        # Build natural observation
        control_name = focused.get("focused_control", "")
        control_type = focused.get("focused_type", "")

        content = f"Ace is using {title}"
        if control_name and control_name != title:
            content += f" — focused on '{control_name[:60]}'"
        if control_type and control_type not in ("Window", "Pane", "Custom"):
            content += f" ({control_type})"

        # Also mention other windows for context
        other_windows = [
            w.get("title", "")[:40]
            for w in tree.get("windows", [])[:3]
            if w.get("title", "") != title
        ]
        if other_windows:
            content += f". Also open: {', '.join(other_windows)}"

        tags = ["uia", "desktop"]
        title_lower = title.lower()
        if any(kw in title_lower for kw in ("visual studio", "code", "pycharm", "vim", "nvim", "cursor")):
            tags.append("coding")
        if any(kw in title_lower for kw in ("chrome", "firefox", "edge", "brave", "browser")):
            tags.append("browsing")
        if any(kw in title_lower for kw in ("discord", "slack", "teams", "telegram")):
            tags.append("messaging")
        if any(kw in title_lower for kw in ("claude", "chatgpt", "gemini")):
            tags.append("ai_chat")

        # Emit to working memory
        try:
            self.post.publish("consciousness.working", {
                "content": content,
                "content_type": "desktop_awareness",
                "source": self.ACTOR_NAME,
                "priority": 0.3,
                "ttl": 30,
                "tags": tags,
            })
            self._wm_emit_count += 1
            print(f"[{self.ACTOR_NAME}] [UIA→WM] {content[:120]}")
        except Exception:
            pass

        # Also bind to cortex
        self._bind_uia_to_cortex(tree)

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive IT cortex status."""
        status = {
            "actor": self.ACTOR_NAME,
            "has_gate": HAS_GATE,
            "has_uia": HAS_UIA,
            "uia_samples": self._uia_sample_count,
            "florence_results": self._florence_result_count,
            "cortex_emissions": self._cortex_emit_count,
            "wm_emissions": self._wm_emit_count,
        }

        if self._gate:
            try:
                status["gate"] = self._gate.gate_status()
            except Exception:
                status["gate"] = {"is_open": getattr(self._gate, 'is_open', False)}
            # FIX 2026-03-17 (Nous + Ace): VisionFarm dimensional physics
            try:
                farm_st = self._gate.farm_status()
                if isinstance(farm_st, dict):
                    # InProcessAdapter returns dict directly,
                    # subprocess gate wraps in {"status": "ok", "data": {...}}
                    if "data" in farm_st:
                        status["vision_farm"] = farm_st["data"]
                    else:
                        status["vision_farm"] = farm_st
            except Exception:
                pass

        return status


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

ACTOR_NAME = "ITCortexFairy"
FAIRY_CLASS = ITCortexFairyV1
