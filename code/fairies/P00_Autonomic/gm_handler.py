"""
GM Command Handler - Responds to GM commands from MCP tunnel

Subscribes to gm.* topics and executes GM functions,
writing results to state/gm/ for MCP to read.

Also watches for reload signals from duplicate boot attempts.
"""

import json
import time
import threading
from pathlib import Path

STATE_DIR = Path(__file__).parent.parent / "state" / "gm"
STATE_DIR.mkdir(parents=True, exist_ok=True)

RELOAD_SIGNAL_FILE = Path(__file__).parent.parent / "state" / "reload_signal.json"

# ============================================================================
# RELOAD SIGNAL WATCHER - Responds to duplicate boot attempts
# ============================================================================

_reload_watcher_running = False

def start_reload_watcher():
    """Watch for reload_signal.json and trigger fairy reloads when detected."""
    global _reload_watcher_running
    if _reload_watcher_running:
        return
    _reload_watcher_running = True

    def watch_loop():
        last_mtime = 0
        while _reload_watcher_running:
            try:
                if RELOAD_SIGNAL_FILE.exists():
                    mtime = RELOAD_SIGNAL_FILE.stat().st_mtime
                    if mtime > last_mtime:
                        last_mtime = mtime
                        signal = json.loads(RELOAD_SIGNAL_FILE.read_text())
                        if signal.get("action") == "reload_all":
                            print(f"[GM-Handler] Reload signal detected from: {signal.get('source')}")
                            _trigger_full_reload()
                            # Clear the signal file
                            RELOAD_SIGNAL_FILE.unlink()
            except Exception as e:
                pass  # Silently ignore errors
            time.sleep(2)  # Check every 2 seconds

    thread = threading.Thread(target=watch_loop, daemon=True, name="ReloadWatcher")
    thread.start()
    print("[GM-Handler] Reload signal watcher started")

def _trigger_full_reload():
    """Reload all fairies in response to a reload signal."""
    print("[GM-Handler] Triggering full fairy reload...")
    try:
        from fairies.P00_Autonomic.fairy_refresh import refresh_fairy, FAIRY_REGISTRY
        reloaded = []
        failed = []
        for fairy_name in FAIRY_REGISTRY.keys():
            try:
                result = refresh_fairy(fairy_name, run_on_boot=True)
                if result.get("success"):
                    reloaded.append(fairy_name)
                else:
                    failed.append(fairy_name)
            except Exception as e:
                failed.append(f"{fairy_name}: {e}")
        print(f"[GM-Handler] Reload complete: {len(reloaded)} success, {len(failed)} failed")
        if failed:
            print(f"[GM-Handler] Failed: {failed}")
    except Exception as e:
        print(f"[GM-Handler] Full reload failed: {e}")

def register_gm_handler(post):
    """Register GM command handlers with postal system."""
    
    def on_gm_world_status(packet):
        """Handle gm.world_status request."""
        try:
            from fairies.P00_Autonomic.gm_tools import gm_world_status
            status = gm_world_status()
            print(f"[GM-Handler] World status written ({status.get('registry', {}).get('fairy_count', 0)} fairies)")
        except Exception as e:
            print(f"[GM-Handler] World status failed: {e}")
    
    def on_gm_inject_tracer(packet):
        """Handle gm.inject_tracer request."""
        try:
            from fairies.P00_Autonomic.gm_tools import gm_inject_tracer
            tracer_id = packet.get("tracer_id") if isinstance(packet, dict) else None
            tid = gm_inject_tracer(tracer_id)
            print(f"[GM-Handler] Tracer injected: {tid}")
        except Exception as e:
            print(f"[GM-Handler] Tracer injection failed: {e}")
    
    def on_gm_list_fairies(packet):
        """Handle gm.list_fairies request."""
        try:
            from fairies.P00_Autonomic.gm_tools import gm_list_fairies
            result = gm_list_fairies()
            # Write to file for MCP
            output = STATE_DIR / "fairy_list.json"
            output.write_text(json.dumps(result, indent=2))
            print(f"[GM-Handler] Fairy list written ({result.get('count', 0)} fairies)")
        except Exception as e:
            print(f"[GM-Handler] List fairies failed: {e}")

    def on_system_fairy_reload(packet):
        """
        Handle system.fairy_reload request - hot-reload a fairy module IN THIS PROCESS.

        This is THE FIX for MCP/server.py process separation.
        When MCP sends this message, server.py reloads the module directly.
        """
        fairy_name = packet.get("fairy_name") if isinstance(packet, dict) else None
        if not fairy_name:
            print("[GM-Handler] Fairy reload: no fairy_name provided")
            return

        try:
            from fairies.P00_Autonomic.fairy_refresh import refresh_fairy
            result = refresh_fairy(fairy_name, run_on_boot=True)
            output = STATE_DIR / "fairy_reload_result.json"
            output.write_text(json.dumps({
                "fairy": fairy_name,
                "success": result.get("success", False),
                "steps": result.get("steps", []),
                "timestamp": time.time()
            }, indent=2))
            print(f"[GM-Handler] Fairy {fairy_name} reloaded: {result.get('success', False)}")
        except Exception as e:
            import traceback
            output = STATE_DIR / "fairy_reload_result.json"
            output.write_text(json.dumps({
                "fairy": fairy_name,
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": time.time()
            }, indent=2))
            print(f"[GM-Handler] Fairy reload failed: {e}")

    # Subscribe to GM topics
    post.subscribe("gm.world_status", on_gm_world_status)
    post.subscribe("gm.inject_tracer", on_gm_inject_tracer)
    post.subscribe("gm.list_fairies", on_gm_list_fairies)

    # Subscribe to system-level commands
    post.subscribe("system.fairy_reload", on_system_fairy_reload)
    print("[GM-Handler] Registered for system.fairy_reload")
    
    print("[GM-Handler] Registered for gm.* commands")

def setup_gm_handler():
    """Setup GM handler with shared postal hub."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        register_gm_handler(post)
        # Start the reload watcher for duplicate boot detection
        start_reload_watcher()
        return True
    except Exception as e:
        print(f"[GM-Handler] Setup failed: {e}")
        return False
