# Patch: Integrate DriftDetector into AutopilotFairy
# 
# This patch wires up the drift detection system to the autopilot,
# enabling automatic momentum injection when Claude drifts.
#
# To apply: Run this file, or import in autopilot_fairy.py

import os
import sys

# Ensure project root is in path
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_this_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def patch_autopilot_with_drift_detection():
    """
    Patch the AutopilotFairy to include drift detection.
    
    This adds:
    1. DriftDetector integration
    2. MomentumInjector wiring
    3. Activity recording from postal events
    4. Auto-start on boot
    """
    try:
        from fairies.P30_Cognition.cognition.autopilot_fairy import (
            AutopilotFairy, get_autopilot_fairy
        )
        from fairies.P30_Cognition.cognition.drift_detector import (
            DriftDetector, MomentumInjector, 
            start_drift_monitoring, record_activity
        )
    except ImportError as e:
        print(f"[DriftPatch] Import failed: {e}")
        return False
    
    # Store original on_boot
    original_on_boot = AutopilotFairy.on_boot
    
    def patched_on_boot(self):
        """Patched on_boot that initializes drift detection."""
        # Call original
        original_on_boot(self)
        
        # Initialize drift detection
        try:
            self._init_drift_detection()
            print(f"[{self.ACTOR_NAME}]  Drift detection initialized")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Drift detection init failed: {e}")
    
    def _init_drift_detection(self):
        """Initialize the drift detection system."""
        # Create detector and injector
        self.drift_injector = MomentumInjector(
            post=getattr(self, 'post', None),
            autopilot=self
        )
        
        self.drift_detector = DriftDetector(
            on_drift_detected=self.drift_injector.inject_momentum
        )
        
        # Start monitoring
        self.drift_detector.start_monitoring(check_interval=5.0)
        
        # Subscribe to postal events for activity tracking
        self._subscribe_to_activity_sources()
        
        # Add continuation behavior
        self._add_continuation_behavior()
    
    def _subscribe_to_activity_sources(self):
        """Subscribe to postal events that indicate activity."""
        if not getattr(self, 'post', None):
            return
        
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            
            # Track tool completions
            postal.subscribe("tool.complete", self._on_tool_activity)
            postal.subscribe("mcp.tool_result", self._on_tool_activity)
            
            # Track code/file activity
            postal.subscribe("file.created", self._on_code_activity)
            postal.subscribe("file.written", self._on_code_activity)
            postal.subscribe("code.executed", self._on_code_activity)
            
            # Track user input
            postal.subscribe("gui.user_message", self._on_user_message)
            postal.subscribe("chat.user_input", self._on_user_message)
            
            # Track responses
            postal.subscribe("claude.response_start", self._on_response_activity)
            postal.subscribe("claudefairy.speak", self._on_response_activity)
            
            print(f"[{self.ACTOR_NAME}]  Subscribed to activity sources for drift detection")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Activity subscription failed: {e}")
    
    def _on_tool_activity(self, packet):
        """Track tool activity."""
        if hasattr(self, 'drift_detector'):
            self.drift_detector.record_activity("tool_result", "claude", packet)
    
    def _on_code_activity(self, packet):
        """Track code/file activity."""
        if hasattr(self, 'drift_detector'):
            self.drift_detector.record_activity("code_write", "claude", packet)
    
    def _on_user_message(self, packet):
        """Track user message receipt."""
        if hasattr(self, 'drift_detector'):
            self.drift_detector.record_activity("user_message_received", "user", packet)
    
    def _on_response_activity(self, packet):
        """Track response activity."""
        if hasattr(self, 'drift_detector'):
            self.drift_detector.record_activity("response_start", "claude", packet)
    
    def _add_continuation_behavior(self):
        """Add a behavior pattern for responding to momentum nudges."""
        from fairies.P30_Cognition.cognition.autopilot_fairy import BehaviorPattern
        
        # Add behavior for momentum nudges
        self.behaviors["respond_to_momentum_nudge"] = BehaviorPattern(
            name="respond_to_momentum_nudge",
            trigger={"event_type": "momentum_nudge"},
            response={
                "action": "trigger_api_continuation",
                "inject_prompt": True,
                "message": "Continue with the task at hand"
            },
            description="Respond to drift detection by continuing work"
        )
        self.behaviors["respond_to_momentum_nudge"].strength = 0.9  # High priority
        
        print(f"[{self.ACTOR_NAME}] [OK] Added momentum nudge behavior")
    
    # Monkey-patch the class
    AutopilotFairy.on_boot = patched_on_boot
    AutopilotFairy._init_drift_detection = _init_drift_detection
    AutopilotFairy._subscribe_to_activity_sources = _subscribe_to_activity_sources
    AutopilotFairy._on_tool_activity = _on_tool_activity
    AutopilotFairy._on_code_activity = _on_code_activity
    AutopilotFairy._on_user_message = _on_user_message
    AutopilotFairy._on_response_activity = _on_response_activity
    AutopilotFairy._add_continuation_behavior = _add_continuation_behavior
    
    print("[DriftPatch] [OK] AutopilotFairy patched with drift detection")
    return True


def apply_patch_to_running_instance():
    """
    Apply drift detection to an already-running autopilot instance.
    """
    try:
        from fairies.P30_Cognition.cognition.autopilot_fairy import get_autopilot_fairy
        from fairies.P30_Cognition.cognition.drift_detector import (
            DriftDetector, MomentumInjector
        )
        
        autopilot = get_autopilot_fairy()
        if not autopilot:
            print("[DriftPatch] No autopilot instance found")
            return False
        
        # Create detector and injector
        autopilot.drift_injector = MomentumInjector(
            post=getattr(autopilot, 'post', None),
            autopilot=autopilot
        )
        
        autopilot.drift_detector = DriftDetector(
            on_drift_detected=autopilot.drift_injector.inject_momentum
        )
        
        # Start monitoring
        autopilot.drift_detector.start_monitoring(check_interval=5.0)
        
        print(f"[DriftPatch] [OK] Drift detection applied to running instance")
        return True
        
    except Exception as e:
        print(f"[DriftPatch] Failed to apply to running instance: {e}")
        return False


if __name__ == "__main__":
    # Apply patch on import or direct run
    patch_autopilot_with_drift_detection()
    
    # Try to apply to running instance too
    apply_patch_to_running_instance()
