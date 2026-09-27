"""
Unified Fairy - The Complete Organ Template

Every fairy built on this template automatically has:
- BODY: Somatic + affect state (energy, coherence, emotions)
- SHADOW: Self-monitoring immune system (health, errors, evolution)
- WORKERS: Tracer-tracked parallel execution (blood cells)
- POSTAL: Pub/sub communication (nervous system)
- LEARNING: Observe, reflect, crystallize (growth)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

The fairy system is a body. UMF/Whisper administers the unconscious.
Sourpatches is the conscious mind. Every fairy contributes to the whole.
"""

import time
from typing import Any, Dict, List, Optional

from .body import FairyBody
from .shadow import FairyShadow
from .workers import FairyWorkerPool


class UnifiedFairy:
    """
    The Complete Unified Fairy Template.

    Every fairy built on this template automatically has:
    - body: Somatic + affect state (energy, coherence, emotions)
    - shadow: Self-monitoring immune system (health, errors, evolution)
    - workers: Tracer-tracked parallel execution (blood cells)
    - post: Pub/sub communication (nervous system, set during boot)
    - Learning methods: observe, reflect, crystallize

    Usage:
        class MyFairy(UnifiedFairy):
            ACTOR_NAME = "MyFairy"
            PLANE = "P30"
            CHANNEL = "cognition"
            PURPOSE = "Process cognitive tasks"

            def on_boot(self) -> bool:
                # Custom initialization
                return True

            def on_tick(self, beat: int):
                # Periodic work
                pass
    """

    # =========================================================================
    # IDENTITY - Override in subclass
    # =========================================================================

    ACTOR_NAME: str = "UnifiedFairy"
    PLANE: str = "P00"
    CHANNEL: str = ""
    PURPOSE: str = "Base unified fairy"
    MANTRA: str = ""
    CAPABILITIES: List[str] = []
    SUBSCRIPTIONS: List[str] = []

    # =========================================================================
    # CRITICALITY - Determines spell/sleep behavior
    # =========================================================================
    # "critical" = Must sleep before spells break (system failure if dies)
    #              Examples: HeartbeatFairy, TokenBucketFairy, DirectoryFairy
    # "important" = Should avoid fizzle (degraded function if fails)
    #              Examples: UMF/Whisper, Gates, WorkingMemoryFairy
    # "app" = Can fizzle spells (just restarts when needed)
    #              Examples: Cognition tasks, Sensory extras, feature fairies
    # =========================================================================
    CRITICALITY: str = "app"

    # Energy thresholds based on criticality (used by SpellChain)
    ENERGY_THRESHOLDS = {
        "critical": {"sleep_at": 0.30, "wake_at": 0.70, "fizzle_allowed": False},
        "important": {"sleep_at": 0.20, "wake_at": 0.50, "fizzle_allowed": False},
        "app": {"sleep_at": 0.10, "wake_at": 0.30, "fizzle_allowed": True},
    }

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self):
        """
        Initialize the unified fairy with all components.

        Creates:
        - body: FairyBody for somatic + affect state
        - shadow: FairyShadow for self-monitoring
        - workers: FairyWorkerPool for parallel execution
        - post: None (set during boot from shared postal hub)
        """
        # Built-in components - use ACTOR_NAME from class definition
        self.body = FairyBody(self.ACTOR_NAME)
        self.shadow = FairyShadow(self.ACTOR_NAME)
        self.workers = FairyWorkerPool(self.ACTOR_NAME, max_workers=4)

        # Postal hub - set during boot from shared postal
        self.post: Optional[Any] = None

        # Internal state
        self._running: bool = False
        self._awake: bool = False
        self._boot_time: Optional[float] = None

    # =========================================================================
    # LIFECYCLE METHODS
    # =========================================================================

    def boot(self) -> bool:
        """
        Boot the fairy.

        Initializes all components, wires subscriptions, and calls on_boot() hook.

        Returns:
            True if boot succeeded, False otherwise
        """
        try:
            # Record boot time
            self._boot_time = time.time()

            # Try to get shared postal hub (only if not already set)
            if self.post is None:
                try:
                    from postal_core.python.postal_shim import get_shared_postal
                    self.post = get_shared_postal()
                except ImportError:
                    # Postal not available - that's OK
                    pass

            # Wire subscriptions
            self._wire_subscriptions()

            # Call subclass hook
            hook_result = self.on_boot()
            if hook_result is False:
                return False

            # Mark as running and awake
            self._running = True
            self._awake = True

            return True

        except Exception as e:
            self.log(f"Boot failed: {e}", level="error")
            return False

    def shutdown(self) -> bool:
        """
        Shutdown the fairy.

        Calls on_shutdown() hook, cleans up workers, and releases resources.

        Returns:
            True if shutdown succeeded, False otherwise
        """
        try:
            # Call subclass hook
            self.on_shutdown()

            # Shutdown workers
            self.workers.shutdown(wait=False)

            # Mark as not running
            self._running = False
            self._awake = False

            return True

        except Exception as e:
            self.log(f"Shutdown failed: {e}", level="error")
            return False

    def on_boot(self) -> bool:
        """
        Called after base boot sequence completes.

        Override to add custom initialization.

        Returns:
            True if boot succeeded, False to fail boot
        """
        return True

    def on_shutdown(self) -> bool:
        """
        Called during shutdown.

        Override to add custom cleanup.

        Returns:
            True if shutdown succeeded
        """
        return True

    def on_tick(self, beat: int) -> None:
        """
        Called on each heartbeat.

        Override to add periodic work.

        Args:
            beat: Current beat number
        """
        pass

    def _wire_subscriptions(self) -> None:
        """
        Wire postal subscriptions.

        Called during boot to set up message handlers.

        Addressing System:
        - ID = ACTOR_NAME (who you are)
        - PLANE = city (P00-P60)
        - CHANNEL = address (your mailbox)

        Automatically subscribes to:
        1. Own channel: {PLANE}.{CHANNEL} (your address)
        2. Direct messages: {PLANE}.{CHANNEL}.{ACTOR_NAME}
        3. Additional SUBSCRIPTIONS (other channels to listen to)

        NO CROSS TALK: Never call fairies directly, only through postal.
        """
        if self.post is None:
            return

        # 1. Subscribe to own channel (your mailbox)
        if self.CHANNEL:
            own_channel = self.postal_address
            try:
                if hasattr(self.post, 'subscribe'):
                    self.post.subscribe(own_channel, self._on_message)
                    self.log(f"Subscribed to own channel: {own_channel}", level="debug")
            except Exception:
                pass

            # 2. Subscribe to direct messages (addressed specifically to you)
            direct_channel = f"{own_channel}.{self.ACTOR_NAME}"
            try:
                if hasattr(self.post, 'subscribe'):
                    self.post.subscribe(direct_channel, self._on_direct_message)
            except Exception:
                pass

        # 3. Subscribe to additional topics from SUBSCRIPTIONS
        for topic in self.SUBSCRIPTIONS:
            try:
                if hasattr(self.post, 'subscribe'):
                    self.post.subscribe(topic, self._on_message)
            except Exception:
                pass  # Subscription failed - continue

    def _on_message(self, envelope: Dict[str, Any]) -> None:
        """
        Handle incoming postal message to channel.

        Override to handle specific message types.

        Args:
            envelope: Message envelope with topic and payload
        """
        pass

    def _on_direct_message(self, envelope: Dict[str, Any]) -> None:
        """
        Handle direct message addressed specifically to this fairy.

        Override to handle direct messages.

        Args:
            envelope: Message envelope with topic and payload
        """
        # Default: treat as regular message
        self._on_message(envelope)

    # =========================================================================
    # POSTAL ADDRESSING - No cross talk, only through channels
    # =========================================================================

    @property
    def postal_address(self) -> str:
        """
        This fairy's postal address: {PLANE}.{CHANNEL}

        ID = ACTOR_NAME (who you are)
        PLANE = city (where you live)
        CHANNEL = address (your mailbox)
        """
        if self.CHANNEL:
            return f"{self.PLANE}.{self.CHANNEL}"
        return self.PLANE

    @property
    def full_address(self) -> str:
        """Full address including name: {PLANE}.{CHANNEL}.{ACTOR_NAME}"""
        return f"{self.postal_address}.{self.ACTOR_NAME}"

    def send_to(self, channel: str, payload: Dict[str, Any]) -> bool:
        """
        Send message to another channel (NO direct fairy calls).

        Args:
            channel: Target channel (e.g., "P30.cognition" or "memory.stream")
            payload: Message payload

        Returns:
            True if sent, False if postal unavailable
        """
        if self.post is None:
            return False

        # Add sender info
        enriched = {
            "from": self.full_address,
            "from_plane": self.PLANE,
            "from_fairy": self.ACTOR_NAME,
            **payload,
        }

        try:
            if hasattr(self.post, 'publish'):
                self.post.publish(channel, enriched)
                return True
            elif hasattr(self.post, 'route'):
                self.post.route(channel, enriched)
                return True
        except Exception:
            pass

        return False

    def broadcast(self, payload: Dict[str, Any]) -> bool:
        """
        Broadcast message on own channel for others to hear.

        Args:
            payload: Message payload

        Returns:
            True if broadcast, False if postal unavailable
        """
        return self.send_to(self.postal_address, payload)

    # =========================================================================
    # LEARNING METHODS
    # =========================================================================

    def observe(
        self,
        action: str,
        input_summary: str = "",
        output_summary: str = "",
        success: bool = True,
        duration_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Record an observation about an action.

        Delegates to shadow and emits to postal.

        Args:
            action: What action was taken
            input_summary: Brief summary of input
            output_summary: Brief summary of output
            success: Did it succeed?
            duration_ms: How long it took

        Returns:
            The observation record
        """
        # Record to shadow
        self.shadow.record_observation()
        if success:
            self.shadow.record_success({"action": action})
        else:
            # Create a simple exception for the error record
            self.shadow.record_error(Exception(f"Action failed: {action}"))

        # Build observation record
        observation = {
            "ts": time.time(),
            "fairy": self.ACTOR_NAME,
            "action": action,
            "input": input_summary,
            "output": output_summary,
            "success": success,
            "duration_ms": duration_ms,
        }

        # Emit to postal if connected
        if self.post is not None:
            try:
                self.post.publish("telemetry.learning.observation", {
                    "fairy": self.ACTOR_NAME,
                    "observation": observation,
                })
            except Exception:
                pass  # Postal emit failed - continue

        return observation

    def reflect(
        self,
        topic: str,
        thought: str,
        insight_type: str = "general",
        confidence: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Submit a reflection for pondering.

        Delegates to shadow and emits to postal.

        Args:
            topic: What the reflection is about
            thought: The actual reflection/insight
            insight_type: Type of insight (general, mistake, pattern, improvement)
            confidence: How confident in this insight (0.0-1.0)

        Returns:
            The reflection record
        """
        # Record to shadow
        self.shadow.record_reflection()

        # Build reflection record
        reflection = {
            "ts": time.time(),
            "fairy": self.ACTOR_NAME,
            "topic": topic,
            "thought": thought,
            "type": insight_type,
            "confidence": confidence,
        }

        # Emit to postal if connected
        if self.post is not None:
            try:
                self.post.publish("shadow.reflection_pool", {
                    "fairy": self.ACTOR_NAME,
                    "reflection": reflection,
                })
            except Exception:
                pass  # Postal emit failed - continue

        return reflection

    def crystallize(
        self,
        learning_type: str,
        content: str,
        confidence: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Emit a crystallized learning.

        Creates a persisted learning record from observations/reflections.

        Args:
            learning_type: Type of learning (pattern, rule, insight, mistake)
            content: The learning itself
            confidence: How confident in this learning

        Returns:
            The learning record
        """
        # Record to shadow
        self.shadow.record_crystallization()

        # Build learning record
        learning = {
            "ts": time.time(),
            "fairy": self.ACTOR_NAME,
            "type": learning_type,
            "content": content,
            "confidence": confidence,
            "plane": self.PLANE,
        }

        # Emit to postal if connected (to SRM intake)
        if self.post is not None:
            try:
                self.post.publish("memory.stream", {
                    "opcode": "SRM_INTAKE_WRITE",
                    "payload": {
                        "kind": f"learning.{learning_type}",
                        "data": learning,
                        "meta": {"fairy": self.ACTOR_NAME, "plane": self.PLANE},
                    }
                })
            except Exception:
                pass  # Postal emit failed - continue

        return learning

    # =========================================================================
    # STATE METHODS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """
        Get full fairy status.

        Returns:
            Dictionary with identity, state, and component statuses
        """
        return {
            # Identity
            "name": self.ACTOR_NAME,
            "plane": self.PLANE,
            "channel": self.CHANNEL,
            "purpose": self.PURPOSE,
            # State
            "is_running": self._running,
            "is_awake": self._awake,
            "uptime": self.uptime,
            # Components
            "body": self.body.to_dict(),
            "shadow": self.shadow.to_dict(),
            "workers": self.workers.get_stats(),
        }

    def log(self, message: str, level: str = "info") -> None:
        """
        Log a message with fairy prefix.

        Args:
            message: Log message
            level: Log level (info, warn, error, debug)
        """
        prefix = f"[{self.ACTOR_NAME}]"
        if level == "error":
            print(f"{prefix} ERROR: {message}")
        elif level == "warn":
            print(f"{prefix} WARN: {message}")
        elif level == "debug":
            pass  # Suppress debug by default
        else:
            print(f"{prefix} {message}")

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def is_running(self) -> bool:
        """True if fairy is running."""
        return self._running

    @property
    def is_awake(self) -> bool:
        """True if fairy is awake (not in sleep mode)."""
        return self._awake

    @property
    def uptime(self) -> float:
        """Seconds since boot (0 if not booted)."""
        if self._boot_time is None:
            return 0.0
        return time.time() - self._boot_time

    # =========================================================================
    # CRITICALITY METHODS - Energy management based on importance
    # =========================================================================

    @property
    def energy_thresholds(self) -> Dict[str, Any]:
        """Get energy thresholds for this fairy's criticality level."""
        return self.ENERGY_THRESHOLDS.get(
            self.CRITICALITY,
            self.ENERGY_THRESHOLDS["app"]  # Default to app if unknown
        )

    @property
    def should_sleep(self) -> bool:
        """
        True if fairy should enter sleep mode based on energy and criticality.

        Critical fairies sleep at 30% energy (proactive preservation).
        Important fairies sleep at 20% energy.
        App fairies sleep at 10% energy (can fizzle instead).
        """
        threshold = self.energy_thresholds["sleep_at"]
        return self.body.energy < threshold

    @property
    def can_fizzle(self) -> bool:
        """True if this fairy's spells are allowed to fizzle (app-level only)."""
        return self.energy_thresholds.get("fizzle_allowed", True)

    @property
    def is_critical(self) -> bool:
        """True if this fairy is system-critical (cannot fizzle)."""
        return self.CRITICALITY == "critical"

    def check_energy_status(self) -> Dict[str, Any]:
        """
        Check current energy status against criticality thresholds.

        Returns dict with:
        - energy: Current energy level
        - criticality: Fairy's criticality level
        - should_sleep: Whether fairy should sleep now
        - can_fizzle: Whether fizzle is allowed
        - status: "healthy", "warning", or "critical"
        """
        energy = self.body.energy
        thresholds = self.energy_thresholds
        sleep_at = thresholds["sleep_at"]
        wake_at = thresholds["wake_at"]

        if energy >= wake_at:
            status = "healthy"
        elif energy >= sleep_at:
            status = "warning"
        else:
            status = "critical"

        return {
            "energy": energy,
            "criticality": self.CRITICALITY,
            "should_sleep": energy < sleep_at,
            "can_fizzle": thresholds["fizzle_allowed"],
            "status": status,
            "thresholds": thresholds,
        }
