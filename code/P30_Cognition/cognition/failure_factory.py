# Shim: Forwards to canonical location at fairies.P30_Cognition.cognition.failure_factory
"""
FIX 2026-02-02: This shim allows 'from P30_Cognition.cognition.failure_factory import ...'
to work even though the real file is at fairies/P30_Cognition/cognition/failure_factory.py
"""
from fairies.P30_Cognition.cognition.failure_factory import *
