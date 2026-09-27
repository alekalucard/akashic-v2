"""
Shared Postal Hub - REDIRECT TO SOURCE OF TRUTH

This file redirects to the ROOT P00_Autonomic/nervous_system/shared_postal_hub.py
which is THE source of truth for postal hub functionality.

All imports from this location are forwarded to the correct module.

FIX 2026-02-06: Previous approach used importlib.util.spec_from_file_location with
a unique module name ("_root_shared_postal_hub"), creating a SEPARATE module object
with its own globals. This caused _SHARED_FABRIC to exist in two copies:
  - P00_Autonomic.nervous_system.shared_postal_hub (set by server.py)
  - _root_shared_postal_hub (always None — never set)
Result: 20+ fairies got orphan TensorFabric instances, deaf to heartbeats.

NEW approach: Check sys.modules FIRST for the canonical module. Only fall back to
filesystem import if not yet loaded, and REGISTER it under canonical name so all
future imports share the same module (and same _SHARED_FABRIC global).
"""

__all__ = [
    "set_shared_fabric",
    "get_shared_fabric",
    "signal_global_shutdown",
    "is_global_shutdown",
    "reset_global_shutdown",
    "get_shared_postal_hub",
    "get_fairy_postal",
    "get_postal_hub",
    "get_postal_status",
    "is_using_fallback",
    "FairyPostalWrapper",
    "InMemoryPostalHub",
    "PostalHubStub",
    "SharedPostalHub",  # Legacy alias for InMemoryPostalHub
]

# Lazy import cache
_source_module = None

# The canonical module name that server.py imports from
_CANONICAL_NAME = "P00_Autonomic.nervous_system.shared_postal_hub"


def _get_source():
    """
    Get the source of truth module — SHARING the same instance as server.py.

    Priority order:
    1. Check sys.modules for canonical name (server.py already loaded it)
    2. Fall back to filesystem import, then REGISTER under canonical name
       so all paths share the same globals (especially _SHARED_FABRIC)
    """
    global _source_module
    if _source_module is None:
        import sys
        import importlib.util
        from pathlib import Path

        # FIRST: Check if the canonical module is already loaded by server.py
        # This is the common case — server.py imports from P00_Autonomic.nervous_system.shared_postal_hub
        # BEFORE any fairy code runs. We MUST reuse that exact module object so
        # _SHARED_FABRIC is the same global that server.py already set.
        canonical = sys.modules.get(_CANONICAL_NAME)
        if canonical is not None:
            _source_module = canonical
            return _source_module

        # Also check if it was loaded under the old unique name (backward compat)
        old_name = sys.modules.get("_root_shared_postal_hub")
        if old_name is not None:
            _source_module = old_name
            return _source_module

        # FALLBACK: Load from filesystem (rare — only if shim is imported before server.py)
        project_root = Path(__file__).parent.parent.parent.parent
        source_path = project_root / "P00_Autonomic" / "nervous_system" / "shared_postal_hub.py"

        if not source_path.exists():
            raise ImportError(f"Source of truth not found: {source_path}")

        spec = importlib.util.spec_from_file_location(
            _CANONICAL_NAME,  # Use canonical name so it's findable by server.py later
            source_path
        )
        _source_module = importlib.util.module_from_spec(spec)

        # CRITICAL: Register in sys.modules BEFORE exec_module to prevent
        # circular imports and ensure server.py finds the same object
        sys.modules[_CANONICAL_NAME] = _source_module

        spec.loader.exec_module(_source_module)
    return _source_module


# System utilities - lazy forwarding functions
def set_shared_fabric(fabric):
    return _get_source().set_shared_fabric(fabric)


def get_shared_fabric():
    return _get_source().get_shared_fabric()


def signal_global_shutdown():
    return _get_source().signal_global_shutdown()


def is_global_shutdown():
    return _get_source().is_global_shutdown()


def reset_global_shutdown():
    return _get_source().reset_global_shutdown()


# Postal hub - lazy forwarding functions
def get_shared_postal_hub():
    return _get_source().get_shared_postal_hub()


def get_fairy_postal(fairy=None):
    return _get_source().get_fairy_postal(fairy)


def get_postal_hub():
    return _get_source().get_postal_hub()


def get_postal_status():
    return _get_source().get_postal_status()


def is_using_fallback():
    return _get_source().is_using_fallback()


# Classes - lazy property access via __getattr__
def __getattr__(name):
    """Lazy attribute access for classes (FairyPostalWrapper, InMemoryPostalHub, PostalHubStub)."""
    if name in ("FairyPostalWrapper", "InMemoryPostalHub", "PostalHubStub"):
        return getattr(_get_source(), name)
    # Legacy alias: SharedPostalHub -> InMemoryPostalHub
    if name == "SharedPostalHub":
        return getattr(_get_source(), "InMemoryPostalHub")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
