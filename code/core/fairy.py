# Fairy - The Caretaker
# Fairies are caretakers of functions. They monitor, maintain, and report.
# Fairies don't DO the work - they care for the things that do.
#
# Every fairy has:
# - A unique tracer_id
# - A checklist of requirements
# - One or more functions it manages
# - Subscriptions to postal topics
# - Intents that others can invoke

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List, Set
from datetime import datetime
import uuid

from .checklist import Checklist, ChecklistResult
from .function import Function, FunctionStatus


class FairyStatus(Enum):
    """Status of a fairy."""
    INITIALIZING = "initializing"
    AWAKE = "awake"
    SLEEPING = "sleeping"
    FAILED = "failed"


@dataclass
class FairyIntent:
    """An intent that can be invoked on this fairy."""
    name: str
    description: str
    handler: Callable[[Dict[str, Any]], Any]
    required_params: List[str] = field(default_factory=list)


class Fairy:
    """
    Base class for all fairies (caretakers).

    A Fairy manages one or more Functions. It doesn't do the actual work -
    it monitors health, handles messages, and reports status.

    Usage:
        class PostalFairy(Fairy):
            def __init__(self):
                super().__init__(
                    name="PostalFairy",
                    plane="P00",
                    description="Manages the postal message routing system"
                )

                # Create the functions this fairy manages
                self._router = MessageRouterFunction()
                self._dispatcher = DispatcherFunction()

                # Register them
                self.register_function(self._router)
                self.register_function(self._dispatcher)

                # Subscribe to topics
                self.subscribe("postal.send", self._on_send)
                self.subscribe("postal.stats", self._on_stats)

                # Register intents
                self.register_intent("get_stats", "Get postal statistics", self._get_stats)

            def _on_send(self, payload: dict):
                # Use the function to do work
                self._router.call(topic=payload["topic"], data=payload["data"])

            def _get_stats(self, params: dict) -> dict:
                return {"messages": self._router.metrics.calls_total}
    """

    def __init__(
        self,
        name: str,
        plane: str = "P00",
        description: str = "",
        mantra: str = ""
    ):
        # Identity
        self.tracer_id = f"fairy_{name}_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.plane = plane
        self.description = description
        self.mantra = mantra

        # State
        self._status = FairyStatus.INITIALIZING
        self._created_at = datetime.now()

        # Functions this fairy manages
        self._functions: Dict[str, Function] = {}

        # Postal subscriptions
        self._subscriptions: Dict[str, Callable] = {}  # topic -> handler
        self._postal = None  # Set when connected to postal system

        # Intents others can invoke
        self._intents: Dict[str, FairyIntent] = {}

        # Checklist
        self.checklist = Checklist(f"{name}_checklist", owner=self)
        self._add_base_checks()

    def _add_base_checks(self):
        """Add standard checks that all fairies need."""
        self.checklist.add(
            "tracer_id",
            "Tracer ID assigned",
            lambda: self.tracer_id is not None and len(self.tracer_id) > 0
        )
        self.checklist.add(
            "name",
            "Fairy has name",
            lambda: self.name is not None and len(self.name) > 0
        )
        self.checklist.add(
            "not_failed",
            "Fairy not in failed state",
            lambda: self._status != FairyStatus.FAILED
        )
        # Functions check - only if we have functions
        self.checklist.add(
            "functions_ready",
            "All managed functions are ready",
            lambda: all(f.is_ready() for f in self._functions.values()) if self._functions else True
        )

    # ═══════════════════════════════════════════════════════════════════════
    # FUNCTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def register_function(self, function: Function) -> bool:
        """
        Register a function that this fairy manages.

        Args:
            function: The function to manage

        Returns:
            True if registered successfully
        """
        if function.name in self._functions:
            return False  # Already registered

        self._functions[function.name] = function
        return True

    def get_function(self, name: str) -> Optional[Function]:
        """Get a managed function by name."""
        return self._functions.get(name)

    def list_functions(self) -> List[str]:
        """List names of all managed functions."""
        return list(self._functions.keys())

    def function_status(self) -> Dict[str, str]:
        """Get status of all managed functions."""
        return {name: fn.status.value for name, fn in self._functions.items()}

    # ═══════════════════════════════════════════════════════════════════════
    # POSTAL INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════

    def connect_postal(self, postal) -> bool:
        """
        Connect to the postal system.

        Args:
            postal: Postal hub instance with subscribe/publish methods

        Returns:
            True if connected successfully
        """
        self._postal = postal

        # Wire up all pending subscriptions
        for topic, handler in self._subscriptions.items():
            try:
                postal.subscribe(topic, handler)
            except Exception as e:
                print(f"[{self.name}] Failed to subscribe to {topic}: {e}")
                return False

        # FIX 2026-02-13b: Register with HeartbeatRegistry for DIRECT delivery.
        # Previously subscribed to heartbeat.pulse via postal, but that caused
        # QUEUE FULL drops when 70+ fairies all subscribed to the same topic.
        # HeartbeatRegistry delivers via ThreadPoolExecutor — no queue drops.
        # Organ_Template fairies already register in _wire_infrastructure(),
        # so this is a safety net for any fairy using the base Fairy class.
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            _hb_reg = get_heartbeat_registry()
            if _hb_reg:
                _hb_reg.register(self.name, self._on_heartbeat_pulse)
        except (ImportError, Exception):
            pass  # Registry not available during early boot — Organ_Template handles it

        # FIX 2026-02-20: Register in _CITIZEN_OBJECTS so watchdog can see us alive.
        # Without this, core/fairy.py fairies aren't in _CITIZEN_OBJECTS and the
        # watchdog's _check_citizen_liveness() can't inspect _last_tick directly.
        # FIX 2026-02-20b: Don't overwrite if existing instance is actively ticking
        # (same dual-instance protection as consolidated.py).
        try:
            from fairy_template.consolidated import _CITIZEN_OBJECTS
            _existing = _CITIZEN_OBJECTS.get(self.name)
            if _existing is None or getattr(_existing, '_tick_count', 0) == 0:
                _CITIZEN_OBJECTS[self.name] = self
        except ImportError:
            try:
                from fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0 import _CITIZEN_OBJECTS
                _existing = _CITIZEN_OBJECTS.get(self.name)
                if _existing is None or getattr(_existing, '_tick_count', 0) == 0:
                    _CITIZEN_OBJECTS[self.name] = self
            except ImportError:
                pass  # Can't register — watchdog will rely on postal echo

        return True

    def _on_heartbeat_pulse(self, packet):
        """Handle heartbeat pulse: update liveness + rate-limited echo.

        FIX 2026-02-13b: Rate-limited fairy.heartbeat echo to every 10th beat.
        Previously 105 fairies ALL echoed fairy.heartbeat on EVERY beat, creating
        105 messages/beat on the fairy postal pool → QUEUE FULL drops.

        HeartbeatHandler._check_citizen_liveness() reads _last_tick directly
        (no postal needed), so the echo is only for DirectoryFairy's secondary
        tracking. Every 10th beat is plenty for liveness.

        Delivery path: HeartbeatRegistry direct-call → this method.
        (No longer via postal subscription — see connect_postal FIX 2026-02-13b)
        """
        import time as _time
        # PRIMARY: Update liveness timestamp directly on the Python object.
        if not hasattr(self, '_tick_count'):
            self._tick_count = 0
        if not hasattr(self, '_last_tick'):
            self._last_tick = 0.0
        self._tick_count += 1
        self._last_tick = _time.time()

        # SECONDARY: Echo to DirectoryFairy via postal (best-effort, RATE-LIMITED).
        # Only echo every 10th beat — DirectoryFairy just needs to know we're alive,
        # it doesn't need 105 messages per second. _last_tick is the PRIMARY signal.
        if not self._postal:
            return
        if self._tick_count % 10 != 0:
            return  # Skip 9 out of 10 beats — saves ~95% of fairy pool traffic
        try:
            payload = packet.get("payload", packet) if isinstance(packet, dict) else {}
            beat = payload.get("beat", 0) if isinstance(payload, dict) else 0
            self._postal.publish("fairy.heartbeat", {
                "name": self.name,
                "plane": self.plane,
                "beat": beat,
                "ts": self._last_tick,
            })
        except Exception:
            pass  # Postal echo is secondary — _last_tick is primary

    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to a postal topic.

        If already connected to postal, subscribes immediately.
        Otherwise, queues for subscription on connect.
        """
        self._subscriptions[topic] = handler

        if self._postal:
            self._postal.subscribe(topic, handler)

    def publish(self, topic: str, payload: Dict[str, Any]):
        """Publish a message to the postal system."""
        if not self._postal:
            raise RuntimeError(f"Fairy {self.name} not connected to postal")

        # Add sender info
        payload = {
            **payload,
            "_sender": self.name,
            "_tracer_id": self.tracer_id
        }

        self._postal.publish(topic, payload)

    @property
    def subscriptions(self) -> Set[str]:
        """Get set of subscribed topics."""
        return set(self._subscriptions.keys())

    # ═══════════════════════════════════════════════════════════════════════
    # INTENT SYSTEM
    # ═══════════════════════════════════════════════════════════════════════

    def register_intent(
        self,
        name: str,
        description: str,
        handler: Callable[[Dict[str, Any]], Any],
        required_params: List[str] = None
    ):
        """
        Register an intent that others can invoke on this fairy.

        Args:
            name: Intent name (e.g., "get_stats", "restart")
            description: What this intent does
            handler: Function to call when intent is invoked
            required_params: List of required parameter names
        """
        self._intents[name] = FairyIntent(
            name=name,
            description=description,
            handler=handler,
            required_params=required_params or []
        )

    def invoke_intent(self, intent_name: str, params: Dict[str, Any] = None) -> Any:
        """
        Invoke an intent on this fairy.

        Args:
            intent_name: Name of intent to invoke
            params: Parameters to pass to intent handler

        Returns:
            Result from intent handler
        """
        params = params or {}

        if intent_name not in self._intents:
            raise ValueError(f"Unknown intent: {intent_name}")

        intent = self._intents[intent_name]

        # Check required params
        for param in intent.required_params:
            if param not in params:
                raise ValueError(f"Missing required param: {param}")

        return intent.handler(params)

    def list_intents(self) -> Dict[str, str]:
        """List available intents with descriptions."""
        return {name: intent.description for name, intent in self._intents.items()}

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    def boot(self) -> bool:
        """
        Boot this fairy and all its functions.

        Returns:
            True if boot succeeded (all checks passed)
        """
        # Initialize all functions
        for name, fn in self._functions.items():
            if not fn.initialize():
                print(f"[{self.name}] Function {name} failed to initialize")
                self._status = FairyStatus.FAILED
                return False

        # Validate self
        result = self.validate()
        if result.all_passed:
            self._status = FairyStatus.AWAKE
            return True
        else:
            self._status = FairyStatus.FAILED
            print(f"[{self.name}] Boot failed: {result.failures}")
            return False

    def sleep(self):
        """Put this fairy to sleep."""
        self._status = FairyStatus.SLEEPING

    def wake(self) -> bool:
        """Wake this fairy from sleep."""
        if self._status != FairyStatus.SLEEPING:
            return False

        result = self.validate()
        if result.all_passed:
            self._status = FairyStatus.AWAKE
            return True
        else:
            self._status = FairyStatus.FAILED
            return False

    def shutdown(self):
        """Shutdown this fairy and all its functions."""
        # Call subclass on_shutdown hook if defined
        if hasattr(self, 'on_shutdown') and callable(self.on_shutdown):
            try:
                self.on_shutdown()
            except Exception as e:
                print(f"[{self.__class__.__name__}] on_shutdown error: {e}")

        for fn in self._functions.values():
            fn.shutdown()
        self._status = FairyStatus.SLEEPING

    def validate(self) -> ChecklistResult:
        """Run all checks and return result."""
        return self.checklist.run()

    def is_ready(self) -> bool:
        """Quick check: is this fairy ready?"""
        return self._status == FairyStatus.AWAKE and self.checklist.is_valid()

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS & REPORTING
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def status(self) -> FairyStatus:
        return self._status

    @property
    def uptime_seconds(self) -> float:
        return (datetime.now() - self._created_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize fairy state for reporting."""
        return {
            "tracer_id": self.tracer_id,
            "name": self.name,
            "plane": self.plane,
            "description": self.description,
            "status": self._status.value,
            "functions": {name: fn.to_dict() for name, fn in self._functions.items()},
            "subscriptions": list(self._subscriptions.keys()),
            "intents": self.list_intents(),
            "checklist": self.checklist.last_result.to_dict() if self.checklist.last_result else None,
            "uptime_seconds": self.uptime_seconds
        }

    def status_line(self) -> str:
        """One-line status for dashboard display."""
        fn_status = f"{sum(1 for f in self._functions.values() if f.is_ready())}/{len(self._functions)} fn"
        sub_count = len(self._subscriptions)
        intent_count = len(self._intents)
        return f"[{self._status.value.upper():12}] {self.name:30} | {fn_status} | {sub_count} subs | {intent_count} intents"

    def __repr__(self) -> str:
        return f"Fairy({self.name}, status={self._status.value}, functions={len(self._functions)})"
