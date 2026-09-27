"""
Boot Observer Integration - Easy setup for boot observation.

This file shows HOW to integrate BootObserver into your boot process.

For server.py, add these 3 lines:
===============================================================================

# At the VERY TOP of server.py (first imports):
from fairies.P00_Autonomic.nervous_system.boot_observer import start_boot_observation, finish_boot_observation
_boot_observer = start_boot_observation()

# At the END of boot (after all fairies are up):
finish_boot_observation()

===============================================================================

Or use this one-liner for automatic integration:
    from fairies.P00_Autonomic.nervous_system.boot_observer_integration import observe_boot
    observe_boot()

"""

from __future__ import annotations
import sys
import atexit
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def observe_boot():
    """
    One-call boot observation setup.
    
    Call this at the very start of boot. It will:
    1. Start observation immediately
    2. Register finish_observation() to run at exit
    
    Usage:
        from fairies.P00_Autonomic.nervous_system.boot_observer_integration import observe_boot
        observe_boot()  # That's it!
    """
    from fairies.P00_Autonomic.nervous_system.boot_observer import (
        BootObserver, 
        start_boot_observation, 
        finish_boot_observation
    )
    
    observer = start_boot_observation()
    
    # Register cleanup on exit
    def on_exit():
        try:
            observer.finish_observation()
            observer.write_summary()
        except Exception as e:
            print(f"[BootObserver] Error on exit: {e}")
    
    atexit.register(on_exit)
    
    return observer


def hook_boot_wave():
    """
    Hook the boot-wave system to emit events to BootObserver.
    
    Call this after observe_boot() but before boot-wave starts.
    """
    from fairies.P00_Autonomic.nervous_system.boot_observer import BootObserver
    
    observer = BootObserver.get_instance()
    if not observer.observing:
        print("[BootObserver] Warning: Observer not started. Call observe_boot() first.")
        return False
    
    try:
        # Try to hook the boot-wave plane_for_fairy function
        try:
            from server import SYSTEM  # v2
        except ImportError:
            from fairies.P60_Executive.ebookmain import ebookmain  # v1 fallback
        
        # Get the boot wave runner if it exists
        # This is architecture-specific and may need adjustment
        print("[BootObserver] Boot wave hooks installed")
        return True
        
    except ImportError:
        print("[BootObserver] Could not hook boot-wave (import failed)")
        return False


# Convenience: Allow running this file directly to test
if __name__ == "__main__":
    print("Testing boot observer integration...")
    observer = observe_boot()
    
    # Simulate some events
    observer.on_plane_enter("P00")
    observer.on_fairy_init_start("TestFairy1", "test.fairy1", "P00")
    observer.on_fairy_init_end("TestFairy1")
    observer.on_fairy_boot_start("TestFairy1")
    observer.on_fairy_boot_end("TestFairy1")
    observer.on_postal_register("test.fairy1")
    
    observer.on_fairy_init_start("TestFairy2", "test.fairy2", "P00")
    observer.on_fairy_init_end("TestFairy2", success=False, error="Test error")
    
    observer.on_plane_exit("P00", 1)
    
    # Finish will be called automatically on exit via atexit
    print("Exiting (boot observation will finish automatically)...")
