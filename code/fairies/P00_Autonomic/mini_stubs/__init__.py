"""
P00 Mini-Stubs - Minimal Bootstrap Capabilities

These are intentionally minimal implementations - just enough to bootstrap
the full versions that live in their respective planes:

- MiniMemory (full version in P10_Memory)
- MiniCognition (full version in P30_Cognition)
- MiniBody (full version in P20_Somatic)

"P00 is the BIOS. It doesn't run the OS. It boots the OS."
"""

from .mini_memory import MiniMemory
from .mini_cognition import MiniCognition
from .mini_body import MiniBody

__all__ = ['MiniMemory', 'MiniCognition', 'MiniBody']
