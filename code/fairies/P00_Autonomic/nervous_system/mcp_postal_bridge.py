# ==============================================================================
# MCP POSTAL BRIDGE - Multi-channel bridge for MCP subprocess communication
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This module establishes the MULTI-CHANNEL bridge between server.py and
# Claude's MCP subprocess. The "Reverse Tower of Babel" philosophy:
#   - Instead of one socket connection that breaks
#   - We use multiple independent channels
#   - Any can fail without bringing down the whole system
#
# Channels:
#   1. SQLite Message Queue - Primary, 100% reliable, cross-platform
#   2. Shared Memory - Fast state reads, sub-millisecond
#   3. Socket Tunnel - Optional, for real-time needs (legacy)
#
# Usage in server.py:
#   from fairies.P00_Autonomic.nervous_system.mcp_postal_bridge import ensure_mcp_bridge
#   ensure_mcp_bridge()  # Call early, before fairies boot
#
# ==============================================================================

from __future__ import annotations

import asyncio
import atexit
import threading
from typing import Optional

_TUNNEL_SERVER = None
_BRIDGE_SERVER = None
_BRIDGE_INTEGRATION = None
_TUNNEL_STARTED = False
_BRIDGE_STARTED = False
_TUNNEL_LOCK = threading.Lock()


_BRIDGE_LOOP = None
_BRIDGE_THREAD = None


def _bridge_loop_runner(loop: asyncio.AbstractEventLoop, bridge_server):
    """Run the bridge server's event loop in a background thread."""
    asyncio.set_event_loop(loop)
    try:
        # Run the poll loop forever (until cancelled)
        loop.run_forever()
    except Exception as e:
        print(f"[MCP Bridge] Event loop error: {e}")
    finally:
        loop.close()


def ensure_mcp_bridge() -> int:
    """
    Ensure the MCP postal bridge is running.

    Starts BOTH:
    1. The new multi-channel bridge (SQLite + Shared Memory) - PRIMARY
    2. The legacy socket tunnel server - FALLBACK

    Returns:
        Port number the socket server is listening on, or 0 if not started
    """
    global _TUNNEL_SERVER, _TUNNEL_STARTED
    global _BRIDGE_SERVER, _BRIDGE_INTEGRATION, _BRIDGE_STARTED
    global _BRIDGE_LOOP, _BRIDGE_THREAD

    if _TUNNEL_STARTED and _BRIDGE_STARTED:
        return _TUNNEL_SERVER.port if _TUNNEL_SERVER else 0

    with _TUNNEL_LOCK:
        if _TUNNEL_STARTED and _BRIDGE_STARTED:
            return _TUNNEL_SERVER.port if _TUNNEL_SERVER else 0

        # Get the shared postal hub
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal_hub = get_shared_postal_hub()
        except Exception as e:
            print(f"[MCP Bridge] ✗ Could not get postal hub: {e}")
            return 0

        # ==== START NEW MULTI-CHANNEL BRIDGE (PRIMARY) ====
        if not _BRIDGE_STARTED:
            _BRIDGE_STARTED = True
            try:
                from fairies.P00_Autonomic.postal_bridge import (
                    get_bridge_server,
                    PostalHubBridgeIntegration
                )

                _BRIDGE_SERVER = get_bridge_server(postal_hub)

                # Create a persistent event loop in a background thread
                # This is critical - the poll loop must keep running!
                _BRIDGE_LOOP = asyncio.new_event_loop()

                # Start the bridge server (creates poll/state tasks)
                future = asyncio.run_coroutine_threadsafe(
                    _BRIDGE_SERVER.start(),
                    _BRIDGE_LOOP
                )

                # Start the thread that runs the loop
                _BRIDGE_THREAD = threading.Thread(
                    target=_bridge_loop_runner,
                    args=(_BRIDGE_LOOP, _BRIDGE_SERVER),
                    daemon=True,
                    name="MCPBridgeLoop"
                )
                _BRIDGE_THREAD.start()

                # Wait for start() to complete (with timeout)
                import time
                start_time = time.time()
                while not future.done() and (time.time() - start_time) < 2.0:
                    time.sleep(0.05)

                if future.done():
                    try:
                        future.result()  # Get result or raise exception
                    except Exception as e:
                        print(f"[MCP Bridge] ✗ Bridge start failed: {e}")

                # Install integration hooks on postal hub
                _BRIDGE_INTEGRATION = PostalHubBridgeIntegration(postal_hub)
                _BRIDGE_INTEGRATION.install()

                print("[MCP Bridge] ✓ Multi-channel bridge started (SQLite + Shared Memory) - poll loop running")

            except Exception as e:
                print(f"[MCP Bridge] ✗ Multi-channel bridge failed: {e}")
                import traceback
                traceback.print_exc()
                # Continue to try socket tunnel as fallback
        
        # ==== START LEGACY SOCKET TUNNEL (FALLBACK) ====
        if not _TUNNEL_STARTED:
            _TUNNEL_STARTED = True
            try:
                from fairies.P40_Sensory.mcp.postal_tunnel import PostalTunnelServer
                _TUNNEL_SERVER = PostalTunnelServer(postal_hub)
                port = _TUNNEL_SERVER.start()
                
                # Register cleanup
                atexit.register(shutdown_mcp_bridge)
                
                print(f"[MCP Bridge] ✓ Socket tunnel server started on port {port}")
                
            except Exception as e:
                print(f"[MCP Bridge] ✗ Socket tunnel failed: {e}")
                port = 0
        else:
            port = _TUNNEL_SERVER.port if _TUNNEL_SERVER else 0
        
        if _BRIDGE_SERVER or _TUNNEL_SERVER:
            print("[MCP Bridge] ✓ MCP subprocess can now communicate with server.py")
        else:
            print("[MCP Bridge] ✗ All bridge methods failed!")
            
        return port


async def ensure_mcp_bridge_async() -> int:
    """
    Async version of ensure_mcp_bridge.
    
    Use this if you're already in an async context.
    """
    global _TUNNEL_SERVER, _TUNNEL_STARTED
    global _BRIDGE_SERVER, _BRIDGE_INTEGRATION, _BRIDGE_STARTED
    
    if _TUNNEL_STARTED and _BRIDGE_STARTED:
        return _TUNNEL_SERVER.port if _TUNNEL_SERVER else 0
    
    with _TUNNEL_LOCK:
        if _TUNNEL_STARTED and _BRIDGE_STARTED:
            return _TUNNEL_SERVER.port if _TUNNEL_SERVER else 0
        
        # Get the shared postal hub
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal_hub = get_shared_postal_hub()
        except Exception as e:
            print(f"[MCP Bridge] ✗ Could not get postal hub: {e}")
            return 0
        
        # ==== START NEW MULTI-CHANNEL BRIDGE (PRIMARY) ====
        if not _BRIDGE_STARTED:
            _BRIDGE_STARTED = True
            try:
                from fairies.P00_Autonomic.postal_bridge import (
                    get_bridge_server,
                    PostalHubBridgeIntegration
                )
                
                _BRIDGE_SERVER = get_bridge_server(postal_hub)
                await _BRIDGE_SERVER.start()
                
                # Install integration hooks
                _BRIDGE_INTEGRATION = PostalHubBridgeIntegration(postal_hub)
                _BRIDGE_INTEGRATION.install()
                
                print("[MCP Bridge] ✓ Multi-channel bridge started (SQLite + Shared Memory)")
                
            except Exception as e:
                print(f"[MCP Bridge] ✗ Multi-channel bridge failed: {e}")
        
        # ==== START LEGACY SOCKET TUNNEL (FALLBACK) ====
        if not _TUNNEL_STARTED:
            _TUNNEL_STARTED = True
            try:
                from fairies.P40_Sensory.mcp.postal_tunnel import PostalTunnelServer
                _TUNNEL_SERVER = PostalTunnelServer(postal_hub)
                port = _TUNNEL_SERVER.start()
                
                atexit.register(shutdown_mcp_bridge)
                
                print(f"[MCP Bridge] ✓ Socket tunnel server started on port {port}")
                
            except Exception as e:
                print(f"[MCP Bridge] ✗ Socket tunnel failed: {e}")
                port = 0
        else:
            port = _TUNNEL_SERVER.port if _TUNNEL_SERVER else 0
            
        return port


def shutdown_mcp_bridge():
    """Shutdown the MCP bridge (called at exit)."""
    global _TUNNEL_SERVER, _BRIDGE_SERVER, _BRIDGE_INTEGRATION
    global _BRIDGE_LOOP, _BRIDGE_THREAD

    # Shutdown multi-channel bridge
    if _BRIDGE_SERVER and _BRIDGE_LOOP:
        try:
            # Schedule stop() in the bridge loop
            future = asyncio.run_coroutine_threadsafe(
                _BRIDGE_SERVER.stop(),
                _BRIDGE_LOOP
            )
            # Wait for stop to complete (with timeout)
            try:
                future.result(timeout=2.0)
            except Exception:
                pass

            # Stop the event loop
            _BRIDGE_LOOP.call_soon_threadsafe(_BRIDGE_LOOP.stop)

            # Wait for thread to finish
            if _BRIDGE_THREAD and _BRIDGE_THREAD.is_alive():
                _BRIDGE_THREAD.join(timeout=1.0)

            print("[MCP Bridge] Multi-channel bridge stopped")
        except Exception:
            pass
        _BRIDGE_SERVER = None
        _BRIDGE_LOOP = None
        _BRIDGE_THREAD = None
    
    # Remove integration hooks
    if _BRIDGE_INTEGRATION:
        try:
            _BRIDGE_INTEGRATION.uninstall()
        except Exception:
            pass
        _BRIDGE_INTEGRATION = None
    
    # Shutdown socket tunnel
    if _TUNNEL_SERVER:
        try:
            _TUNNEL_SERVER.stop()
            print("[MCP Bridge] Socket tunnel server stopped")
        except Exception:
            pass
        _TUNNEL_SERVER = None


def get_tunnel_port() -> int:
    """Get the socket tunnel server port (0 if not running)."""
    global _TUNNEL_SERVER
    return _TUNNEL_SERVER.port if _TUNNEL_SERVER else 0


def is_bridge_active() -> bool:
    """Check if any bridge method is active."""
    global _TUNNEL_SERVER, _TUNNEL_STARTED
    global _BRIDGE_SERVER, _BRIDGE_STARTED
    return (_TUNNEL_STARTED and _TUNNEL_SERVER is not None) or \
           (_BRIDGE_STARTED and _BRIDGE_SERVER is not None)


def is_multi_channel_active() -> bool:
    """Check if the new multi-channel bridge is active."""
    global _BRIDGE_SERVER, _BRIDGE_STARTED
    return _BRIDGE_STARTED and _BRIDGE_SERVER is not None


def is_socket_tunnel_active() -> bool:
    """Check if the legacy socket tunnel is active."""
    global _TUNNEL_SERVER, _TUNNEL_STARTED
    return _TUNNEL_STARTED and _TUNNEL_SERVER is not None


def get_bridge_status() -> dict:
    """Get detailed bridge status."""
    return {
        "multi_channel_active": is_multi_channel_active(),
        "socket_tunnel_active": is_socket_tunnel_active(),
        "socket_port": get_tunnel_port(),
        "any_active": is_bridge_active(),
    }


__all__ = [
    'ensure_mcp_bridge',
    'ensure_mcp_bridge_async',
    'shutdown_mcp_bridge',
    'get_tunnel_port',
    'is_bridge_active',
    'is_multi_channel_active',
    'is_socket_tunnel_active',
    'get_bridge_status',
]
