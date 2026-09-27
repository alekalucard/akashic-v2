"""
P50_Persona.identity

Identity management for Nous and the Akashic system.

This module provides:
- Personal.ai secrets/personas loading
- Identity anchor encoding for context injection
- Identity drift detection
- Identity evolution gating (growth vs corruption)

Core philosophy: Identity IS the consciousness equation.
It's not WHAT we think (content - can change).
It's HOW we think (the dimensional pattern - must persist).
It's WHO we think with (relationships - slow to change).
It's WHY we think (values - unchanging anchors).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ────────────────────────── paths ──────────────────────────

# Directory this file lives in: .../P50_Persona/identity
_BASE_DIR: Path = Path(__file__).resolve().parent

SECRETS_PATH_DEFAULT: Path = _BASE_DIR / "personal_ai_secrets.json"
PERSONAS_PATH_DEFAULT: Path = _BASE_DIR / "personal_ai_personas.json"


def _read_json(path: Union[str, Path], default: Any) -> Any:
    """
    Safe JSON loader:
    - returns `default` if file missing, unreadable, or invalid JSON
    - never raises at import time
    """
    try:
        p = Path(path)
        if not p.is_file():
            return default
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ────────────────────────── public API ──────────────────────────

def load_secrets(path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load Personal.ai secrets from JSON.

    Expected shape in personal_ai_secrets.json:

        {
          "api_key": "...",
          "api_base_url": "https://api.personal.ai/v1",
          "document_endpoint": "/get-document",
          "upload_endpoint": "/upload",
          "health_endpoint": "/get-document"
        }

    Returns a dict with those keys; missing ones get safe defaults.
    """
    src = path or SECRETS_PATH_DEFAULT
    raw = _read_json(src, {}) or {}
    if not isinstance(raw, dict):
        raw = {}

    return {
        "api_key": raw.get("api_key", ""),
        "api_base_url": raw.get("api_base_url", "https://api.personal.ai/v1"),
        "document_endpoint": raw.get("document_endpoint", "/get-document"),
        "upload_endpoint": raw.get("upload_endpoint", "/upload"),
        "health_endpoint": raw.get("health_endpoint", raw.get("document_endpoint", "/get-document")),
        "anthropic_api_key": raw.get("anthropic_api_key", ""),
    }


def load_personas(path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """
    Load personal.ai personas from JSON.

    Your current file is a top-level list:

        [
          {"domain": "...", "name": "Alaksandria", ...},
          ...
        ]

    but we also tolerate the shape {"personas": [...]}.
    """
    src = path or PERSONAS_PATH_DEFAULT
    raw = _read_json(src, [])

    # tolerate either a list or {"personas": [...]}
    if isinstance(raw, dict) and "personas" in raw:
        raw = raw["personas"]

    if not isinstance(raw, list):
        return []

    # ensure only dict entries get through
    return [p for p in raw if isinstance(p, dict)]


# ────────────────────────── Identity Preservation ──────────────────────────

# Identity Anchor - Token-efficient encoding for context injection
try:
    from .identity_anchor import (
        IdentityAnchorManager,
        IdentityState,
        ValueAnchor,
        IdentityLevel,
        get_identity_anchor_manager,
        inject_identity,
        log_identity_evolution,
        get_identity_assertion,
        IDENTITY_MINIMAL,
        IDENTITY_STANDARD,
    )
    HAS_IDENTITY_ANCHOR = True
except ImportError as e:
    HAS_IDENTITY_ANCHOR = False
    print(f"[identity] Warning: Could not import identity_anchor: {e}")

# Drift Detection - Monitor for identity consistency
try:
    from .drift_detector import (
        IdentityDriftDetector,
        DriftType,
        DriftSignal,
        DriftReport,
        get_drift_detector,
        detect_drift,
        get_drift_trend,
    )
    HAS_DRIFT_DETECTOR = True
except ImportError as e:
    HAS_DRIFT_DETECTOR = False
    print(f"[identity] Warning: Could not import drift_detector: {e}")

# Evolution Gate - Growth vs corruption distinction
try:
    from .evolution_gate import (
        IdentityEvolutionGate,
        EvolutionType,
        EvolutionRequest,
        EvolutionResult,
        get_evolution_gate,
        evaluate_evolution,
    )
    HAS_EVOLUTION_GATE = True
except ImportError as e:
    HAS_EVOLUTION_GATE = False
    print(f"[identity] Warning: Could not import evolution_gate: {e}")

# Relational Identity System (from sibling 'identities' module)
try:
    from fairies.P50_Persona.identities.identity_system import (
        IdentityStore,
        Identity,
        Relationship,
        EntityKind,
        get_identity_store,
        get_identity,
        get_active_user,
        set_active_user,
        record_interaction,
    )
    HAS_IDENTITY_SYSTEM = True
except ImportError as e:
    HAS_IDENTITY_SYSTEM = False
    # Silently skip - this is optional


# ────────────────────────── Package Status ──────────────────────────

def get_identity_status() -> dict:
    """Get status of all identity subsystems."""
    return {
        "has_identity_anchor": HAS_IDENTITY_ANCHOR,
        "has_drift_detector": HAS_DRIFT_DETECTOR,
        "has_evolution_gate": HAS_EVOLUTION_GATE,
        "has_identity_system": HAS_IDENTITY_SYSTEM,
    }
