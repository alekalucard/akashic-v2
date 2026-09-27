# Mind Scheduler Monitoring API
#
# Provides status endpoints and postal emissions for GUI monitoring
# Subscribe to "mind.status" for real-time updates
#
# Usage:
#   from fairies.P30_Cognition.cognition.mind_scheduler_monitor import get_minds_status, subscribe_monitor

from __future__ import annotations

import threading
import time
from typing import Dict, Any, List, Optional, Callable

# ============================================================================
# STATUS SNAPSHOT - For GUI Polling
# ============================================================================

def get_minds_status() -> Dict[str, Any]:
    """
    Get a snapshot of all minds' status for GUI display.
    
    Returns dict with:
        - minds: {mind_id: {status, last_activity, drift_state, ...}}
        - scheduler: {running, queue_size, current_api_user}
        - summary: {total_minds, active_count, drifting_count}
        - ts: timestamp
    """
    try:
        from fairies.P30_Cognition.cognition.mind_scheduler import get_mind_scheduler, MindState
        scheduler = get_mind_scheduler()
        
        if not scheduler:
            return {"error": "scheduler_not_initialized", "ts": time.time()}
        
        minds_data = {}
        active_count = 0
        drifting_count = 0
        
        for mind_id, agent in scheduler.minds.items():
            now = time.time()
            # Use correct attribute: last_activity_ts
            last_activity = agent.last_activity_ts
            idle_sec = now - last_activity if last_activity > 0 else 0
            
            # Check state enum for drift
            is_drifting = agent.state == MindState.DRIFTING
            
            # Determine state
            if is_drifting:
                state = "drifting"
                drifting_count += 1
            elif idle_sec < 30:
                state = "active"
                active_count += 1
            elif idle_sec < 120:
                state = "idle"
            else:
                state = "dormant"
            
            # Get last activity type from buffer
            last_activity_type = "none"
            if agent.activity_buffer:
                last_event = agent.activity_buffer[-1]
                last_activity_type = last_event.get("type", "unknown")
            
            # Get recent activities from buffer
            recent_activities = []
            for event in list(agent.activity_buffer)[-5:]:
                recent_activities.append({
                    "type": event.get("type", "unknown"),
                    "ts": event.get("timestamp", 0),
                    "age_sec": round(now - event.get("timestamp", now), 1)
                })
            
            minds_data[mind_id] = {
                "display_name": agent.display_name,
                "state": state,
                "priority": agent.priority,
                "last_activity_type": last_activity_type,
                "last_activity_time": last_activity,
                "idle_seconds": round(idle_sec, 1),
                "drift_detected": is_drifting,
                "drift_timeout": agent.drift_timeout,
                "activity_count": len(agent.activity_buffer),
                "pending_followups": len(agent.pending_followups),
                "stats": {
                    "api_calls": agent.total_api_calls,
                    "drifts": agent.total_drifts_detected,
                    "nudges": agent.total_nudges_received,
                },
                "recent_activities": recent_activities
            }
        
        # Scheduler status
        return {
            "minds": minds_data,
            "scheduler": {
                "running": scheduler._running,
                "queue_size": scheduler.request_queue.qsize(),
                "current_api_user": scheduler.current_api_user,
                "drift_check_interval": scheduler.drift_check_interval,
                "total_requests": scheduler.total_requests_processed,
            },
            "summary": {
                "total_minds": len(minds_data),
                "active_count": active_count,
                "drifting_count": drifting_count,
                "idle_count": len(minds_data) - active_count - drifting_count,
            },
            "ts": time.time(),
        }
        
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc(), "ts": time.time()}


def get_mind_detail(mind_id: str) -> Dict[str, Any]:
    """
    Get detailed info for a specific mind.
    
    Returns full activity log and drift history.
    """
    try:
        from fairies.P30_Cognition.cognition.mind_scheduler import get_mind_scheduler, MindState
        scheduler = get_mind_scheduler()
        
        if not scheduler:
            return {"error": "scheduler_not_initialized"}
        
        agent = scheduler.minds.get(mind_id)
        if not agent:
            return {"error": f"mind_not_found: {mind_id}"}
        
        now = time.time()
        
        # Get activity log from buffer
        activity_log = []
        for event in agent.activity_buffer:
            activity_log.append({
                "type": event.get("type", "unknown"),
                "ts": event.get("timestamp", 0),
                "age_sec": round(now - event.get("timestamp", now), 1),
                "details_preview": str(event.get("details", {}))[:100]
            })
        
        return {
            "mind_id": mind_id,
            "display_name": agent.display_name,
            "priority": agent.priority,
            "drift_timeout": agent.drift_timeout,
            "drift_detected": agent.state == MindState.DRIFTING,
            "state": agent.state.value,
            "last_activity_time": agent.last_activity_ts,
            "idle_seconds": round(now - agent.last_activity_ts, 1) if agent.last_activity_ts > 0 else 0,
            "pending_followups": agent.pending_followups,
            "activity_log": activity_log,
            "stats": {
                "api_calls": agent.total_api_calls,
                "drifts": agent.total_drifts_detected,
                "nudges": agent.total_nudges_received,
            },
            "ts": now,
        }
        
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# REAL-TIME MONITORING - Postal Emissions
# ============================================================================

_MONITOR_THREAD = None
_MONITOR_STOP = threading.Event()
_MONITOR_INTERVAL = 5.0  # seconds


def start_monitor_emissions(interval: float = 5.0):
    """
    Start emitting mind.status updates to postal every `interval` seconds.
    
    Subscribe to "mind.status" to receive updates.
    """
    global _MONITOR_THREAD, _MONITOR_INTERVAL
    
    if _MONITOR_THREAD and _MONITOR_THREAD.is_alive():
        return {"ok": True, "status": "already_running"}
    
    _MONITOR_INTERVAL = interval
    _MONITOR_STOP.clear()
    
    def _emit_loop():
        post = None
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
        except:
            pass
        
        while not _MONITOR_STOP.is_set():
            try:
                status = get_minds_status()
                
                if post:
                    # Main status update
                    post.route("mind.status", {
                        "opcode": "MINDS_STATUS_UPDATE",
                        "payload": status
                    })
                    
                    # Per-mind drift alerts
                    for mind_id, mind_data in status.get("minds", {}).items():
                        if mind_data.get("drift_detected"):
                            post.route("mind.drift", {
                                "opcode": "DRIFT_ALERT",
                                "payload": {
                                    "mind_id": mind_id,
                                    "display_name": mind_data.get("display_name"),
                                    "idle_seconds": mind_data.get("idle_seconds"),
                                }
                            })
                
            except Exception as e:
                print(f"[MIND-MONITOR] Emission error: {e}")
            
            _MONITOR_STOP.wait(_MONITOR_INTERVAL)
    
    _MONITOR_THREAD = threading.Thread(target=_emit_loop, daemon=True, name="MindMonitor")
    _MONITOR_THREAD.start()
    
    print(f"[MIND-MONITOR] Started emissions every {interval}s")
    return {"ok": True, "interval": interval}


def stop_monitor_emissions():
    """Stop the monitoring emission thread."""
    global _MONITOR_THREAD
    
    _MONITOR_STOP.set()
    if _MONITOR_THREAD:
        _MONITOR_THREAD.join(timeout=2.0)
        _MONITOR_THREAD = None
    
    print("[MIND-MONITOR] Stopped")
    return {"ok": True}


# ============================================================================
# CALLBACK REGISTRATION - For GUI Integration
# ============================================================================

_STATUS_CALLBACKS: List[Callable[[Dict], None]] = []
_DRIFT_CALLBACKS: List[Callable[[str, Dict], None]] = []


def register_status_callback(callback: Callable[[Dict], None]):
    """
    Register a callback to receive status updates.
    
    Callback receives the full status dict from get_minds_status().
    """
    if callback not in _STATUS_CALLBACKS:
        _STATUS_CALLBACKS.append(callback)
    return len(_STATUS_CALLBACKS)


def register_drift_callback(callback: Callable[[str, Dict], None]):
    """
    Register a callback for drift alerts.
    
    Callback receives (mind_id, details_dict).
    """
    if callback not in _DRIFT_CALLBACKS:
        _DRIFT_CALLBACKS.append(callback)
    return len(_DRIFT_CALLBACKS)


def unregister_callback(callback):
    """Remove a callback from either list."""
    if callback in _STATUS_CALLBACKS:
        _STATUS_CALLBACKS.remove(callback)
    if callback in _DRIFT_CALLBACKS:
        _DRIFT_CALLBACKS.remove(callback)


# ============================================================================
# CONVENIENCE: Quick Status Check
# ============================================================================

def minds_summary() -> str:
    """
    Get a human-readable summary of all minds.
    
    Good for console/debug output.
    """
    status = get_minds_status()
    
    if "error" in status:
        return f"❌ Error: {status['error']}"
    
    lines = ["═══ MINDS STATUS ═══"]
    
    for mind_id, data in status.get("minds", {}).items():
        state_emoji = {
            "active": "",
            "idle": "", 
            "drifting": "",
            "dormant": "⚫"
        }.get(data.get("state"), "⚪")
        
        idle = data.get("idle_seconds", 0)
        last_type = data.get("last_activity_type", "none")
        
        lines.append(f"{state_emoji} {data.get('display_name', mind_id)}: {data.get('state')} "
                     f"(idle {idle:.0f}s, last: {last_type})")
    
    summary = status.get("summary", {})
    lines.append(f"───")
    lines.append(f"Total: {summary.get('total_minds', 0)} | "
                 f"Active: {summary.get('active_count', 0)} | "
                 f"Drifting: {summary.get('drifting_count', 0)}")
    
    scheduler = status.get("scheduler", {})
    if scheduler:
        lines.append(f"Scheduler: {' running' if scheduler.get('running') else ' stopped'} | "
                     f"Queue: {scheduler.get('queue_size', 0)} | "
                     f"API: {scheduler.get('current_api_user') or 'idle'}")
    
    return "\n".join(lines)


# ============================================================================
# GUI HELPER: Status Widget Data
# ============================================================================

def get_widget_data() -> Dict[str, Any]:
    """
    Get pre-formatted data for a GUI status widget.
    
    Returns:
        - cards: List of mind cards with color/icon hints
        - alerts: Any active alerts
        - graph_data: Time series for activity visualization
    """
    status = get_minds_status()
    
    if "error" in status:
        return {"error": status["error"]}
    
    cards = []
    alerts = []
    
    for mind_id, data in status.get("minds", {}).items():
        state = data.get("state", "unknown")
        
        # Color hints for GUI
        color = {
            "active": "#4CAF50",    # green
            "idle": "#FFC107",      # amber
            "drifting": "#F44336",  # red
            "dormant": "#9E9E9E"    # gray
        }.get(state, "#757575")
        
        # Icon hints
        icon = {
            "active": "",
            "idle": "",
            "drifting": "⚠",
            "dormant": ""
        }.get(state, "❓")
        
        card = {
            "mind_id": mind_id,
            "title": data.get("display_name", mind_id),
            "subtitle": f"{state.title()} • {data.get('idle_seconds', 0):.0f}s idle",
            "state": state,
            "color": color,
            "icon": icon,
            "last_activity": data.get("last_activity_type", "none"),
            "priority": data.get("priority", 5),
            "stats": data.get("stats", {}),
            "activity_sparkline": [
                a.get("age_sec", 0) for a in data.get("recent_activities", [])
            ]
        }
        cards.append(card)
        
        # Generate alerts
        if data.get("drift_detected"):
            alerts.append({
                "type": "drift",
                "severity": "warning",
                "mind_id": mind_id,
                "message": f"{data.get('display_name')} has drifted ({data.get('idle_seconds', 0):.0f}s idle)",
                "color": "#F44336"
            })
    
    return {
        "cards": cards,
        "alerts": alerts,
        "summary": status.get("summary", {}),
        "scheduler": status.get("scheduler", {}),
        "ts": status.get("ts", time.time())
    }


# ============================================================================
# INITIALIZATION HOOK
# ============================================================================

def init_monitoring(auto_start_emissions: bool = True, interval: float = 5.0):
    """
    Initialize the monitoring system.
    
    Call this during boot to start emissions and set up callbacks.
    """
    if auto_start_emissions:
        start_monitor_emissions(interval)
    
    # Wire into postal for GUI consumption
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        
        # Subscribe to requests for status
        def on_status_request(p):
            status = get_minds_status()
            post.route("mind.status.response", {
                "opcode": "STATUS_RESPONSE",
                "payload": status,
                "request_id": p.get("request_id")
            })
        
        post.subscribe("mind.status.request", on_status_request)
        print("[MIND-MONITOR] [OK] Monitoring initialized")
        
    except Exception as e:
        print(f"[MIND-MONITOR] Partial init: {e}")
    
    return {"ok": True}
