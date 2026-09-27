"""
gui_cortex.py - HEADLESS MODE STUB
===================================
Qt GUI Cortex has been replaced by web dashboard.

All functionality now available at:
- localhost:8080 (web dashboard)
- Use start_dashboard.bat to launch
"""

from . import GUI_Cortex, get_cortex, _deprecated_warning

__all__ = ['GUI_Cortex', 'get_cortex']

def boot():
    """Boot stub - no-op in headless mode."""
    _deprecated_warning("gui_cortex.boot")
    print("[gui_cortex] Headless mode - use web dashboard")

def run():
    """Run stub - no-op in headless mode."""
    _deprecated_warning("gui_cortex.run")
    print("[gui_cortex] Headless mode - use web dashboard")

def main():
    """Main stub - no-op in headless mode."""
    _deprecated_warning("gui_cortex.main")
    print("[gui_cortex] Headless mode - use web dashboard")
