# ==============================================================================
# MCP POSTAL HELPER - Get postal connection for MCP subprocess
# ==============================================================================
#
# This module provides a unified way for MCP tools to get postal access.
# It automatically connects to the PostalTunnel if the server is running,
# otherwise falls back to a local isolated hub.
#
# IMPORTANT: MCP runs in a SEPARATE PROCESS from server.py.
# Local singletons DO NOT contain real state - we must use the postal
# tunnel or multi-channel bridge to communicate with the real system.
#
# Usage:
#   from mcp_postal_helper import get_postal, emit_to_server
#
#   # Route a message to the server's postal hub
#   get_postal().route("cognition.input", {"thought": "..."})
#
#   # Or use the helper
#   emit_to_server("consciousness.stream", {...})
#
# ==============================================================================

from __future__ import annotations

import sys
import os
from typing import Optional, Dict, Any

_postal = None
_postal_init_done = False
_is_bridged = False


def _log(msg: str):
    """Safe stderr logging - never raises even if pipe is broken."""
    try:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    except Exception:
        pass  # Pipe broken, swallow silently


def get_postal():
    """
    Get postal connection - bridge/tunnel if available, local hub otherwise.

    IMPORTANT: MCP runs in a SEPARATE PROCESS from server.py.
    This function tries to connect to server.py via:
    1. Multi-channel bridge (SQLite + SharedMemory) - most reliable
    2. Socket tunnel (legacy) - fast but can fail
    3. Local isolated hub (fallback) - no real state, just for compatibility

    Returns:
        PostalBridgeClient or PostalTunnelClient if bridged to server.py,
        else SharedPostalHub (isolated, not ideal)
    """
    global _postal, _postal_init_done, _is_bridged

    if _postal is not None:
        return _postal

    if _postal_init_done:
        return _postal  # May be None if all methods failed

    _postal_init_done = True

    # Check for EMBEDDED MODE first (MCP running inside server.py)
    if os.environ.get("AKASHIC_EMBEDDED_MCP") == "1":
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            _postal = get_shared_postal_hub()
            _is_bridged = True  # Embedded = bridged by definition
            _log("[MCP] [OK] EMBEDDED MODE - Using same postal hub as server.py")
            return _postal
        except Exception as e:
            _log(f"[MCP] Embedded postal hub failed: {e}")

    # PRIORITY 1: Try multi-channel bridge (most reliable)
    try:
        from fairies.P00_Autonomic.postal_bridge import get_bridge_client
        client = get_bridge_client()
        if client.connect():
            _postal = client
            _is_bridged = True
            _log("[MCP] [OK] Connected to server.py via multi-channel bridge")
            return _postal
        else:
            _log("[MCP] Multi-channel bridge connect() returned False")
    except ImportError:
        _log("[MCP] postal_bridge module not found")
    except Exception as e:
        _log(f"[MCP] Multi-channel bridge error: {e}")

    # PRIORITY 2: Try the socket tunnel (connects to server.py / start_nous.bat)
    try:
        from postal_tunnel import get_postal_tunnel_client, get_postal_client, is_tunnel_available

        # Try HTTP client first (port 8081), then socket tunnel (port 49500)
        client = get_postal_client()
        if client and hasattr(client, '_connected') and client._connected:
            _postal = client
            _is_bridged = True
            _log(f"[MCP] [OK] Connected to server via {type(client).__name__}")
            return _postal

        # Fallback: try direct socket tunnel
        if is_tunnel_available():
            client = get_postal_tunnel_client()
            if client and client.ping():
                _postal = client
                _is_bridged = True
                _log("[MCP] [OK] Connected to server via socket tunnel")
                return _postal
            else:
                _log("[MCP] Socket tunnel available but ping failed")
        else:
            _log("[MCP] Socket tunnel not available (port file missing, no HTTP bridge, default port closed)")
    except ImportError:
        _log("[MCP] postal_tunnel module not found")
    except Exception as e:
        _log(f"[MCP] Socket tunnel error: {e}")

    # PRIORITY 3: Fall back to local hub (isolated - NOT IDEAL!)
    # This is only used if server.py is not running
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        _postal = get_shared_postal_hub()
        _is_bridged = False
        _log("[MCP] [WARN] Using ISOLATED local postal hub (NOT connected to server.py)")
        _log("[MCP] [WARN] Body/consciousness queries will return empty data!")
        return _postal
    except Exception as e:
        _log(f"[MCP] Local postal hub failed: {e}")

    return None


def is_bridged_to_server() -> bool:
    """Check if we're connected to the server's postal hub."""
    global _is_bridged
    get_postal()  # Ensure initialized
    return _is_bridged


def reconnect_postal() -> bool:
    """
    Force reconnection to postal tunnel.

    Use this if server.py started after MCP, or if connection was lost.
    Returns True if successfully connected to server.py.
    """
    global _postal, _postal_init_done, _is_bridged

    # Reset cache to force reconnection
    _postal = None
    _postal_init_done = False
    _is_bridged = False

    # Try to connect
    get_postal()
    return _is_bridged


def emit_to_server(topic: str, payload: Dict[str, Any]) -> bool:
    """
    Emit a message to the server's postal hub.

    Returns:
        True if message was routed, False if postal unavailable
    """
    postal = get_postal()
    if postal:
        try:
            result = postal.route(topic, payload)
            return result > 0 if isinstance(result, int) else bool(result)
        except Exception as e:
            _log(f"[MCP] Route error: {e}")
    return False


def get_server_status() -> Dict[str, Any]:
    """
    Get status from the server's postal hub.

    Returns stats if bridged, empty dict if not connected.
    """
    postal = get_postal()
    if postal and hasattr(postal, 'get_stats'):
        try:
            return postal.get_stats()
        except Exception:
            pass
    return {}


def get_server_topics() -> list:
    """
    Get list of active topics in the server.

    Returns topic list if bridged, empty list if not connected.
    """
    postal = get_postal()
    if postal and hasattr(postal, 'list_topics'):
        try:
            return postal.list_topics()
        except Exception:
            pass
    return []


__all__ = [
    'get_postal',
    'is_bridged_to_server',
    'reconnect_postal',
    'emit_to_server',
    'get_server_status',
    'get_server_topics',
    # Backward compatibility aliases
    'is_bridged_to_ebookmain',
    'emit_to_ebookmain',
    'get_ebookmain_status',
    'get_ebookmain_topics',
]


# Backward compatibility aliases
is_bridged_to_ebookmain = is_bridged_to_server
emit_to_ebookmain = emit_to_server
get_ebookmain_status = get_server_status
get_ebookmain_topics = get_server_topics
