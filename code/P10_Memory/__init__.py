"""
P10_Memory Re-export Shim - Forwards to fairies.P10_Memory

This shim provides backward compatibility for code that imports from P10_Memory
directly instead of fairies.P10_Memory. All exports are forwarded from the
canonical location at fairies.P10_Memory.
"""
try:
    from fairies.P10_Memory import *
except ImportError as e:
    print(f"[P10_Memory shim] Import warning: {e}")
