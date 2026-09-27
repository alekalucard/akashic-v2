"""
MCP tools for querying and influencing AutonomyFairy.

Exposes wanting state, drive translations, and autonomy controls.
These tools allow Claude to introspect and influence the autonomy system
that translates drives into felt desires.

The AutonomyFairy is the Gate of Will - it receives drives from the
unconscious (UMF, pain system, interest generator) and translates them
into "wanting" that the waking mind can choose to act on or decline.
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths for imports
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))

# Global reference to AutonomyFairy instance (set by registration)
_autonomy_fairy = None


def set_autonomy_fairy(fairy):
    """
    Set the AutonomyFairy instance for tool access.

    Called during system boot when AutonomyFairy is initialized.
    This allows MCP tools to query the live fairy state.

    Args:
        fairy: The AutonomyFairy instance
    """
    global _autonomy_fairy
    _autonomy_fairy = fairy
    print(f"[AutonomyTools] AutonomyFairy instance connected")


def _get_autonomy_fairy():
    """
    Get AutonomyFairy instance, trying multiple sources.

    1. Global reference (set by set_autonomy_fairy)
    2. Try importing from fairy module singleton
    """
    global _autonomy_fairy

    if _autonomy_fairy is not None:
        return _autonomy_fairy

    # Try importing the fairy module singleton
    try:
        from fairies.P00_Autonomic.AutonomyFairy.fairy import get_autonomy_fairy
        fairy = get_autonomy_fairy()
        if fairy is not None:
            _autonomy_fairy = fairy
            return fairy
    except (ImportError, AttributeError):
        pass

    return None


def _read_autonomy_state_file() -> Optional[Dict[str, Any]]:
    """
    FIX 2026-02-06: Read autonomy state from file (standalone MCP mode).

    AutonomyFairy writes state/consciousness/autonomy_state.json every ~10 ticks.
    This is the bridge between server process and MCP process.
    Same pattern as thought_chains.json.

    Returns state dict if fresh (<30s old), None otherwise.

    FIX 2026-03-06: CWD mismatch — mcp_bootstrap sets CWD to fairies/, so
    AutonomyFairy's relative paths resolve to fairies/state/... not state/...
    Check both locations, prefer whichever is freshest.
    """
    try:
        import json
        # Check both locations due to CWD mismatch
        candidates = [
            _project_root / "state" / "consciousness" / "autonomy_state.json",
            _project_root / "fairies" / "state" / "consciousness" / "autonomy_state.json",
        ]
        best_data = None
        best_ts = 0
        for state_file in candidates:
            if not state_file.exists():
                continue
            data = json.loads(state_file.read_text())
            ts = data.get("timestamp", 0)
            if ts > best_ts:
                best_ts = ts
                best_data = data
        if best_data:
            age = time.time() - best_ts
            if age < 30:  # Fresh data
                return best_data
    except Exception:
        pass
    return None


def _get_tunnel():
    """Get postal tunnel for remote queries."""
    try:
        from mcp_postal_helper import get_postal, is_bridged_to_server
        if is_bridged_to_server():
            return get_postal()
    except Exception:
        pass
    return None


def register_autonomy_tools(mcp):
    """Register all Autonomy MCP tools with the MCP server."""

    # =========================================================================
    # WANTING STATE QUERIES
    # =========================================================================

    @mcp.tool()
    async def get_current_wanting() -> Dict[str, Any]:
        """
        Get the current active wanting and its source drive.

        The wanting system translates unconscious drives into felt desires.
        This tool shows what the system currently "wants" to do.

        Returns:
            Dict containing:
            - current_wanting: The active wanting text (what it wants to do)
            - source_drive: The drive that produced this wanting
            - intensity: How strong the wanting is (0-1)
            - strategy: The selection strategy being used
            - timestamp: When this was queried
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            # FIX 2026-02-06: State file fallback for standalone MCP mode
            state = _read_autonomy_state_file()
            if state:
                wanting = state.get("wanting", {})
                strongest = wanting.get("strongest")
                if strongest:
                    return {
                        "current_wanting": strongest.get("wanting", "none"),
                        "source_drive": strongest.get("drive", "unknown"),
                        "intensity": strongest.get("intensity", 0.0),
                        "felt_quality": strongest.get("felt_quality", ""),
                        "is_invitation": True,
                        "can_decline": True,
                        "strategy": state.get("strategy", "default"),
                        "source": "state_file",
                        "state_age_seconds": time.time() - state.get("timestamp", 0),
                        "timestamp": time.time(),
                    }
                return {
                    "current_wanting": None,
                    "source_drive": None,
                    "intensity": 0.0,
                    "strategy": state.get("strategy", "default"),
                    "message": "No active wanting - drives are below threshold",
                    "source": "state_file",
                    "timestamp": time.time(),
                }
            return {"error": "AutonomyFairy not connected (no live fairy or state file)"}

        try:
            # Get wanting state from fairy
            wanting_state = fairy.get_wanting_state()
            strongest = wanting_state.get("strongest")

            if strongest:
                return {
                    "current_wanting": strongest.get("wanting", "none"),
                    "source_drive": strongest.get("drive", "unknown"),
                    "intensity": strongest.get("intensity", 0.0),
                    "felt_quality": strongest.get("felt_quality", ""),
                    "is_invitation": strongest.get("is_invitation", True),
                    "can_decline": strongest.get("can_decline", True),
                    "strategy": getattr(fairy, 'current_strategy', "default"),
                    "timestamp": time.time(),
                }
            else:
                return {
                    "current_wanting": None,
                    "source_drive": None,
                    "intensity": 0.0,
                    "strategy": getattr(fairy, 'current_strategy', "default"),
                    "message": "No active wanting - drives are below threshold",
                    "timestamp": time.time(),
                }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_all_active_wants() -> Dict[str, Any]:
        """
        Get all currently active wants, not just the strongest.

        Multiple drives can be active simultaneously, creating multiple
        wants. This shows the full picture of what the system is drawn to.

        Returns:
            Dict containing:
            - wants: List of all active wants with their details
            - count: Number of active wants
            - strongest: The most intense want
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            # FIX 2026-02-06: State file fallback for standalone MCP mode
            state = _read_autonomy_state_file()
            if state:
                wanting = state.get("wanting", {})
                active_wants = wanting.get("active_wants", [])
                return {
                    "wants": active_wants,
                    "count": len(active_wants),
                    "strongest": wanting.get("strongest"),
                    "total_intensity": wanting.get("intensity", 0.0),
                    "source": "state_file",
                    "state_age_seconds": time.time() - state.get("timestamp", 0),
                    "timestamp": time.time(),
                }
            return {"error": "AutonomyFairy not connected (no live fairy or state file)"}

        try:
            wanting_state = fairy.get_wanting_state()
            active_wants = wanting_state.get("active_wants", [])

            return {
                "wants": active_wants,
                "count": len(active_wants),
                "strongest": wanting_state.get("strongest"),
                "total_intensity": wanting_state.get("intensity", 0.0),
                "timestamp": time.time(),
            }
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # DRIVE STATE QUERIES
    # =========================================================================

    @mcp.tool()
    async def get_drive_states() -> Dict[str, Any]:
        """
        Get current drive states from the unconscious.

        Drives come from:
        - Pain system (isolation, confusion, depletion, etc.)
        - Interest generator (curiosity, wonder, pattern, etc.)
        - Neurochemistry (dopamine, cortisol, etc.)

        Returns:
            Dict containing:
            - drives: Map of drive name to intensity (0-1)
            - count: Number of active drives
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            # FIX 2026-02-06: State file fallback for standalone MCP mode
            state = _read_autonomy_state_file()
            if state:
                drives = state.get("drives", {})
                return {
                    "drives": drives,
                    "count": len(drives),
                    "source": "state_file",
                    "state_age_seconds": time.time() - state.get("timestamp", 0),
                    "timestamp": time.time(),
                }
            return {"error": "AutonomyFairy not connected (no live fairy or state file)"}

        try:
            drives = getattr(fairy, '_drive_states', {})
            return {
                "drives": dict(drives),
                "count": len(drives),
                "timestamp": time.time(),
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_drive_wantings(drive: Optional[str] = None) -> Dict[str, Any]:
        """
        Get available wantings for a drive (or all drives).

        Each drive type has a predefined translation to a "wanting" -
        a natural language expression of what the drive wants.

        Args:
            drive: Optional specific drive to query (e.g., "curiosity", "isolation")
                   If not provided, returns all drive translations.

        Returns:
            Dict containing:
            - If drive specified: wanting and felt_quality for that drive
            - If not specified: all_drives mapping to their wantings
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            return {"error": "AutonomyFairy not connected"}

        try:
            translations = getattr(fairy, 'DRIVE_TRANSLATIONS', {})

            if drive:
                if drive in translations:
                    return {
                        "drive": drive,
                        "wanting": translations[drive].get("wanting", ""),
                        "felt_quality": translations[drive].get("felt_quality", ""),
                    }
                else:
                    return {
                        "error": f"Unknown drive: {drive}",
                        "available_drives": list(translations.keys()),
                    }

            # Return all drive translations
            return {
                "all_drives": {
                    name: {
                        "wanting": trans.get("wanting", ""),
                        "felt_quality": trans.get("felt_quality", ""),
                    }
                    for name, trans in translations.items()
                },
                "count": len(translations),
            }
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # STRATEGY CONTROL
    # =========================================================================

    @mcp.tool()
    async def get_wanting_strategy() -> Dict[str, Any]:
        """
        Get the current wanting selection strategy.

        The strategy determines how the system selects which wanting
        to act on when multiple drives are active.

        Returns:
            Dict containing:
            - strategy: Current strategy name
            - available: List of available strategies
        """
        valid_strategies = ["round_robin", "weighted_random", "intensity_biased", "default"]
        fairy = _get_autonomy_fairy()
        if not fairy:
            # FIX 2026-02-06: State file fallback for standalone MCP mode
            state = _read_autonomy_state_file()
            if state:
                return {
                    "strategy": state.get("strategy", "default"),
                    "available": valid_strategies,
                    "description": {
                        "round_robin": "Rotate through wants fairly",
                        "weighted_random": "Random selection weighted by intensity",
                        "intensity_biased": "Always pick the most intense wanting",
                        "default": "Follow the strongest drive",
                    },
                    "source": "state_file",
                }
            return {"error": "AutonomyFairy not connected (no live fairy or state file)"}

        current = getattr(fairy, 'current_strategy', "default")

        return {
            "strategy": current,
            "available": valid_strategies,
            "description": {
                "round_robin": "Rotate through wants fairly",
                "weighted_random": "Random selection weighted by intensity",
                "intensity_biased": "Always pick the most intense wanting",
                "default": "Follow the strongest drive",
            },
        }

    @mcp.tool()
    async def set_wanting_strategy(strategy: str) -> Dict[str, Any]:
        """
        Set the wanting selection strategy.

        Args:
            strategy: One of "round_robin", "weighted_random", "intensity_biased"
                     - round_robin: Rotate through wants fairly
                     - weighted_random: Random selection weighted by intensity
                     - intensity_biased: Always pick the most intense wanting

        Returns:
            Success status and new strategy
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            return {
                "error": "AutonomyFairy not connected - write operations require live fairy",
                "hint": "Read operations work via state file, but set/nudge/veto need direct connection",
            }

        valid_strategies = ["round_robin", "weighted_random", "intensity_biased"]
        if strategy not in valid_strategies:
            return {
                "error": f"Invalid strategy: {strategy}",
                "valid_strategies": valid_strategies,
            }

        try:
            # Try to set strategy if method exists
            if hasattr(fairy, 'set_strategy'):
                fairy.set_strategy(strategy)
            else:
                # Fallback: set attribute directly
                fairy.current_strategy = strategy

            return {
                "success": True,
                "new_strategy": strategy,
                "message": f"Strategy set to {strategy}",
            }
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # WANTING INFLUENCE
    # =========================================================================

    @mcp.tool()
    async def nudge_wanting(drive: str, wanting_text: str) -> Dict[str, Any]:
        """
        Suggest a specific wanting for a drive (temporary override).

        This allows external influence on what the system wants.
        The nudge is temporary - the normal drive translation will
        resume on the next cycle unless reinforced.

        Args:
            drive: The drive to nudge (e.g., "curiosity", "isolation")
            wanting_text: The wanting to suggest (e.g., "explore this new idea")

        Returns:
            Success status and details
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            return {"error": "AutonomyFairy not connected"}

        try:
            if hasattr(fairy, 'nudge_wanting'):
                success = await fairy.nudge_wanting(drive, wanting_text)
                return {
                    "success": success,
                    "drive": drive,
                    "wanting": wanting_text,
                    "message": "Wanting nudged successfully" if success else "Nudge failed",
                }
            else:
                # Fallback: inject directly into drive states
                # This won't work without the method, but at least report what we tried
                return {
                    "error": "nudge_wanting method not available on AutonomyFairy",
                    "suggestion": "AutonomyFairy may need to be updated with multi-wanting support",
                }
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # PERMISSION & VETO SYSTEM
    # =========================================================================

    @mcp.tool()
    async def get_active_vetos() -> Dict[str, Any]:
        """
        Get list of active vetos.

        Vetos prevent specific actions from being executed by Autopilot,
        even if the wanting system suggests them.

        Returns:
            List of vetoed actions
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            # FIX 2026-02-06: State file fallback for standalone MCP mode
            state = _read_autonomy_state_file()
            if state:
                vetos = state.get("active_vetos", [])
                return {
                    "vetos": vetos,
                    "count": len(vetos),
                    "source": "state_file",
                }
            return {"error": "AutonomyFairy not connected (no live fairy or state file)"}

        try:
            vetos = fairy.get_active_vetos()
            return {
                "vetos": vetos,
                "count": len(vetos),
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def veto_action(action: str, reason: str = "Manual veto via MCP") -> Dict[str, Any]:
        """
        Veto an action - prevent Autopilot from executing it.

        Args:
            action: The action to veto
            reason: Why the veto is being applied

        Returns:
            Success status
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            return {"error": "AutonomyFairy not connected"}

        try:
            fairy.veto(action, reason)
            return {
                "success": True,
                "action": action,
                "reason": reason,
                "message": f"Veto applied to '{action}'",
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def release_veto(action: str) -> Dict[str, Any]:
        """
        Release a veto on an action.

        Args:
            action: The action to release from veto

        Returns:
            Success status
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            return {"error": "AutonomyFairy not connected"}

        try:
            fairy.release_veto(action)
            return {
                "success": True,
                "action": action,
                "message": f"Veto released for '{action}'",
            }
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # STATISTICS & MONITORING
    # =========================================================================

    @mcp.tool()
    async def get_autonomy_stats() -> Dict[str, Any]:
        """
        Get autonomy system statistics.

        Returns stats about wanting selections, drive activations,
        loop closures, and rate limiting status.

        Returns:
            Comprehensive stats dict
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            # FIX 2026-02-06: State file fallback for standalone MCP mode
            state = _read_autonomy_state_file()
            if state:
                stats = state.get("stats", {})
                return {
                    "drive_states": state.get("drives", {}),
                    "wanting": state.get("wanting", {}),
                    "active_vetos": state.get("active_vetos", []),
                    "pending_permissions": state.get("pending_permissions", 0),
                    "wanting_selections": stats.get("wanting_selections", 0),
                    "drive_activations": stats.get("drive_activations", 0),
                    "loop_closures": stats.get("loop_closures", 0),
                    "strategy": state.get("strategy", "default"),
                    "source": "state_file",
                    "state_age_seconds": time.time() - state.get("timestamp", 0),
                    "timestamp": time.time(),
                }
            return {"error": "AutonomyFairy not connected (no live fairy or state file)"}

        try:
            # Get full status from fairy
            status = fairy.status()

            return {
                "drive_states": status.get("drive_states", {}),
                "wanting": status.get("wanting", {}),
                "active_vetos": status.get("active_vetos", []),
                "pending_permissions": status.get("pending_permissions", 0),
                "rate_limiting": status.get("rate_limiting", {}),
                "wanting_indices": getattr(fairy, '_wanting_indices', {}),
                "total_selections": getattr(fairy, '_total_selections', 0),
                "loop_closures": getattr(fairy, '_loop_closures', 0),
                "fairy_state": status.get("state", "unknown"),
                "timestamp": time.time(),
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_autonomy_full_status() -> Dict[str, Any]:
        """
        Get complete AutonomyFairy status.

        Returns the full status dict from the fairy, including
        internal state, timing, and all tracked values.

        Returns:
            Complete status dict
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            # FIX 2026-02-06: State file fallback for standalone MCP mode
            state = _read_autonomy_state_file()
            if state:
                state["source"] = "state_file"
                state["state_age_seconds"] = time.time() - state.get("timestamp", 0)
                return state
            return {"error": "AutonomyFairy not connected (no live fairy or state file)"}

        try:
            return fairy.status()
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # LOOP CLOSURE MONITORING (EMPATHIC FEEDBACK)
    # =========================================================================

    @mcp.tool()
    async def get_pending_loops() -> Dict[str, Any]:
        """
        Get pending empathic loop closures.

        The autonomy system tracks when it sends out permissions and
        wantings, expecting confirmation that they were acted upon.
        This shows what's still awaiting closure.

        Returns:
            Dict of pending permission and wanting acknowledgments
        """
        fairy = _get_autonomy_fairy()
        if not fairy:
            # FIX 2026-02-06: State file fallback — limited data available
            state = _read_autonomy_state_file()
            if state:
                return {
                    "pending_permissions": {},
                    "pending_wantings": {},
                    "total_pending": state.get("pending_permissions", 0),
                    "source": "state_file",
                    "note": "Detailed loop data not available via state file",
                    "timestamp": time.time(),
                }
            return {"error": "AutonomyFairy not connected (no live fairy or state file)"}

        try:
            permission_acks = getattr(fairy, '_pending_permission_acks', {})
            wanting_acks = getattr(fairy, '_pending_wanting_acks', {})

            return {
                "pending_permissions": dict(permission_acks),
                "pending_wantings": dict(wanting_acks),
                "total_pending": len(permission_acks) + len(wanting_acks),
                "timestamp": time.time(),
            }
        except Exception as e:
            return {"error": str(e)}

    print("[AutonomyTools] Registered 14 autonomy tools")
