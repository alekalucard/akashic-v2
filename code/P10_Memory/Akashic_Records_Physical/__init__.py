# Akashic Records Physical - The DNA of the system
"""
Physical storage layer for Akashic records.

Contains:
- Organ_Templates: Base class templates for all fairies
"""

# Export organ template for easy access
try:
    from .Organ_Templates.Organ_Template_0_1_2 import (
        MyFairy as Fairy,
        MyOrganFairy,
        MyOrganShadow,
    )
except ImportError:
    pass
