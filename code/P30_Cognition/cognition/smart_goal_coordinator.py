# Shim: Forwards to canonical location at fairies.P30_Cognition.cognition.smart_goal_coordinator
"""
FIX 2026-02-02: This shim allows 'from P30_Cognition.cognition.smart_goal_coordinator import ...'
to work even though the real file is at fairies/P30_Cognition/cognition/smart_goal_coordinator.py
"""
from fairies.P30_Cognition.cognition.smart_goal_coordinator import *
