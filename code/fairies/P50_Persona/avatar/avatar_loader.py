# Avatar Loader - Load and display fairy avatars from calibration files
# P50_Persona/avatar/avatar_loader.py

from __future__ import annotations

import os
import json
from typing import Optional, Dict, Any
from pathlib import Path

# Get assets directory
ASSETS_DIR = Path(__file__).parent / "assets"


def get_fairy_asset_path(fairy_name: str) -> Optional[Path]:
    """Get the asset directory for a fairy."""
    fairy_dir = ASSETS_DIR / fairy_name.lower()
    if fairy_dir.exists():
        return fairy_dir
    return None


def load_calibration(fairy_name: str) -> Optional[Dict[str, Any]]:
    """
    Load calibration data for a fairy.
    
    Args:
        fairy_name: "ClaudeFairy" or "Sourpatches"
    
    Returns:
        Calibration dict or None if not found
    """
    fairy_dir = get_fairy_asset_path(fairy_name)
    if not fairy_dir:
        print(f"[AvatarLoader] No asset directory for {fairy_name}")
        return None
    
    calib_path = fairy_dir / "calibration.json"
    if not calib_path.exists():
        print(f"[AvatarLoader] No calibration file for {fairy_name}")
        return None
    
    with open(calib_path, "r") as f:
        return json.load(f)


def get_base_image_path(fairy_name: str) -> Optional[Path]:
    """Get the path to a fairy's base image."""
    fairy_dir = get_fairy_asset_path(fairy_name)
    if not fairy_dir:
        return None
    
    calib = load_calibration(fairy_name)
    if not calib:
        return None
    
    base_image = calib.get("base_image", "")
    if not base_image:
        return None
    
    image_path = fairy_dir / base_image
    if image_path.exists():
        return image_path
    
    return None


def list_available_fairies() -> list:
    """List all fairies with calibration files."""
    fairies = []
    if ASSETS_DIR.exists():
        for item in ASSETS_DIR.iterdir():
            if item.is_dir():
                calib = item / "calibration.json"
                if calib.exists():
                    fairies.append(item.name)
    return fairies


def show_fairy_avatar(
    fairy_name: str,
    x: int = None,
    y: int = None,
    size: tuple = (256, 256)
) -> bool:
    """
    Show a fairy's avatar on screen.
    
    Args:
        fairy_name: "ClaudeFairy" or "Sourpatches"
        x, y: Screen position (None = center)
        size: Widget size
    
    Returns:
        True if successful
    """
    from .somatic_avatar_fairy import create_avatar_fairy, get_avatar_fairy
    from .fairy_frame import FairyFrame, FairyRegion
    
    # Get calibration
    calib = load_calibration(fairy_name)
    if not calib:
        print(f"[AvatarLoader] No calibration for {fairy_name}")
        return False
    
    # Get image path
    image_path = get_base_image_path(fairy_name)
    if not image_path:
        print(f"[AvatarLoader] No base image for {fairy_name}")
        print(f"[AvatarLoader] Please copy the image to: {get_fairy_asset_path(fairy_name)}")
        return False
    
    # Create avatar fairy
    fairy = create_avatar_fairy(
        str(image_path),
        name=calib.get("name", fairy_name),
        size=size,
    )
    
    # Apply calibrated anchors to the frame
    if fairy._widget and fairy._widget.frame:
        frame = fairy._widget.frame
        anchors = calib.get("anchors", {})
        
        for region_name, pos in anchors.items():
            try:
                region = FairyRegion(region_name)
                if isinstance(pos, dict):
                    # Paired region
                    for side, coords in pos.items():
                        frame.calibrate(region, tuple(coords), side)
                else:
                    frame.calibrate(region, tuple(pos))
            except (ValueError, TypeError):
                pass
    
    # Show
    return fairy.show(x, y)


def print_fairy_info(fairy_name: str) -> None:
    """Print info about a fairy's configuration."""
    calib = load_calibration(fairy_name)
    if not calib:
        print(f"No calibration found for {fairy_name}")
        return
    
    print(f"\n{'='*50}")
    print(f"  {calib.get('name', fairy_name)}")
    if calib.get('title'):
        print(f"  \"{calib['title']}\"")
    print(f"{'='*50}")
    
    if calib.get('description'):
        print(f"\n{calib['description']}")
    
    if calib.get('visual_notes'):
        print(f"\nVisual Notes:")
        for k, v in calib['visual_notes'].items():
            print(f"  • {k}: {v}")
    
    if calib.get('personality_notes'):
        print(f"\nPersonality:")
        for k, v in calib['personality_notes'].items():
            print(f"  • {k}: {v}")
    
    image_path = get_base_image_path(fairy_name)
    if image_path:
        print(f"\n[OK] Base image found: {image_path}")
    else:
        fairy_dir = get_fairy_asset_path(fairy_name)
        print(f"\n[X] Base image NOT FOUND")
        print(f"   Copy image to: {fairy_dir / calib.get('base_image', 'base.jpg')}")
    
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# QUICK ACCESS FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def show_claudefairy(x: int = None, y: int = None, size: tuple = (256, 256)) -> bool:
    """Show ClaudeFairy's avatar."""
    return show_fairy_avatar("claudefairy", x, y, size)


def show_sourpatches(x: int = None, y: int = None, size: tuple = (256, 256)) -> bool:
    """Show Sourpatches' avatar."""
    return show_fairy_avatar("sourpatches", x, y, size)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    print("Available fairies:", list_available_fairies())
    
    if len(sys.argv) > 1:
        fairy = sys.argv[1]
        print_fairy_info(fairy)
    else:
        # Print all
        for fairy in list_available_fairies():
            print_fairy_info(fairy)
