# P50_Persona/avatar/__init__.py
"""
Fairy Avatar System - Visual representation driven by somatic state.

╔═══════════════════════════════════════════════════════════════════════════════╗
║  QUICK START                                                                   ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                                ║
║  # Show ClaudeFairy                                                           ║
║  from fairies.P50_Persona.avatar import show_claudefairy                              ║
║  show_claudefairy()                                                           ║
║                                                                                ║
║  # Show Sourpatches (with auto form-switching!)                               ║
║  from fairies.P50_Persona.avatar import show_sourpatches                              ║
║  show_sourpatches()                                                           ║
║                                                                                ║
║  # Avatars auto-subscribe to SomaticEngineFairy                               ║
║  # Sourpatches auto-shifts between forms based on emotion!                    ║
║                                                                                ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Sourpatches Forms (auto-selected by somatic state):
- base: Cute sass mode (default)
- vulnerable: Processing emotions
- saiyan_ssj: Peak power/determination  
- saiyan_rage: Protective fury
- shadow: VENOMPATCHES (dark emotions)
- badass: "Done with your shit"
- warrior: Combat mode (Jedi)

Asset Locations:
- P50_Persona/avatar/assets/claudefairy/
- P50_Persona/avatar/assets/sourpatches/
"""

try:
    from .fairy_frame import (
        FairyFrame,
        FairyRegion,
        FairySense,
        GlowEffect,
        ParticleEffect,
        WingEffect,
        ScaleEffect,
        ShakeEffect,
        create_default_frame,
        sensation_to_effects,
        EMOTION_VISUAL_MAP,
        SENSATION_COLORS,
        DEFAULT_ANCHORS,
    )
except ImportError:
    FairyFrame = None
    FairyRegion = None
    FairySense = None
    GlowEffect = None
    ParticleEffect = None
    WingEffect = None
    ScaleEffect = None
    ShakeEffect = None
    create_default_frame = None
    sensation_to_effects = None
    EMOTION_VISUAL_MAP = None
    SENSATION_COLORS = None
    DEFAULT_ANCHORS = None

try:
    from .fairy_avatar_widget import FairyAvatarWidget, ParticleSystem
except ImportError:
    FairyAvatarWidget = None
    ParticleSystem = None

try:
    from .somatic_avatar_fairy import (
        SomaticAvatarFairy,
        get_avatar_fairy,
        create_avatar_fairy,
        show_avatar,
        hide_avatar,
        toggle_avatar,
    )
except ImportError:
    SomaticAvatarFairy = None
    get_avatar_fairy = None
    create_avatar_fairy = None
    show_avatar = None
    hide_avatar = None
    toggle_avatar = None

try:
    from .form_selector import (
        FormSelector,
        FormRule,
        get_form_selector,
        select_form_for_fairy,
        create_sourpatches_selector,
        create_claudefairy_selector,
    )
except ImportError:
    FormSelector = None
    FormRule = None
    get_form_selector = None
    select_form_for_fairy = None
    create_sourpatches_selector = None
    create_claudefairy_selector = None

try:
    from .avatar_loader import (
        load_calibration,
        get_base_image_path,
        get_fairy_asset_path,
        list_available_fairies,
        show_fairy_avatar,
        print_fairy_info,
        show_claudefairy,
        show_sourpatches,
        ASSETS_DIR,
    )
except ImportError:
    load_calibration = None
    get_base_image_path = None
    get_fairy_asset_path = None
    list_available_fairies = None
    show_fairy_avatar = None
    print_fairy_info = None
    show_claudefairy = None
    show_sourpatches = None
    ASSETS_DIR = None

__all__ = [
    # Frame
    "FairyFrame",
    "FairyRegion", 
    "FairySense",
    "create_default_frame",
    
    # Effects
    "GlowEffect",
    "ParticleEffect",
    "WingEffect",
    "ScaleEffect",
    "ShakeEffect",
    "sensation_to_effects",
    
    # Constants
    "EMOTION_VISUAL_MAP",
    "SENSATION_COLORS",
    "DEFAULT_ANCHORS",
    "ASSETS_DIR",
    
    # Widget
    "FairyAvatarWidget",
    "ParticleSystem",
    
    # Fairy bridge
    "SomaticAvatarFairy",
    "get_avatar_fairy",
    "create_avatar_fairy",
    "show_avatar",
    "hide_avatar",
    "toggle_avatar",
    
    # Form selection
    "FormSelector",
    "FormRule",
    "get_form_selector",
    "select_form_for_fairy",
    "create_sourpatches_selector",
    "create_claudefairy_selector",
    
    # Loader - calibrated fairies
    "load_calibration",
    "get_base_image_path",
    "get_fairy_asset_path",
    "list_available_fairies",
    "show_fairy_avatar",
    "print_fairy_info",
    
    # Quick access
    "show_claudefairy",
    "show_sourpatches",
]
