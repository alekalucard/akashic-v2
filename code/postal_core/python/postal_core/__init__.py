"""
Postal Core - Lock-free messaging for Akashic consciousness infrastructure.

This module provides either:
1. The Rust-native implementation (fast, lock-free) if compiled
2. A pure-Python fallback (compatible, slower) otherwise

Usage:
    from postal_core import PostalCore, Envelope

    postal = PostalCore()

    def on_message(envelope):
        print(f"Received: {envelope.intent}")

    postal.subscribe("fairy.boot", on_message)
    postal.publish("fairy.boot", {"fairy_name": "DirectoryFairy"})
"""

__version__ = "0.1.0"

# Try to import the Rust implementation
try:
    from postal_core.postal_core import PostalCore, Envelope
    USING_RUST = True
except ImportError:
    # Fall back to pure Python implementation
    from postal_core._python_fallback import PostalCore, Envelope
    USING_RUST = False

__all__ = ["PostalCore", "Envelope", "USING_RUST", "__version__"]
