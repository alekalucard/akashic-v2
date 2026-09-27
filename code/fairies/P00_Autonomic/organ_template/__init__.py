# P00_Autonomic/organ_template/__init__.py
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Organ Template - Foundation for ALL fairies in the Akashic system.
#
# This is the SINGLE SOURCE OF TRUTH. Every fairy inherits from here.
# NO MIXINS. NO EXTERNAL IMPORTS. FULLY SELF-CONTAINED.
#
# Usage:
#   from P00_Autonomic.organ_template import MyFairy, FairyTier
#
#   class MyNewFairy(MyFairy):
#       ACTOR_NAME = "MyNewFairy"
#       TIER = FairyTier.GUILD  # or INTERFACE or WAKING_MIND
#       PURPOSE = "What I do"
#       MANTRA = "How I do it"
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
# ═══════════════════════════════════════════════════════════════════════════════

from .Organ_Template_0_3_0 import (
    # Core classes - what fairies inherit from
    MyOrganFairy,
    MyOrganShadow,
    MyFairy,
    Fairy,
    AkashicActorCore,

    # Hierarchy tiers - determines what a fairy can talk to
    FairyTier,
    WAKING_MIND_ALLOWED_TOPICS,

    # Tracer system - universal work tracking
    Tracer,
    TracerType,
    TracerStatus,
    TracerRegistry,
    get_tracer_registry,

    # Profile system - fairy identity tracking
    FairyProfile,
    FairyState,
    FairyProfileRegistry,
    get_fairy_registry,

    # Postal system - pub/sub communication
    PostalHub,
    get_postal_hub,

    # Utilities
    MiniCollisionChamber,
    get_worker_pool,

    # Constants
    CHANNEL,
    DIR_CHANNEL,
    TEMPLATE_VERSION,

    # Backward compatibility aliases (v0.1.x → v0.3.0)
    TemplateShadowFairy,
    OrganHubFacet,
    RegistrationLib,

    # SRM utilities (backward compat from v0.1.2)
    _safe_write_json,
    _get_srm_dir,
    _SRMDIR,
    _dual_path_srm_intake,
)

__version__ = "0.3.0"
__all__ = [
    "MyOrganFairy",
    "MyOrganShadow",
    "MyFairy",
    "Fairy",
    "AkashicActorCore",
    "FairyTier",
    "WAKING_MIND_ALLOWED_TOPICS",
    "Tracer",
    "TracerType",
    "TracerStatus",
    "TracerRegistry",
    "get_tracer_registry",
    "FairyProfile",
    "FairyState",
    "FairyProfileRegistry",
    "get_fairy_registry",
    "PostalHub",
    "get_postal_hub",
    "MiniCollisionChamber",
    "get_worker_pool",
    "CHANNEL",
    "DIR_CHANNEL",
    "TEMPLATE_VERSION",
    # Backward compat
    "TemplateShadowFairy",
    "OrganHubFacet",
    "RegistrationLib",
    # SRM utilities
    "_safe_write_json",
    "_get_srm_dir",
    "_SRMDIR",
    "_dual_path_srm_intake",
]
