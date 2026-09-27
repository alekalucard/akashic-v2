"""
Fairy Template - Passthrough to Organ Template v0.3.0.

FIFTH RING PRINCIPLE: POSTAL-ONLY, NO MIXINS
============================================
The Organ Template is the ONE source of truth for fairy logic.
This file exists only as a convenient import path - nothing more.

Usage:
    from fairy_template import Fairy

    class MyFairy(Fairy):
        ACTOR_NAME = "MyFairy"
        ...

FIX 2026-02-06: Updated to import directly from the production Organ Template
package (fairies.P00_Autonomic.organ_template) instead of using dynamic
file-based import from Organ_Templates archive folder. The dynamic import
was fragile — version mismatches caused AttributeError crashes at boot.

The canonical import chain is now:
    fairy_template → fairies.P00_Autonomic.organ_template → Organ_Template_0_3_0.py
"""

import sys
import os

# ═══════════════════════════════════════════════════════════════════════════════
# DIRECT IMPORT FROM PRODUCTION ORGAN TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════
# We import directly from the organ_template package, NOT via dynamic file
# loading. This is safer — one source of truth, no version mismatch possible.

# Ensure project root is on sys.path so "fairies.P00_Autonomic..." resolves
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)  # fairy_template is at project root level
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fairies.P00_Autonomic.organ_template import (
    # Core classes - what fairies inherit from
    MyOrganFairy,
    MyOrganShadow,
    MyFairy,
    Fairy as _Fairy,
    AkashicActorCore,

    # Hierarchy tiers
    FairyTier,
    WAKING_MIND_ALLOWED_TOPICS,

    # Tracer system
    Tracer,
    TracerType,
    TracerStatus,
    TracerRegistry,
    get_tracer_registry,

    # Profile system
    FairyProfile,
    FairyState as _ProfileFairyState,
    FairyProfileRegistry,
    get_fairy_registry,

    # Postal system
    PostalHub,
    get_postal_hub,

    # Utilities
    MiniCollisionChamber,
    get_worker_pool,

    # Constants
    CHANNEL,
    DIR_CHANNEL,
    TEMPLATE_VERSION,
)

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — What fairies import from fairy_template
# ═══════════════════════════════════════════════════════════════════════════════

# Core class — THE fairy base class (both names work)
Fairy = _Fairy
MyFairy = _Fairy

# Backward compatibility alias
FairyBase = _Fairy

# State definitions (simple enum, lives in fairy_template/states.py)
from .states import FairyState, VALID_TRANSITIONS, can_transition

__all__ = [
    # Main classes
    "Fairy",
    "MyFairy",
    "FairyBase",
    "FairyState",

    # Backward compatibility
    "MyOrganFairy",
    "MyOrganShadow",
    "AkashicActorCore",

    # Infrastructure
    "PostalHub",
    "MiniCollisionChamber",
    "get_postal_hub",

    # Tiers
    "FairyTier",
    "WAKING_MIND_ALLOWED_TOPICS",

    # Tracers
    "Tracer",
    "TracerType",
    "TracerStatus",
    "TracerRegistry",
    "get_tracer_registry",

    # Profile
    "FairyProfile",
    "FairyProfileRegistry",
    "get_fairy_registry",

    # State transitions
    "VALID_TRANSITIONS",
    "can_transition",

    # Utilities
    "get_worker_pool",

    # Constants
    "CHANNEL",
    "DIR_CHANNEL",
    "TEMPLATE_VERSION",
]
