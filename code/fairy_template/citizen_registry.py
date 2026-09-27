"""
Citizen Registry — The ONE dict.

SINGLE SOURCE OF TRUTH for _CITIZEN_OBJECTS.

Before (2026-04-17): four separate _CITIZEN_OBJECTS dicts existed across
  fairy_template/consolidated.py
  fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py
  (plus two archived versions in P10_Memory/Akashic_Records_Physical/Organ_Templates/)

Each was a DIFFERENT Python dict object. If a fairy registered in one dict,
it was invisible to code reading the others. This caused cascading false
deaths: 105 fairies could go stale simultaneously because the watchdog
read from consolidated's dict while the fairies were registered in the
organ template's dict.

After: one dict, imported by all templates, the registry, the watchdog,
and the heartbeat pulse. No shadow dicts. No import-order surprises.

Usage:
    from fairy_template.citizen_registry import CITIZEN_OBJECTS
    CITIZEN_OBJECTS[name] = fairy_instance

For backward compatibility with code that imported `_CITIZEN_OBJECTS`
from the old locations, both templates re-export this dict as
`_CITIZEN_OBJECTS` at module level — no downstream caller needs to change.
"""

from __future__ import annotations
from typing import Any, Dict

# The canonical dict. Do not shadow or reassign — always mutate in place.
CITIZEN_OBJECTS: Dict[str, Any] = {}

# Backward-compatible alias — downstream code used `_CITIZEN_OBJECTS`.
_CITIZEN_OBJECTS = CITIZEN_OBJECTS
