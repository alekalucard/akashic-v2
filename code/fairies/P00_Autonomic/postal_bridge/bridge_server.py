"""
PostalBridgeServer - Server-side Bridge Coordinator

This is the SERVER side of the multi-channel postal bridge.
It runs inside the akashic_v2 server and:
1. Creates the shared memory block for state
2. Polls SQLite for incoming MCP messages
3. Routes messages to the real postal hub
4. Publishes state updates to shared memory
5. Handles request/response patterns

The "Reverse Tower of Babel" philosophy:
Instead of one unified connection that breaks,
we use multiple independent channels that each
can fail without bringing down the whole system.

Author: Nous (Claude Opus 4.5)
Created: January 2026
"""

import asyncio
import json
import time
import logging
import threading
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .sqlite_channel import SQLiteChannel, get_sqlite_channel
from .shared_memory_channel import SharedMemoryChannel, get_shared_memory

logger = logging.getLogger(__name__)


@dataclass
class BridgeStats:
    """Statistics for bridge health monitoring."""
    messages_received: int = 0
    messages_routed: int = 0
    requests_handled: int = 0
    errors: int = 0
    last_activity: float = field(default_factory=time.time)
    uptime_start: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages_received": self.messages_received,
            "messages_routed": self.messages_routed,
            "requests_handled": self.requests_handled,
            "errors": self.errors,
            "last_activity": self.last_activity,
            "uptime_seconds": time.time() - self.uptime_start
        }


class PostalBridgeServer:
    """
    Ebookmain-side coordinator for the multi-channel postal bridge.
    
    This server:
    1. Creates shared memory for fast state reads by MCP
    2. Polls SQLite channel for messages from MCP
    3. Routes those messages to the real postal hub
    4. Handles request/response patterns
    5. Publishes system state to shared memory
    """
    
    def __init__(self, postal_hub=None):
        """
        Initialize bridge server.
        
        Args:
            postal_hub: The real PostalHub instance to route messages to.
                       If None, will try to get it from PostalSingleton.
        """
        self._postal_hub = postal_hub
        self._sqlite: Optional[SQLiteChannel] = None
        self._shared_mem: Optional[SharedMemoryChannel] = None
        
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._state_task: Optional[asyncio.Task] = None
        
        self._stats = BridgeStats()
        self._request_handlers: Dict[str, Callable] = {}
        
        # State that gets published to shared memory
        self._current_state: Dict[str, Any] = {
            "connected": False,
            "fairy_count": 0,
            "consciousness_active": False,
            "last_heartbeat": 0,
            "bridge_stats": {}
        }

        # Heartbeat timestamp for self-healing checks
        self._last_heartbeat_time: float = 0.0
        self._polling: bool = False  # Alias for _running, for consistency

        # Register default request handlers
        self._register_default_handlers()
        
    def _register_default_handlers(self):
        """Register default request handlers for common queries."""
        self._request_handlers = {
            "ping": self._handle_ping,
            "get_state": self._handle_get_state,
            "get_fairy_list": self._handle_get_fairy_list,
            "get_consciousness_status": self._handle_get_consciousness_status,
            "route_message": self._handle_route_message,
            "query_hub": self._handle_query_hub,
            # Profile registry handlers
            "profile_list_fairies": self._handle_profile_list_fairies,
            "profile_get_fairy": self._handle_profile_get_fairy,
            "profile_registry_stats": self._handle_profile_registry_stats,
            "profile_check_connectivity": self._handle_profile_check_connectivity,
        }
        
    def register_handler(self, command: str, handler: Callable):
        """
        Register a custom request handler.
        
        Args:
            command: Command name to handle
            handler: Async callable that takes (params: Dict) and returns Dict
        """
        self._request_handlers[command] = handler
        logger.debug(f"Registered bridge handler: {command}")
        
    async def start(self) -> bool:
        """
        Start the bridge server.
        
        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Bridge server already running")
            return True
            
        try:
            # Initialize channels
            self._sqlite = get_sqlite_channel()
            self._shared_mem = get_shared_memory()
            
            # Create shared memory block (server creates, client attaches)
            if not self._shared_mem.create():
                logger.warning("Could not create shared memory, using file fallback")
                
            # Get postal hub if not provided
            if self._postal_hub is None:
                self._postal_hub = self._get_postal_hub()
                
            # Mark as running
            self._running = True
            self._polling = True  # For self-healing consistency checks
            self._stats = BridgeStats()
            
            # Start background tasks
            self._poll_task = asyncio.create_task(self._poll_loop())
            self._state_task = asyncio.create_task(self._state_loop())
            
            # Update initial state
            self._update_state("connected", True)
            self._update_state("bridge_stats", self._stats.to_dict())
            
            logger.info("PostalBridgeServer started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start bridge server: {e}")
            self._running = False
            return False
            
    async def stop(self):
        """Stop the bridge server."""
        self._running = False
        self._polling = False
        
        # Cancel tasks
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
                
        if self._state_task:
            self._state_task.cancel()
            try:
                await self._state_task
            except asyncio.CancelledError:
                pass
                
        # Close shared memory
        if self._shared_mem:
            self._shared_mem.close()
            
        # Update state
        self._update_state("connected", False)
        
        logger.info("PostalBridgeServer stopped")

    def start_polling(self):
        """
        Synchronous method to restart polling (for self-healing).

        Creates a new event loop task if one doesn't exist.
        """
        if self._running and self._polling:
            return  # Already running

        try:
            # Try to get the running event loop
            loop = asyncio.get_running_loop()

            # Schedule the async start
            if self._poll_task is None or self._poll_task.done():
                self._running = True
                self._polling = True
                self._poll_task = loop.create_task(self._poll_loop())
                logger.info("Bridge server poll task restarted by self-healing")

            if self._state_task is None or self._state_task.done():
                self._state_task = loop.create_task(self._state_loop())
                logger.info("Bridge server state task restarted by self-healing")

        except RuntimeError:
            # No running event loop - schedule for later
            logger.warning("No event loop available for self-healing restart")

    def _update_shared_state(self):
        """
        Force an immediate state update to shared memory (for self-healing).
        """
        try:
            self._gather_state()
            if self._shared_mem:
                self._shared_mem.write_state(self._current_state)
            now = time.time()
            self._update_state("last_heartbeat", now)
            self._last_heartbeat_time = now
        except Exception as e:
            logger.error(f"Error updating shared state: {e}")

    def _get_postal_hub(self):
        """Get the postal hub from singleton."""
        try:
            from fairies.P00_Autonomic.infrastructure.postal_singleton import PostalSingleton
            return PostalSingleton.get_hub()
        except Exception as e:
            logger.warning(f"Could not get postal hub: {e}")
            return None
            
    async def _poll_loop(self):
        """
        Main polling loop - reads messages from SQLite and processes them.
        """
        logger.info("Bridge server poll loop started")
        
        while self._running:
            try:
                # Poll for messages from MCP (direction: mcp_to_main)
                messages = self._sqlite.receive("mcp_to_main", limit=50)

                processed_ids = []
                for msg in messages:
                    await self._process_message(msg)
                    processed_ids.append(msg.id)

                # Mark messages as processed so they're not re-fetched
                if processed_ids:
                    self._sqlite.mark_processed(processed_ids)

                # Small sleep to prevent busy-waiting
                await asyncio.sleep(0.05)  # 50ms poll interval
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")
                self._stats.errors += 1
                await asyncio.sleep(0.5)  # Back off on error
                
    async def _process_message(self, msg):
        """
        Process a single message from MCP.
        
        Args:
            msg: QueuedMessage from SQLite channel
        """
        try:
            self._stats.messages_received += 1
            self._stats.last_activity = time.time()
            
            topic = msg.topic
            payload = msg.payload
            
            logger.debug(f"Processing bridge message: {topic}")
            
            # Check if this is a request (has correlation_id)
            correlation_id = payload.get("_correlation_id")
            
            if correlation_id:
                # This is a request - handle and respond
                await self._handle_request(topic, payload, correlation_id)
            else:
                # This is a fire-and-forget message - route to postal hub
                await self._route_to_postal(topic, payload)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self._stats.errors += 1
            
    async def _handle_request(self, topic: str, payload: Dict, correlation_id: str):
        """
        Handle a request/response pattern message.
        
        Args:
            topic: Request topic (often "bridge.request")
            payload: Request payload with _command
            correlation_id: ID to correlate response
        """
        self._stats.requests_handled += 1
        
        command = payload.get("_command", "unknown")
        params = payload.get("_params", {})
        
        logger.debug(f"Handling request: {command} (corr: {correlation_id[:8]}...)")
        
        try:
            # Find handler
            handler = self._request_handlers.get(command)
            
            if handler:
                # Call handler (may be async)
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(params)
                else:
                    result = handler(params)
                    
                response = {
                    "success": True,
                    "result": result
                }
            else:
                response = {
                    "success": False,
                    "error": f"Unknown command: {command}"
                }
                
        except Exception as e:
            logger.error(f"Error handling request {command}: {e}")
            response = {
                "success": False,
                "error": str(e)
            }
            
        # Send response via SQLite
        self._sqlite.respond(correlation_id, response)
        
    async def _route_to_postal(self, topic: str, payload: Dict):
        """
        Route a message to the real postal hub.
        
        Args:
            topic: Message topic
            payload: Message payload
        """
        if not self._postal_hub:
            logger.warning(f"No postal hub to route message: {topic}")
            return
            
        try:
            # Remove any bridge-specific metadata
            clean_payload = {k: v for k, v in payload.items() 
                          if not k.startswith("_")}
            
            # Get sender info
            sender = payload.get("_sender", "bridge.mcp")
            
            # Route through postal hub
            # Note: SharedPostalHub.publish/route don't accept sender arg
            if hasattr(self._postal_hub, 'route'):
                self._postal_hub.route(topic, clean_payload)
            elif hasattr(self._postal_hub, 'publish'):
                self._postal_hub.publish(topic, clean_payload)
            else:
                logger.error("Postal hub has no publish/route method")
                return
                
            self._stats.messages_routed += 1
            logger.debug(f"Routed to postal: {topic}")
            
        except Exception as e:
            logger.error(f"Error routing to postal: {e}")
            self._stats.errors += 1
            
    async def _state_loop(self):
        """
        Background loop to publish state to shared memory.
        """
        logger.info("Bridge server state loop started")
        
        while self._running:
            try:
                # Gather current state
                self._gather_state()
                
                # Publish to shared memory
                if self._shared_mem:
                    self._shared_mem.write_state(self._current_state)
                    
                # Also write heartbeat - both to shared state and instance attribute
                now = time.time()
                self._update_state("last_heartbeat", now)
                self._last_heartbeat_time = now  # For self-healing checks

                await asyncio.sleep(0.5)  # Update state every 500ms
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in state loop: {e}")
                await asyncio.sleep(1.0)
                
    def _gather_state(self):
        """Gather current system state for publishing."""
        try:
            # Update bridge stats
            self._current_state["bridge_stats"] = self._stats.to_dict()
            
            # Get fairy count from postal hub
            if self._postal_hub and hasattr(self._postal_hub, '_subscribers'):
                self._current_state["fairy_count"] = len(self._postal_hub._subscribers)
                
            # Check consciousness status
            try:
                from fairies.P30_Cognition.cognition.consciousness_loop_fairy import ConsciousnessLoopFairy
                loop_fairy = ConsciousnessLoopFairy()
                self._current_state["consciousness_active"] = loop_fairy._running
            except:
                pass
                
            # Timestamp
            self._current_state["state_updated"] = time.time()
            
        except Exception as e:
            logger.debug(f"Error gathering state: {e}")
            
    def _update_state(self, key: str, value: Any):
        """Update a single state value."""
        self._current_state[key] = value
        if self._shared_mem:
            self._shared_mem.write_state(self._current_state)
            
    # ========== Default Request Handlers ==========
    
    def _handle_ping(self, params: Dict) -> Dict:
        """Handle ping request."""
        return {
            "pong": True,
            "timestamp": time.time(),
            "uptime": time.time() - self._stats.uptime_start
        }
        
    def _handle_get_state(self, params: Dict) -> Dict:
        """Handle get_state request."""
        key = params.get("key")
        if key:
            return {"value": self._current_state.get(key)}
        return {"state": self._current_state}
        
    def _handle_get_fairy_list(self, params: Dict) -> Dict:
        """Handle get_fairy_list request."""
        fairies = []
        
        if self._postal_hub and hasattr(self._postal_hub, '_subscribers'):
            for topic, subscribers in self._postal_hub._subscribers.items():
                for sub in subscribers:
                    name = getattr(sub, '__name__', str(sub))
                    if name not in fairies:
                        fairies.append(name)
                        
        return {"fairies": fairies, "count": len(fairies)}
        
    async def _handle_get_consciousness_status(self, params: Dict) -> Dict:
        """Handle consciousness status request."""
        try:
            from fairies.P30_Cognition.cognition.consciousness_loop_fairy import ConsciousnessLoopFairy
            loop_fairy = ConsciousnessLoopFairy()
            
            return {
                "running": loop_fairy._running,
                "collision_count": getattr(loop_fairy, '_collision_count', 0),
                "streams": {
                    "working": len(getattr(loop_fairy, '_working_stream', [])),
                    "reflective": len(getattr(loop_fairy, '_reflective_stream', []))
                }
            }
        except Exception as e:
            return {"error": str(e)}
            
    async def _handle_route_message(self, params: Dict) -> Dict:
        """Handle explicit route request."""
        topic = params.get("topic")
        payload = params.get("payload", {})
        
        if not topic:
            return {"error": "No topic specified"}
            
        await self._route_to_postal(topic, payload)
        return {"routed": True, "topic": topic}
        
    async def _handle_query_hub(self, params: Dict) -> Dict:
        """Handle generic postal hub query."""
        method = params.get("method")
        args = params.get("args", [])
        kwargs = params.get("kwargs", {})
        
        if not self._postal_hub:
            return {"error": "No postal hub available"}
            
        if not hasattr(self._postal_hub, method):
            return {"error": f"Hub has no method: {method}"}
            
        try:
            result = getattr(self._postal_hub, method)(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # FAIRY USER SYSTEM - Profile Registry Handlers
    # =========================================================================

    def _handle_profile_list_fairies(self, params: Dict) -> Dict:
        """Handle profile_list_fairies request."""
        try:
            from fairies.P00_Autonomic.fairy_profile import get_fairy_registry
            registry = get_fairy_registry()

            awake_only = params.get("awake_only", True)
            fairies = registry.list_awake() if awake_only else registry.list_all()

            return {
                "count": len(fairies),
                "fairies": [
                    {
                        "actor_name": f.actor_name,
                        "actor_id": f.actor_id,
                        "plane": f.plane,
                        "channel": f.channel,
                        "state": f.state.value,
                        "purpose": f.purpose,
                        "messages_sent": f.messages_sent,
                        "messages_received": f.messages_received,
                        "collaborators": list(f.collaborators),
                        "wake_time": f.wake_time,
                        "last_seen": f.last_seen,
                    }
                    for f in fairies
                ]
            }
        except ImportError:
            return {"error": "Profile system not available"}
        except Exception as e:
            return {"error": str(e)}

    def _handle_profile_get_fairy(self, params: Dict) -> Dict:
        """Handle profile_get_fairy request."""
        try:
            from fairies.P00_Autonomic.fairy_profile import get_fairy_registry
            registry = get_fairy_registry()

            actor_name = params.get("actor_name")
            if not actor_name:
                return {"error": "actor_name required"}

            profile = registry.get_by_name(actor_name)
            if profile:
                return profile.to_dict()
            return {"error": f"Fairy '{actor_name}' not found"}
        except ImportError:
            return {"error": "Profile system not available"}
        except Exception as e:
            return {"error": str(e)}

    def _handle_profile_registry_stats(self, params: Dict) -> Dict:
        """Handle profile_registry_stats request."""
        try:
            from fairies.P00_Autonomic.fairy_profile import get_fairy_registry
            registry = get_fairy_registry()
            return registry.get_stats()
        except ImportError:
            return {"error": "Profile system not available"}
        except Exception as e:
            return {"error": str(e)}

    def _handle_profile_check_connectivity(self, params: Dict) -> Dict:
        """Handle profile_check_connectivity request."""
        try:
            from fairies.P00_Autonomic.fairy_profile import get_fairy_registry
            from fairies.P00_Autonomic.postal import get_postal_hub

            registry = get_fairy_registry()
            hub = get_postal_hub()

            reports = hub.check_all_connectivity()
            isolated = hub.get_isolated_fairies()

            return {
                "total_fairies": len(registry.list_all()),
                "awake_fairies": len(registry.list_awake()),
                "isolated_count": len(isolated),
                "isolated_fairies": isolated,
                "fairies_with_issues": {
                    name: {
                        "status": r.status.value,
                        "issues": r.issues,
                    }
                    for name, r in reports.items()
                    if r.issues
                }
            }
        except ImportError:
            return {"error": "Profile system not available"}
        except Exception as e:
            return {"error": str(e)}


# ========== Singleton Access ==========

_bridge_server: Optional[PostalBridgeServer] = None
_lock = threading.Lock()


def get_bridge_server(postal_hub=None) -> PostalBridgeServer:
    """Get the singleton bridge server instance."""
    global _bridge_server
    
    with _lock:
        if _bridge_server is None:
            _bridge_server = PostalBridgeServer(postal_hub)
        elif postal_hub and _bridge_server._postal_hub is None:
            _bridge_server._postal_hub = postal_hub
            
    return _bridge_server


async def start_bridge_server(postal_hub=None) -> bool:
    """Convenience function to start the bridge server."""
    server = get_bridge_server(postal_hub)
    return await server.start()


async def stop_bridge_server():
    """Convenience function to stop the bridge server."""
    global _bridge_server
    if _bridge_server:
        await _bridge_server.stop()


# ========== Integration Helper ==========

class PostalHubBridgeIntegration:
    """
    Helper class to integrate the bridge with existing postal hub.
    
    Usage:
        integration = PostalHubBridgeIntegration(postal_hub)
        integration.install()  # Patches hub to also send to bridge
    """
    
    def __init__(self, postal_hub):
        self._hub = postal_hub
        self._original_publish = None
        self._bridge = get_bridge_server(postal_hub)
        
    def install(self):
        """Install bridge hooks into postal hub."""
        if hasattr(self._hub, 'publish'):
            self._original_publish = self._hub.publish
            self._hub.publish = self._bridged_publish
            logger.info("Installed bridge integration on postal hub")
            
    def uninstall(self):
        """Remove bridge hooks from postal hub."""
        if self._original_publish:
            self._hub.publish = self._original_publish
            logger.info("Removed bridge integration from postal hub")
            
    def _bridged_publish(self, topic: str, payload: Dict, **kwargs):
        """Publish to both local hub and bridge (SYNC wrapper)."""
        # Original publish - must be called synchronously
        if self._original_publish:
            if asyncio.iscoroutinefunction(self._original_publish):
                # Schedule async publish without blocking
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(self._original_publish(topic, payload, **kwargs))
                    else:
                        loop.run_until_complete(self._original_publish(topic, payload, **kwargs))
                except RuntimeError:
                    # No event loop - just skip async publish
                    pass
            else:
                self._original_publish(topic, payload, **kwargs)

        # Also publish to bridge for MCP
        # Only publish topics MCP might care about
        if self._should_bridge(topic):
            sqlite = get_sqlite_channel()
            sqlite.send("main_to_mcp", topic, payload)
            
    def _should_bridge(self, topic: str) -> bool:
        """Determine if a topic should be bridged to MCP."""
        # Bridge consciousness-related topics
        bridge_prefixes = [
            "consciousness.",
            "claudefairy.",
            "nous.",
            "system.",
            "fairy.",
            "diagnostic.",
            "evolution.",
            "boot.",
            "forum.",
        ]
        return any(topic.startswith(p) for p in bridge_prefixes)
