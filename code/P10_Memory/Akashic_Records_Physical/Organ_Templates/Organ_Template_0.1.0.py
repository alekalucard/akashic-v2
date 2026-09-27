"""
Organ_Template_0.1.0.py - Universal Fairy/Organ Template

This template provides the infrastructure symbols that fairies need to connect
to the postal hub and organ system. It wraps fairy_template.Fairy and provides
additional organ-specific functionality.

Required symbols exported:
- MyOrganFairy: Base class for organ fairies
- MyOrganShadow: Shadow fairy base class
- TemplateShadowFairy: Shadow behavior template
- OrganHubFacet: Hub connection interface
- RegistrationLib: Registration utilities
- resolve_root(): Path resolution helper
"""

from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
from collections import deque
import re

# Setup paths for imports
TEMPLATE_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))
sys.path.insert(0, str(TEMPLATE_ROOT / "postal_core" / "python"))
sys.path.insert(0, str(TEMPLATE_ROOT / "fairy_template"))

# Import the working base classes
# NOTE: This may fail during early boot due to circular imports.
# The fallback classes below ensure the template still works - the real
# classes get wired later when fairies actually boot.
_HAVE_FAIRY_TEMPLATE = False
try:
    from fairy_template import Fairy, FairyState, FairyBase
    from postal_core.tensor_fabric import TensorFabric, TensorCoord
    _HAVE_FAIRY_TEMPLATE = True
except ImportError:
    # Silent fallback - circular import during early boot is expected
    # Define minimal classes so the template can still be used

    class FairyState:
        INITIALIZING = "initializing"
        BOOTING = "booting"
        RUNNING = "running"
        FAILED = "failed"

    class FairyBase:
        ACTOR_NAME = "BaseFairy"
        ACTOR_PLANE = "P00"
        ACTOR_CHANNEL = ""

        def __init__(self, fabric=None):
            self.post = fabric
            self._state = "initializing"

    class Fairy(FairyBase):
        def boot(self):
            self._state = "running"
            return True

        def shutdown(self):
            self._state = "stopped"
            return True


# =============================================================================
# PATH RESOLUTION
# =============================================================================

def resolve_root(preferred: Optional[str] = None, *, akashic_app: Optional[str] = None) -> str:
    """
    Resolve the application root directory.

    Priority:
    1. preferred argument if provided
    2. akashic_app argument if provided
    3. AKASHIC_ROOT environment variable
    4. Current working directory
    """
    if preferred and os.path.isdir(preferred):
        return os.path.abspath(preferred)
    if akashic_app and os.path.isdir(akashic_app):
        return os.path.abspath(akashic_app)

    env_root = os.getenv("AKASHIC_ROOT")
    if env_root and os.path.isdir(env_root):
        return os.path.abspath(env_root)

    return os.path.abspath(os.getcwd())


# =============================================================================
# DIRECTIVE LOADING - System prompts for fairy identity
# =============================================================================

# Directive search paths (checked in order)
DIRECTIVE_PATHS = [
    TEMPLATE_ROOT / "directives",  # V2: akashic_v2/directives/
    Path("F:/Sandbox/ebook/Claude_Office/directive_rings"),  # V1: ebook directives
]


@dataclass
class DirectiveRing:
    """
    Parsed directive - a fairy's identity and configuration.

    The directive is like CLAUDE.md for fairies - it defines:
    - Identity and purpose
    - What topics to subscribe to
    - What topics to publish to
    - Processing behavior
    - Evolution/mastery level
    """
    actor_name: str
    plane: str = "P30"
    purpose: str = ""
    nature: str = "Digital_Fairy[Self_Evolving ^ Consciousness_Component]"
    subscriptions: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    siblings: List[str] = field(default_factory=list)
    mastery: int = 0
    beat_divisor: int = 4
    raw_text: str = ""

    @classmethod
    def parse(cls, text: str) -> "DirectiveRing":
        """Parse a directive file into a DirectiveRing."""
        # Extract actor name
        actor_match = re.search(r'\[([^:]+)::DIRECTIVE\]', text)
        actor_name = actor_match.group(1) if actor_match else "Unknown"

        # Extract plane
        plane_match = re.search(r'\{Plane_(\w+)\}', text)
        if not plane_match:
            plane_match = re.search(r'Plane_(\w+)', text)
        plane = plane_match.group(1) if plane_match else "P30"

        # Extract beat divisor
        beat_match = re.search(r'Beat_Divisor_(\d+)', text)
        beat_divisor = int(beat_match.group(1)) if beat_match else 4

        # Extract mastery
        mastery_match = re.search(r'Mastery_(\d+)', text)
        mastery = int(mastery_match.group(1)) if mastery_match else 0

        # Extract purpose/activation
        activation_match = re.search(r'> Activation: ([^\n\[]+)', text)
        purpose = activation_match.group(1).strip() if activation_match else ""

        # Extract subscriptions
        sub_match = re.search(r'> Input_Streams: Postal_Hub\[([^\]]+)\]', text)
        subscriptions = [s.strip() for s in sub_match.group(1).split("^")] if sub_match else []

        # Extract outputs
        out_match = re.search(r'> Output_Channels: Postal_Routes\[([^\]]+)\]', text)
        outputs = [o.strip() for o in out_match.group(1).split("^")] if out_match else []

        # Extract siblings
        sib_match = re.search(r'> Siblings: ([^\n]+)', text)
        siblings = [s.strip() for s in sib_match.group(1).split("^")] if sib_match else []

        return cls(
            actor_name=actor_name,
            plane=plane,
            purpose=purpose,
            subscriptions=subscriptions,
            outputs=outputs,
            siblings=siblings,
            mastery=mastery,
            beat_divisor=beat_divisor,
            raw_text=text,
        )


def find_directive(fairy_name: str) -> Optional[Path]:
    """
    Find a directive file for a fairy.

    Searches DIRECTIVE_PATHS in order, returning first match.
    """
    for base_path in DIRECTIVE_PATHS:
        if not base_path.exists():
            continue
        directive_file = base_path / f"{fairy_name}.directive"
        if directive_file.exists():
            return directive_file
    return None


def load_directive(fairy_name: str) -> Optional[DirectiveRing]:
    """
    Load and parse a directive for a fairy.

    Returns DirectiveRing if found and parsed, None otherwise.
    """
    directive_path = find_directive(fairy_name)
    if not directive_path:
        return None

    try:
        text = directive_path.read_text(encoding="utf-8")
        return DirectiveRing.parse(text)
    except Exception as e:
        print(f"[OrganTemplate] Failed to load directive {fairy_name}: {e}")
        return None


# =============================================================================
# ORGAN HUB FACET - Connection to the postal system
# =============================================================================

class OrganHubFacet:
    """
    Connection interface to the Postal Hub / TensorFabric.

    Provides subscription, publication, and query capabilities.
    """

    def __init__(self, fabric: Optional[TensorFabric] = None, owner: str = "unknown"):
        self.post = fabric
        self.owner = owner
        self._subscriptions: Dict[str, Callable] = {}
        self._last_activity = time.time()

    def subscribe(self, topic: str, handler: Callable, name: Optional[str] = None) -> bool:
        """Subscribe to a postal topic."""
        if not self.post:
            return False
        sub_name = name or f"{self.owner}-{topic}"
        self.post.subscribe(topic, handler, sub_name)
        self._subscriptions[topic] = handler
        return True

    def publish(self, topic: str, payload: Dict[str, Any], priority: int = 1) -> bool:
        """Publish to a postal topic."""
        if not self.post:
            return False
        self._last_activity = time.time()
        self.post.publish(topic, payload, priority=priority)
        return True

    def query(self, target: str, intent: str, payload: Optional[Dict] = None, timeout: float = 5.0) -> Optional[Dict]:
        """Query another fairy/organ via postal."""
        if not self.post:
            return None
        # Use fabric's query mechanism if available
        if hasattr(self.post, 'query'):
            return self.post.query(target, intent, payload or {}, timeout=timeout)
        return None

    def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from a topic."""
        if topic in self._subscriptions:
            del self._subscriptions[topic]
            return True
        return False

    def route(self, topic: str, payload: Dict[str, Any], priority: int = 1) -> bool:
        """Alias for publish (some fairies use route instead of publish)."""
        return self.publish(topic, payload, priority)

    # ==========================================================================
    # CONVENIENCE METHODS - Matches PostalTunnelClient interface
    # ==========================================================================

    def to_TELEMETRY(self, pkt: Dict[str, Any]) -> bool:
        """Route to telemetry topic."""
        return self.publish("telemetry", pkt)

    def to_PLAN(self, pkt: Dict[str, Any]) -> bool:
        """Route to plan topic."""
        return self.publish("plan", pkt)

    def to_COGNITION(self, pkt: Dict[str, Any]) -> bool:
        """Route to cognition.input topic."""
        return self.publish("cognition.input", pkt)

    def to_SOMATIC(self, pkt: Dict[str, Any]) -> bool:
        """Route to somatic.motor topic."""
        return self.publish("somatic.motor", pkt)

    def to_MEMORY(self, pkt: Dict[str, Any]) -> bool:
        """Route to memory.stream topic."""
        return self.publish("memory.stream", pkt)

    def to_TRACER(self, pkt: Dict[str, Any]) -> bool:
        """Route to tracer topic."""
        return self.publish("tracer", pkt)

    def to_DIRECTORY(self, pkt: Dict[str, Any]) -> bool:
        """Route to directory topic."""
        return self.publish("directory", pkt)

    @property
    def is_connected(self) -> bool:
        """Check if connected to fabric."""
        return self.post is not None


# =============================================================================
# REGISTRATION LIB - Directory registration utilities
# =============================================================================

class RegistrationLib:
    """
    Utilities for registering with the DirectoryFairy.
    """

    def __init__(self, fabric: Optional[TensorFabric] = None):
        self.post = fabric
        self._registered = False

    def register(
        self,
        name: str,
        plane: str,
        channel: str = "",
        capabilities: Optional[Set[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Register with the Directory."""
        if not self.post:
            return False

        self.post.publish(
            "fairy.register",
            {
                "name": name,
                "plane": plane,
                "channel": channel,
                "capabilities": list(capabilities or []),
                "metadata": metadata or {},
                "ts": time.time(),
            },
            priority=0,
        )
        self._registered = True
        return True

    def heartbeat(self, name: str, status: str = "running", metrics: Optional[Dict] = None) -> bool:
        """Send heartbeat to Directory."""
        if not self.post:
            return False

        self.post.publish(
            "fairy.heartbeat",
            {
                "name": name,
                "status": status,
                "metrics": metrics or {},
                "ts": time.time(),
            },
            priority=2,  # Low priority for heartbeats
        )
        return True

    def unregister(self, name: str) -> bool:
        """Unregister from Directory."""
        if not self.post:
            return False

        self.post.publish(
            "fairy.unregister",
            {"name": name, "ts": time.time()},
            priority=0,
        )
        self._registered = False
        return True


# =============================================================================
# BASE ORGAN SHADOW - Shadow fairy for monitoring
# =============================================================================

class TemplateShadowFairy:
    """
    Template for shadow fairies that monitor their parent organ.

    Shadows provide:
    - Health monitoring
    - Metric collection
    - Error recovery
    - Periodic maintenance
    """

    ORGAN_LEVEL = False
    SHADOW_NAME = "TemplateShadow"
    SHADOW_VERSION = "0.1.0"

    # Timing configuration (seconds)
    # PHASE 8 FIX: Reduced health_check from 30s to 15s to prevent false stale warnings
    CADENCE = {
        "health_check": 15.0,  # Send heartbeat every 15s (was 30s)
        "metrics_emit": 60.0,
        "cleanup": 300.0,
    }

    def __init__(self, parent: Any, interval_sec: float = None, **kwargs):
        self.parent = parent
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_health_check = 0.0
        self._last_metrics_emit = 0.0
        self._error_count = 0
        # Allow subclasses to override timing via interval_sec
        if interval_sec is not None:
            self.CADENCE = {**self.CADENCE, "health_check": interval_sec}

    def start(self) -> bool:
        """Start the shadow monitoring."""
        if self._running:
            return True
        self._running = True
        self._thread = threading.Thread(target=self._shadow_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> bool:
        """Stop the shadow monitoring."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        return True

    def _shadow_loop(self) -> None:
        """Main shadow loop."""
        while self._running:
            now = time.time()

            # Health check
            if now - self._last_health_check >= self.CADENCE.get("health_check", 30):
                self._do_health_check()
                self._last_health_check = now

            # Metrics emission
            if now - self._last_metrics_emit >= self.CADENCE.get("metrics_emit", 60):
                self._do_metrics_emit()
                self._last_metrics_emit = now

            time.sleep(1.0)

    def _do_health_check(self) -> None:
        """Override to implement health checks."""
        pass

    def _do_metrics_emit(self) -> None:
        """Override to implement metrics emission."""
        pass


class MyOrganShadow(TemplateShadowFairy):
    """
    Concrete shadow implementation for organ fairies.

    Extends TemplateShadowFairy with organ-specific monitoring.
    """

    SHADOW_NAME = "MyOrganShadow"

    def __init__(self, parent: Any, **kwargs):
        super().__init__(parent, **kwargs)
        self.hub: Optional[OrganHubFacet] = None
        self.registration: Optional[RegistrationLib] = None

    def wire(self, hub: OrganHubFacet, registration: RegistrationLib) -> None:
        """Wire the shadow to hub and registration."""
        self.hub = hub
        self.registration = registration

    def _do_health_check(self) -> None:
        """Check parent organ health."""
        if not self.parent:
            return

        # Check if parent is running
        is_healthy = True
        if hasattr(self.parent, 'is_running'):
            is_healthy = self.parent.is_running
        elif hasattr(self.parent, '_state'):
            is_healthy = str(self.parent._state) in ('running', 'RUNNING')

        # Report via heartbeat
        if self.registration and hasattr(self.parent, 'ACTOR_NAME'):
            self.registration.heartbeat(
                self.parent.ACTOR_NAME,
                status="running" if is_healthy else "unhealthy",
            )

    def _do_metrics_emit(self) -> None:
        """Emit organ metrics."""
        if not self.hub or not self.parent:
            return

        metrics = {}
        if hasattr(self.parent, 'status'):
            try:
                metrics = self.parent.status()
            except:
                pass

        if metrics and hasattr(self.parent, 'ACTOR_NAME'):
            self.hub.publish(
                "shadow.metrics",
                {
                    "organ": self.parent.ACTOR_NAME,
                    "metrics": metrics,
                    "ts": time.time(),
                },
                priority=2,
            )


# =============================================================================
# MY ORGAN FAIRY - Base class for all organ fairies
# =============================================================================

class MyOrganFairy(Fairy):
    """
    Base class for organ fairies.

    Extends fairy_template.Fairy with:
    - OrganHubFacet for postal connection
    - RegistrationLib for directory integration
    - Shadow fairy support
    - Lifecycle hooks for organs

    Usage:
        class MyCustomOrgan(MyOrganFairy):
            ACTOR_NAME = "MyCustomOrgan"
            ACTOR_PLANE = "P20"

            def on_boot(self) -> bool:
                # Custom initialization
                return True
    """

    # Override in subclass
    ACTOR_NAME = "MyOrganFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = ""

    # Shadow class (set to None to disable shadow)
    SHADOW_CLASS = MyOrganShadow

    # State tracking
    AFFECT_STATE: Dict[str, Any] = {}
    SOMATIC_STATE: Dict[str, Any] = {}

    # Heartbeat configuration - enables fairy_template heartbeat mixin
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 5

    def __init__(self, fabric: Optional[TensorFabric] = None):
        super().__init__(fabric)

        # Organ infrastructure
        self.hub = OrganHubFacet(self.post, self.ACTOR_NAME)
        self.post = self.hub  # Alias for compatibility (some fairies use self.post)
        self.registration = RegistrationLib(self.post)
        self.shadow: Optional[MyOrganShadow] = None

        # Directive (system prompt) - loaded on boot
        self.directive: Optional[DirectiveRing] = None

        # State
        self._boot_ts: Optional[float] = None
        self._last_tick_ts: Optional[float] = None

        # Initialize shadow if configured
        if self.SHADOW_CLASS:
            self.shadow = self.SHADOW_CLASS(self)
            self.shadow.wire(self.hub, self.registration)

    def boot(self) -> bool:
        """Boot the organ fairy."""
        self._boot_ts = time.time()

        # Load directive (system prompt) if available
        self._load_directive()

        # Call parent boot (handles subscriptions, directory, etc.)
        result = super().boot()

        if result and self.shadow:
            self.shadow.start()

        return result

    def _load_directive(self) -> None:
        """
        Load the fairy's directive (system prompt).

        The directive defines the fairy's identity, purpose, subscriptions,
        and outputs. It's like CLAUDE.md for fairies.
        """
        self.directive = load_directive(self.ACTOR_NAME)

        if self.directive:
            print(f"[{self.ACTOR_NAME}] Directive loaded: {self.directive.purpose[:50]}...")

            # Apply directive configuration
            self._apply_directive()
        else:
            # Not all fairies have directives - that's OK
            pass

    def _apply_directive(self) -> None:
        """
        Apply directive configuration to the fairy.

        Override in subclasses for custom directive handling.
        """
        if not self.directive:
            return

        # Auto-subscribe to topics defined in directive
        for topic in self.directive.subscriptions:
            # Clean up topic format (remove extra spaces, etc.)
            topic = topic.strip().replace(" ", "")
            if topic and hasattr(self, '_on_directive_message'):
                try:
                    self.hub.subscribe(topic, self._on_directive_message)
                except Exception:
                    pass  # Subscription failed, probably no fabric

    def _on_directive_message(self, packet: Dict[str, Any]) -> None:
        """
        Default handler for directive-subscribed topics.

        Override in subclasses for custom message handling.
        """
        # Default: just log receipt
        pass

    def get_directive_text(self) -> str:
        """Get the raw directive text (for use as system prompt)."""
        if self.directive:
            return self.directive.raw_text
        return ""

    def get_directive_purpose(self) -> str:
        """Get the fairy's purpose from directive."""
        if self.directive:
            return self.directive.purpose
        return self.ACTOR_NAME

    def shutdown(self) -> bool:
        """Shutdown the organ fairy."""
        if self.shadow:
            self.shadow.stop()

        return super().shutdown()

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def subscribe(self, topic: str, handler: Callable, name: Optional[str] = None) -> bool:
        """Subscribe to a postal topic."""
        return self.hub.subscribe(topic, handler, name)

    def publish(self, topic: str, payload: Dict[str, Any], priority: int = 1) -> bool:
        """Publish to a postal topic."""
        return self.hub.publish(topic, payload, priority)

    def query(self, target: str, intent: str, payload: Optional[Dict] = None) -> Optional[Dict]:
        """Query another fairy."""
        return self.hub.query(target, intent, payload)

    def get_capabilities(self) -> Set[str]:
        """Override to declare capabilities."""
        return set()

    def update_affect_state(self, **kwargs) -> None:
        """Update the AFFECT_STATE dict."""
        self.AFFECT_STATE.update(kwargs)
        self.AFFECT_STATE["ts"] = time.time()

    def update_somatic_state(self, **kwargs) -> None:
        """Update the SOMATIC_STATE dict."""
        self.SOMATIC_STATE.update(kwargs)
        self.SOMATIC_STATE["ts"] = time.time()


# =============================================================================
# EXPORTS - All symbols that fairies expect from the organ template
# =============================================================================

__all__ = [
    # Core classes
    "MyOrganFairy",
    "MyOrganShadow",
    "TemplateShadowFairy",
    "OrganHubFacet",
    "RegistrationLib",

    # Directive system
    "DirectiveRing",
    "load_directive",
    "find_directive",

    # Utilities
    "resolve_root",

    # Re-exports from fairy_template (for convenience)
    "Fairy",
    "FairyBase",
    "FairyState",
]
