# Mind Scheduler Infrastructure Module
# 
# Provides _get_mind_scheduler() for the Organ Template
# This gets injected into all fairies as infrastructure
#
# Pattern matches: _get_consciousness_loop(), _get_shared_postal_hub()

from __future__ import annotations

import threading
from typing import Optional, Dict, Any

# ============================================================================
# MIND SCHEDULER INFRASTRUCTURE - Multi-Mind Coordination
# ============================================================================
# MindScheduler is infrastructure - it coordinates all minds (ClaudeFairy,
# SourpatchesFairy, etc.) to prevent API overload and enable per-mind
# drift detection.
#
# Boot order:
#   1. ConsciousnessLoop starts (provides stream substrate)
#   2. Directory/PostalHub boots (routing)  
#   3. MindScheduler boots (mind coordination)
#   4. Fairies boot and register with scheduler
# ============================================================================

_SHARED_MIND_SCHEDULER = None
_MIND_SCHEDULER_LOCK = threading.Lock()
_MINDS_INITIALIZED = False


def _get_mind_scheduler():
    """
    Get or create the shared MindScheduler singleton.
    This is infrastructure - it coordinates all minds.
    
    All fairies should use this same scheduler for drift detection
    and API access coordination.
    """
    global _SHARED_MIND_SCHEDULER, _MINDS_INITIALIZED
    
    if _SHARED_MIND_SCHEDULER is not None:
        return _SHARED_MIND_SCHEDULER
    
    with _MIND_SCHEDULER_LOCK:
        # Double-check after acquiring lock
        if _SHARED_MIND_SCHEDULER is not None:
            return _SHARED_MIND_SCHEDULER
        
        try:
            # Import the real MindScheduler
            from fairies.P30_Cognition.cognition.mind_scheduler import (
                get_mind_scheduler, 
                setup_akashic_minds
            )
            
            scheduler = get_mind_scheduler()
            
            # Set up the standard minds if not already done
            if not _MINDS_INITIALIZED and not scheduler.minds:
                # Get postal for wiring
                post = None
                try:
                    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                    post = get_shared_postal_hub()
                except Exception as e:
                    print(f"[MIND-SCHEDULER-INFRA] Postal not available: {e}")
                
                # Use the built-in setup function
                setup_akashic_minds(post)
                
                # Start the scheduler
                scheduler.start()
                
                _MINDS_INITIALIZED = True
                print("[MIND-SCHEDULER-INFRA] [OK] MindScheduler initialized and started")
            
            _SHARED_MIND_SCHEDULER = scheduler
            return _SHARED_MIND_SCHEDULER
            
        except ImportError as e:
            print(f"[MIND-SCHEDULER-INFRA] MindScheduler not available: {e}")
            # Create a minimal shim
            _SHARED_MIND_SCHEDULER = _MindSchedulerShim()
            return _SHARED_MIND_SCHEDULER
        except Exception as e:
            import traceback
            print(f"[MIND-SCHEDULER-INFRA] Error: {e}")
            traceback.print_exc()
            _SHARED_MIND_SCHEDULER = _MindSchedulerShim()
            return _SHARED_MIND_SCHEDULER


class _MindSchedulerShim:
    """
    Minimal shim when full MindScheduler isn't available.
    Provides no-op interface so fairies don't crash.
    """
    
    def __init__(self):
        self.minds = {}
        self._running = False
        self.request_queue = None
        self.current_api_user = None
        print("[MIND-SCHEDULER-INFRA] [WARN] Using shim (full scheduler unavailable)")
    
    def get_mind(self, mind_id: str):
        return None
    
    def register_mind(self, mind_id: str, **kwargs):
        return None
    
    def record_activity(self, mind_id: str, activity_type: str, details: Dict = None):
        pass
    
    def request_api(self, mind_id: str, request_type: str, payload: Dict) -> str:
        return ""
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    def get_status(self) -> Dict:
        return {
            "running": False,
            "shim": True,
            "error": "Full scheduler unavailable"
        }


# ============================================================================
# HELPER FUNCTIONS FOR FAIRIES
# ============================================================================

def register_fairy_with_scheduler(actor_name: str, priority: int = 5, 
                                   drift_timeout: float = 30.0):
    """
    Register a fairy as a trackable mind with the scheduler.
    
    Only call this for fairies that are actual "minds" (ClaudeFairy,
    SourpatchesFairy, etc.), not worker fairies.
    """
    try:
        scheduler = _get_mind_scheduler()
        if scheduler and hasattr(scheduler, 'register_mind'):
            return scheduler.register_mind(
                mind_id=actor_name,
                display_name=actor_name,
                priority=priority,
                drift_timeout=drift_timeout
            )
    except Exception as e:
        print(f"[MIND-SCHEDULER-INFRA] Registration failed for {actor_name}: {e}")
    return None


def record_fairy_activity(mind_id: str, activity_type: str, details: Dict = None):
    """
    Record activity for a mind.
    
    Args:
        mind_id: Which mind (e.g., "ClaudeFairy")
        activity_type: "response", "thinking", "tool_result", "user_message"
        details: Additional details
    """
    try:
        scheduler = _get_mind_scheduler()
        if scheduler and hasattr(scheduler, 'record_activity'):
            scheduler.record_activity(mind_id, activity_type, details or {})
    except Exception:
        pass


def get_scheduler_status() -> Dict[str, Any]:
    """Get current scheduler status for monitoring."""
    try:
        scheduler = _get_mind_scheduler()
        if scheduler and hasattr(scheduler, 'get_status'):
            return scheduler.get_status()
    except Exception as e:
        return {"error": str(e)}
    return {"error": "scheduler_unavailable"}


# ============================================================================
# AUTO-INJECTION INTO TEMPLATE
# ============================================================================

def inject_into_template():
    """
    Inject _get_mind_scheduler into the template module.
    Called during import to make it available to all fairies.
    """
    try:
        import sys
        
        # Find the template module
        template_module = None
        for name, mod in sys.modules.items():
            if 'akashic_template' in name or 'Organ_Template' in name:
                template_module = mod
                break
        
        if template_module:
            if not hasattr(template_module, '_get_mind_scheduler'):
                template_module._get_mind_scheduler = _get_mind_scheduler
                print("[MIND-SCHEDULER-INFRA]  Injected into template module")
    except Exception as e:
        print(f"[MIND-SCHEDULER-INFRA] Template injection skipped: {e}")


# Auto-inject on import
inject_into_template()
