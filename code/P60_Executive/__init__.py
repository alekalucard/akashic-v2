"""
P60_Executive Re-export Shim - Forwards to fairies.P60_Executive

This shim provides backward compatibility for code that imports from P60_Executive
directly instead of fairies.P60_Executive. All exports are forwarded from the
canonical location at fairies.P60_Executive.
"""
try:
    from fairies.P60_Executive.CardinalFairy import CardinalFairy
    __all__ = ["CardinalFairy"]
except ImportError as e:
    print(f"[P60_Executive shim] Import warning: {e}")
    __all__ = []
