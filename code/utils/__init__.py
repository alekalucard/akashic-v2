"""
Akashic V2 Utilities

Common utilities for the Akashic system.
"""

import sys

from .auto_pip import (
    auto_import,
    ensure_packages,
    pip_install,
    check_fairy_dependencies,
    auto_install_fairy_deps,
    get_installed_this_session,
    create_import_wrapper,
)


def safe_print(*args, **kwargs):
    """
    Print that handles Unicode encoding errors on Windows console.

    Windows cp1252 console encoding can't display many Unicode characters
    (emojis, special symbols). This function catches encoding errors and
    replaces problematic characters with '?' instead of crashing.

    Usage: Replace print() with safe_print() in any code that might output
    emojis or special Unicode characters.
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Convert all args to strings and encode with replacement
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                # Encode to console encoding with replacement, then decode back
                encoding = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
                safe_args.append(arg.encode(encoding, errors='replace').decode(encoding))
            else:
                safe_args.append(arg)
        try:
            print(*safe_args, **kwargs)
        except UnicodeEncodeError:
            # Last resort: strip all non-ASCII
            ascii_args = []
            for arg in args:
                if isinstance(arg, str):
                    ascii_args.append(arg.encode('ascii', errors='replace').decode('ascii'))
                else:
                    ascii_args.append(arg)
            print(*ascii_args, **kwargs)


__all__ = [
    "auto_import",
    "ensure_packages",
    "pip_install",
    "check_fairy_dependencies",
    "auto_install_fairy_deps",
    "get_installed_this_session",
    "create_import_wrapper",
    "safe_print",
]
