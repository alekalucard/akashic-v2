"""
Auto-Pip Installer - Automatic dependency resolution for Akashic fairies.

When imports fail due to missing packages, this utility:
1. Detects the missing package
2. Installs it via pip (with user consent or auto-mode)
3. Retries the import

Usage:
    from utils.auto_pip import auto_import, ensure_packages
    
    # Single import with auto-install
    numpy = auto_import("numpy")
    
    # Ensure multiple packages exist
    ensure_packages(["numpy", "pillow", "requests"])
    
    # Wrap a whole import block
    with safe_imports():
        import numpy
        import pandas
        from PIL import Image

Configuration:
    Set AKASHIC_AUTO_PIP=1 to enable fully automatic installs
    Set AKASHIC_AUTO_PIP=0 to disable (will raise ImportError)
    Default: prompt user (in interactive mode) or auto (in daemon mode)
"""

import os
import sys
import subprocess
import importlib
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# Common package name mappings (pip name != import name)
PACKAGE_MAP = {
    "PIL": "pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "serial": "pyserial",
    "dotenv": "python-dotenv",
    "magic": "python-magic",
    "jwt": "pyjwt",
    "dateutil": "python-dateutil",
    "crypto": "pycryptodome",
}

# Packages that should NEVER be auto-installed (security)
BLOCKED_PACKAGES = {
    "os", "sys", "subprocess", "shutil", "pathlib",  # Built-ins
    "ctypes", "multiprocessing",  # Low-level
}

# Track what we've installed this session
_installed_this_session: List[str] = []


def get_pip_name(import_name: str) -> str:
    """Convert import name to pip package name."""
    # Check mapping first
    if import_name in PACKAGE_MAP:
        return PACKAGE_MAP[import_name]
    # Handle submodules (e.g., "PIL.Image" -> "pillow")
    base = import_name.split(".")[0]
    if base in PACKAGE_MAP:
        return PACKAGE_MAP[base]
    return import_name


def is_auto_mode() -> bool:
    """Check if auto-install is enabled."""
    env = os.environ.get("AKASHIC_AUTO_PIP", "").lower()
    if env == "1" or env == "true" or env == "yes":
        return True
    if env == "0" or env == "false" or env == "no":
        return False
    # Default: auto in daemon mode, prompt in interactive
    return not sys.stdin.isatty()


def pip_install(package: str, upgrade: bool = False) -> bool:
    """
    Install a package via pip.
    
    Returns True if successful, False otherwise.
    """
    if package.lower() in BLOCKED_PACKAGES:
        print(f"[auto_pip] BLOCKED: {package} is on the security blocklist")
        return False
    
    cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.append(package)
    
    try:
        print(f"[auto_pip] Installing {package}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
        )
        
        if result.returncode == 0:
            print(f"[auto_pip] Successfully installed {package}")
            _installed_this_session.append(package)
            return True
        else:
            print(f"[auto_pip] Failed to install {package}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[auto_pip] Timeout installing {package}")
        return False
    except Exception as e:
        print(f"[auto_pip] Error installing {package}: {e}")
        return False


def auto_import(
    module_name: str,
    package: Optional[str] = None,
    auto_install: Optional[bool] = None,
) -> Any:
    """
    Import a module, auto-installing if needed.
    
    Args:
        module_name: The module to import (e.g., "numpy")
        package: Override pip package name if different
        auto_install: Override auto-install behavior
        
    Returns:
        The imported module
        
    Raises:
        ImportError: If import fails and auto-install is disabled/fails
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        pip_name = package or get_pip_name(module_name)
        
        # Check if we should auto-install
        should_install = auto_install if auto_install is not None else is_auto_mode()
        
        if not should_install:
            raise ImportError(
                f"Module '{module_name}' not found. "
                f"Install with: pip install {pip_name}"
            ) from e
        
        # Attempt install
        if pip_install(pip_name):
            # Clear import cache and retry
            importlib.invalidate_caches()
            try:
                return importlib.import_module(module_name)
            except ImportError:
                raise ImportError(
                    f"Installed {pip_name} but still can't import {module_name}"
                ) from e
        else:
            raise ImportError(
                f"Failed to auto-install {pip_name} for module {module_name}"
            ) from e


def ensure_packages(packages: List[str], auto_install: Optional[bool] = None) -> Dict[str, bool]:
    """
    Ensure multiple packages are installed.
    
    Args:
        packages: List of package names (import names or pip names)
        auto_install: Override auto-install behavior
        
    Returns:
        Dict mapping package name to success status
    """
    results = {}
    
    for pkg in packages:
        try:
            importlib.import_module(pkg.split("[")[0])  # Handle extras like pkg[extra]
            results[pkg] = True
        except ImportError:
            pip_name = get_pip_name(pkg)
            should_install = auto_install if auto_install is not None else is_auto_mode()
            
            if should_install:
                results[pkg] = pip_install(pip_name)
            else:
                results[pkg] = False
                print(f"[auto_pip] Missing: {pkg} (pip install {pip_name})")
    
    return results


@contextmanager
def safe_imports(auto_install: Optional[bool] = None):
    """
    Context manager for safe imports with auto-install.
    
    Usage:
        with safe_imports():
            import numpy
            import pandas
    
    Note: This doesn't actually catch import errors in the block,
    it's more for documentation. Use ensure_packages() for actual
    pre-flight checks.
    """
    yield


def get_installed_this_session() -> List[str]:
    """Get list of packages installed this session."""
    return _installed_this_session.copy()


def create_import_wrapper(module_name: str, package: Optional[str] = None):
    """
    Create a lazy import wrapper that auto-installs on first access.
    
    Usage:
        numpy = create_import_wrapper("numpy")
        # Later...
        array = numpy.array([1, 2, 3])  # Installs numpy here if needed
    """
    class LazyModule:
        _module = None
        _name = module_name
        _package = package
        
        def __getattr__(self, name):
            if LazyModule._module is None:
                LazyModule._module = auto_import(self._name, self._package)
            return getattr(LazyModule._module, name)
    
    return LazyModule()


# =============================================================================
# FAIRY BOOT HELPER
# =============================================================================

def check_fairy_dependencies(fairy_path: str) -> Dict[str, Any]:
    """
    Scan a fairy file for imports and check if they're available.
    
    Returns dict with:
        - missing: List of missing packages
        - available: List of available packages
        - errors: Any scan errors
    """
    import ast
    from pathlib import Path
    
    path = Path(fairy_path)
    if not path.exists():
        return {"error": f"File not found: {fairy_path}"}
    
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as e:
        return {"error": f"Parse error: {e}"}
    
    imports = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    
    # Filter out local/relative imports
    stdlib = {
        "os", "sys", "time", "json", "re", "typing", "pathlib", 
        "collections", "dataclasses", "threading", "asyncio",
        "functools", "itertools", "contextlib", "abc", "enum",
        "logging", "traceback", "importlib", "weakref", "hashlib",
        "uuid", "random", "math", "copy", "datetime", "glob",
    }
    
    external = imports - stdlib
    missing = []
    available = []
    
    for pkg in external:
        try:
            importlib.import_module(pkg)
            available.append(pkg)
        except ImportError:
            missing.append(pkg)
    
    return {
        "missing": missing,
        "available": available,
        "all_imports": list(imports),
    }


def auto_install_fairy_deps(fairy_path: str) -> bool:
    """
    Check and auto-install dependencies for a fairy.
    
    Returns True if all deps are now available.
    """
    check = check_fairy_dependencies(fairy_path)
    
    if "error" in check:
        print(f"[auto_pip] {check['error']}")
        return False
    
    if not check["missing"]:
        return True
    
    print(f"[auto_pip] Fairy {fairy_path} missing: {check['missing']}")
    
    results = ensure_packages(check["missing"], auto_install=True)
    
    return all(results.values())


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-pip utility")
    parser.add_argument("--check-fairy", help="Check fairy file for missing deps")
    parser.add_argument("--install-fairy-deps", help="Install deps for fairy file")
    parser.add_argument("--ensure", nargs="+", help="Ensure packages are installed")
    
    args = parser.parse_args()
    
    if args.check_fairy:
        result = check_fairy_dependencies(args.check_fairy)
        print(f"Missing: {result.get('missing', [])}")
        print(f"Available: {result.get('available', [])}")
        
    elif args.install_fairy_deps:
        success = auto_install_fairy_deps(args.install_fairy_deps)
        print(f"All deps installed: {success}")
        
    elif args.ensure:
        results = ensure_packages(args.ensure, auto_install=True)
        for pkg, ok in results.items():
            print(f"  {pkg}: {'OK' if ok else 'FAILED'}")
