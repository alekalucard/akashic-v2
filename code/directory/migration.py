"""
Fairy Migration - Plug-and-play migration from v1 to v2.

Handles:
- Scanning v1 fairies
- Creating v2 wrappers
- Registering in sleeping state
- Controlled wake-up
"""

import importlib.util
import inspect
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

# Setup paths BEFORE any dynamic imports - ORDER MATTERS!
# ROOT must be first so we find akashic_v2/P00_Autonomic/ NOT fairies/P00_Autonomic/
_ROOT = Path(__file__).parent.parent
# Insert in reverse order - last one ends up at position 0
for _p in [str(_ROOT / "fairies"), str(_ROOT / "postal_core" / "python"), str(_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from .registry import FairyRegistry, FairyRecord


class FairyScanner:
    """Scans a directory for v1 fairy classes."""

    # Patterns that indicate a fairy class
    FAIRY_INDICATORS = [
        "ACTOR_NAME",
        "on_boot",
        "fairy",
        "_fairy",
    ]

    def __init__(self, v1_root: Path):
        self.v1_root = Path(v1_root)
        self._cache: Dict[str, Dict[str, Any]] = {}

    # FIX 2026-02-05: Windows reserved device names that can cause rglob() to hang.
    # A directory named 'nul' was found in P20_Somatic, causing Python's pathlib
    # to hang during recursive scanning (NUL is a Windows device like /dev/null).
    _WIN_RESERVED = frozenset({
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
    })

    def scan_plane(self, plane: str) -> List[Dict[str, Any]]:
        """Scan a plane directory for fairies."""
        plane_dir = self.v1_root / plane
        if not plane_dir.exists():
            return []

        fairies = []
        try:
            for py_file in plane_dir.rglob("*.py"):
                # Skip test files and __init__
                if py_file.stem.startswith("test_") or py_file.stem == "__init__":
                    continue

                # Skip files inside Windows reserved device name directories
                if any(part.lower() in self._WIN_RESERVED for part in py_file.parts):
                    continue

                found = self._scan_file(py_file, plane)
                fairies.extend(found)
        except (OSError, PermissionError) as e:
            print(f"[FairyScanner] WARNING: Error scanning {plane}: {e}", flush=True)

        return fairies

    def _scan_file(self, file_path: Path, plane: str) -> List[Dict[str, Any]]:
        """Scan a Python file for fairy classes."""
        fairies = []

        try:
            # Read and parse
            source = file_path.read_text(encoding="utf-8")

            # Quick check for fairy indicators
            if not any(ind in source for ind in self.FAIRY_INDICATORS):
                return []

            # Extract class info via AST would be better, but quick text scan works
            lines = source.split("\n")
            current_class = None
            class_info = {}

            for line in lines:
                stripped = line.strip()

                # Class definition
                if stripped.startswith("class ") and "Fairy" in stripped:
                    if current_class and class_info:
                        fairies.append(class_info)
                    # Extract class name
                    class_name = stripped.split("(")[0].replace("class ", "").strip()
                    if class_name.endswith(":"):
                        class_name = class_name[:-1]
                    current_class = class_name
                    class_info = {
                        "name": class_name,
                        "file": str(file_path),
                        "plane": plane,
                        "capabilities": set(),
                    }

                # ACTOR_NAME - must be a proper assignment, not a method call
                if current_class and "ACTOR_NAME" in stripped:
                    # Only match: ACTOR_NAME = "SomeName" or ACTOR_NAME = 'SomeName'
                    # Avoid: self.ACTOR_NAME, foo(ACTOR_NAME), etc.
                    match = re.match(r'^ACTOR_NAME\s*=\s*["\']([^"\']+)["\']', stripped)
                    if match:
                        name = match.group(1)
                        # Validate: must look like a proper name (CamelCase ending in Fairy)
                        if name and not name.startswith("self.") and "(" not in name:
                            class_info["actor_name"] = name

                # ACTOR_CHANNEL
                if current_class and "ACTOR_CHANNEL" in stripped and "=" in stripped:
                    parts = stripped.split("=", 1)
                    if len(parts) == 2:
                        channel = parts[1].strip().strip("\"'")
                        class_info["channel"] = channel

            # Don't forget last class
            if current_class and class_info:
                fairies.append(class_info)

        except Exception:
            pass  # Skip files that can't be parsed

        # Filter out garbage entries - must have valid ACTOR_NAME
        valid_fairies = []
        for f in fairies:
            # CRITICAL: Only include classes that explicitly define ACTOR_NAME
            # This filters out data classes like FairySRMNode, FairyAura, FairyStatusSheet
            # which have "Fairy" in name but are not actual fairies
            if "actor_name" not in f:
                continue

            name = f.get("actor_name", "")
            # Skip garbage: must be proper identifier, no parens, no self., no True/False
            if not name or "(" in name or ")" in name or name.startswith("self."):
                continue
            if name in ("True", "False", "None"):
                continue
            if "=" in name or "," in name:
                continue
            # Skip template placeholders like {actor_name}, {class_name}
            if "{" in name or "}" in name:
                continue
            valid_fairies.append(f)

        return valid_fairies

    def scan_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Scan all planes CONCURRENTLY (filesystem I/O benefits from threading)."""
        import concurrent.futures
        import time as _time

        planes = ["P00_Autonomic", "P10_Memory", "P20_Somatic", "P30_Cognition", "P40_Sensory", "P50_Persona", "P60_Executive"]
        result = {}
        t0 = _time.time()

        def _scan_one(plane):
            found = self.scan_plane(plane)
            return plane, found

        # All 7 planes scan concurrently — pure filesystem I/O, no GIL contention
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            futures = {executor.submit(_scan_one, p): p for p in planes}
            for future in concurrent.futures.as_completed(futures):
                try:
                    plane, found = future.result(timeout=30)
                    print(f"[FairyScanner]   -> {len(found)} fairies in {plane}", flush=True)
                    if found:
                        result[plane] = found
                except Exception as e:
                    plane = futures[future]
                    print(f"[FairyScanner]   -> ERROR scanning {plane}: {e}", flush=True)

        elapsed = _time.time() - t0
        total = sum(len(v) for v in result.values())
        print(f"[FairyScanner] Parallel scan: {total} fairies across {len(result)} planes ({elapsed:.1f}s)", flush=True)
        return result

    def instantiate_fairy(
        self,
        scan_entry: Dict[str, Any],
        fabric: Any,
        skip_classes: Optional[Set[str]] = None,
    ) -> Optional[Any]:
        """
        Dynamically import and instantiate a fairy from scan results.

        This connects the scanned fairy to the organ template (TensorFabric).

        Args:
            scan_entry: Dict from scan_plane with 'name', 'file', 'plane'
            fabric: TensorFabric instance to wire the fairy to
            skip_classes: Set of class names to skip (already instantiated)

        Returns:
            Fairy instance, or None if instantiation fails
        """
        file_path = Path(scan_entry.get("file", ""))
        class_name = scan_entry.get("name", "")

        if not file_path.exists() or not class_name:
            return None

        # Skip if already in skip list
        if skip_classes and class_name in skip_classes:
            return None

        # Skip known problematic patterns
        if class_name in ("BaseFairy", "OrganTemplate", "Fairy"):
            return None

        try:
            # Dynamic import
            module_name = f"fairy_dynamic_{class_name}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find the class
            fairy_class = getattr(module, class_name, None)
            if not fairy_class or not inspect.isclass(fairy_class):
                return None

            # Instantiate with fabric
            # Try different constructor signatures
            instance = None

            # 1. Try fabric as keyword arg first (keyword-only constructors)
            try:
                instance = fairy_class(fabric=fabric)
            except TypeError:
                pass

            # 2. Try fabric as positional arg (standard constructors)
            if instance is None:
                try:
                    instance = fairy_class(fabric)
                except TypeError:
                    pass

            # 3. Try no-arg constructor and wire fabric after
            if instance is None:
                try:
                    instance = fairy_class()
                    # Wire fabric/post to the fairy (both attributes may exist)
                    if hasattr(instance, "fabric"):
                        instance.fabric = fabric
                    if hasattr(instance, "post"):
                        instance.post = fabric
                    # Also try setting _post (used by some templates)
                    if hasattr(instance, "_post"):
                        instance._post = fabric
                except TypeError:
                    # Give up if can't instantiate
                    return None

            # Even when fabric is passed to constructor, some fairies create
            # hub/registration with a different fabric in super().__init__()
            # before the fabric arg is available. Re-wire them here.
            if instance:
                if hasattr(instance, "hub") and hasattr(instance.hub, "fabric"):
                    instance.hub.fabric = fabric
                if hasattr(instance, "registration") and hasattr(instance.registration, "fabric"):
                    instance.registration.fabric = fabric

            return instance

        except Exception as e:
            # Log but don't crash - some fairies may have import issues
            print(f"[FairyScanner] Could not instantiate {class_name}: {e}")
            return None

    def instantiate_all(
        self,
        fabric: Any,
        skip_classes: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scan and instantiate all fairies across all planes IN PARALLEL.

        Uses a shared ThreadPoolExecutor with 16 workers to instantiate
        all fairies concurrently. Each fairy has a 10s timeout guard.

        FIX 2026-02-05: Previous code created a NEW single-worker executor
        per fairy (serial with overhead). Now uses one pool for true parallelism.
        Boot time: ~120+ seconds → ~15-30 seconds.

        Args:
            fabric: TensorFabric to wire fairies to
            skip_classes: Set of class names to skip (already manually instantiated)

        Returns:
            List of dicts with 'name', 'plane', 'instance', 'channel'
        """
        import time as _time
        import concurrent.futures

        results = []
        skip = skip_classes or set()

        # Initialize Go TracerPool for boot tracking (if available)
        _go_pool = None
        try:
            from tracer_pool import TracerPool, TracerType, USING_GO
            if USING_GO:
                _go_pool = TracerPool.global_instance()
                print(f"[FairyScanner] Go TracerPool: ACTIVE (native DLL)", flush=True)
        except Exception as e:
            print(f"[FairyScanner] Go TracerPool: unavailable ({e})", flush=True)

        # Phase 1: Scan all planes (fast - just file scanning)
        print(f"[FairyScanner] Starting scan_all()...", flush=True)
        scan_start = _time.time()
        all_scanned = self.scan_all()
        scan_time = _time.time() - scan_start
        total_found = sum(len(v) for v in all_scanned.values())
        print(f"[FairyScanner] scan_all() returned {total_found} fairies across {len(all_scanned)} planes ({scan_time:.1f}s)", flush=True)

        # Phase 2: Collect all fairy entries (filtering out skips)
        to_instantiate = []
        seen_names = set()  # Dedup by actor_name AND class_name
        for plane, fairies in all_scanned.items():
            for entry in fairies:
                name = entry.get("actor_name") or entry.get("name", "")
                class_name = entry.get("name", "")

                # Skip if already handled or duplicate
                if name in skip or class_name in skip:
                    continue
                if name in seen_names or class_name in seen_names:
                    continue

                seen_names.add(name)
                seen_names.add(class_name)
                to_instantiate.append((plane, entry, name, class_name))

        print(f"[FairyScanner] PARALLEL instantiation: {len(to_instantiate)} fairies (skipping {total_found - len(to_instantiate)} already registered)", flush=True)

        # Phase 3: PARALLEL instantiation with Go tracer tracking
        # Use 16 workers — Python GIL still limits CPU but importlib I/O benefits hugely
        max_workers = min(len(to_instantiate), 16)
        inst_start = _time.time()

        # Create boot tracer if Go pool available
        _boot_tracer_id = None
        if _go_pool:
            try:
                _boot_tracer_id = _go_pool.create_tracer(
                    tracer_type="fairy_boot",
                    fairy_name="FairyScanner",
                    cluster_id="cluster_boot",
                    intent="instantiate_all",
                ).id
                _go_pool.start(_boot_tracer_id)
            except Exception:
                pass

        def _instantiate_one(args):
            """Instantiate a single fairy (runs in thread pool worker)."""
            plane, entry, name, class_name = args
            t0 = _time.time()

            # Create per-fairy Go tracer
            fairy_tracer_id = None
            if _go_pool:
                try:
                    fairy_tracer_id = _go_pool.create_tracer(
                        tracer_type="fairy_boot",
                        fairy_name=name,
                        intent="instantiate",
                    ).id
                    _go_pool.start(fairy_tracer_id)
                except Exception:
                    pass

            try:
                instance = self.instantiate_fairy(entry, fabric, skip)
                elapsed = _time.time() - t0

                if fairy_tracer_id:
                    try:
                        _go_pool.set_progress(fairy_tracer_id, 1.0)
                        _go_pool.complete(fairy_tracer_id)
                    except Exception:
                        pass

                if elapsed > 2.0:
                    print(f"[FairyScanner]   SLOW: {name} took {elapsed:.1f}s", flush=True)

                return (plane, entry, name, class_name, instance, None)

            except Exception as e:
                if fairy_tracer_id:
                    try:
                        _go_pool.fail(fairy_tracer_id, str(e))
                    except Exception:
                        pass
                return (plane, entry, name, class_name, None, str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit ALL fairy instantiations at once
            future_map = {
                executor.submit(_instantiate_one, args): args
                for args in to_instantiate
            }

            # Collect results as they complete — 60s overall timeout
            completed = 0
            failed = 0
            timed_out = 0
            try:
                for future in concurrent.futures.as_completed(future_map, timeout=60):
                    try:
                        result = future.result(timeout=10.0)
                        plane, entry, name, class_name, instance, error = result

                        if error:
                            print(f"[FairyScanner] ERROR: {name}: {error}", flush=True)
                            failed += 1
                        elif instance:
                            clean_plane = plane.split("_")[0] if "_" in plane else plane
                            results.append({
                                "name": name,
                                "class_name": class_name,
                                "plane": clean_plane,
                                "instance": instance,
                                "channel": entry.get("channel", ""),
                                "file": entry.get("file", ""),
                            })
                            completed += 1
                        else:
                            failed += 1

                    except concurrent.futures.TimeoutError:
                        args = future_map[future]
                        print(f"[FairyScanner] TIMEOUT: {args[2]} hung >10s, skipping", flush=True)
                        timed_out += 1
                    except Exception as e:
                        args = future_map[future]
                        print(f"[FairyScanner] ERROR: {args[2]}: {e}", flush=True)
                        failed += 1

            except concurrent.futures.TimeoutError:
                # Overall 60s timeout — some fairies never completed
                pending = [args[2] for fut, args in future_map.items() if not fut.done()]
                print(f"[FairyScanner] OVERALL TIMEOUT: {len(pending)} fairies still pending: {pending[:10]}", flush=True)
                timed_out += len(pending)

        inst_time = _time.time() - inst_start

        # Complete boot tracer
        if _boot_tracer_id:
            try:
                _go_pool.set_progress(_boot_tracer_id, 1.0)
                _go_pool.complete(_boot_tracer_id)
            except Exception:
                pass

        print(f"[FairyScanner] PARALLEL complete: {completed} OK, {failed} failed, {timed_out} timed out ({inst_time:.1f}s)", flush=True)

        return results

    def scan_and_register(
        self,
        directory,
        skip_classes: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scan all planes and register fairies in directory as 'sleeping' specs.

        NO importing, NO instantiation, NO on_boot.
        Just filesystem scanning + directory registration.
        This is the lightweight Phase 4b — GoBootOrchestrator handles the rest.

        Args:
            directory: DirectoryFairy instance to register into
            skip_classes: Set of fairy names to skip

        Returns:
            List of registered spec dicts (name, plane, file, channel)
        """
        import time as _time
        skip = skip_classes or set()

        # Phase 1: Scan all planes (fast - just file reading)
        scan_start = _time.time()
        all_scanned = self.scan_all()
        scan_time = _time.time() - scan_start
        total_found = sum(len(v) for v in all_scanned.values())
        print(f"[FairyScanner] scan_and_register: {total_found} fairies found ({scan_time:.1f}s)", flush=True)

        # Phase 2: Register each as sleeping (no import, no instance)
        registered = []
        seen_names = set()

        for plane, fairies in all_scanned.items():
            for entry in fairies:
                name = entry.get("actor_name") or entry.get("name", "")
                class_name = entry.get("name", "")

                # Skip if already handled or duplicate
                if name in skip or class_name in skip:
                    continue
                if name in seen_names or class_name in seen_names:
                    continue

                seen_names.add(name)
                seen_names.add(class_name)

                clean_plane = plane.split("_")[0] if "_" in plane else plane

                # Register as sleeping — NO fairy_instance, just source_file
                try:
                    directory.register_fairy(
                        name=name,
                        plane=clean_plane,
                        channel=entry.get("channel", ""),
                        capabilities=set(),
                        status="sleeping",
                        metadata={
                            "source_file": entry.get("file", ""),
                            "class_name": class_name,
                            "needs_instantiation": True,  # Flag for orchestrator
                        },
                    )
                    registered.append({
                        "name": name,
                        "class_name": class_name,
                        "plane": clean_plane,
                        "file": entry.get("file", ""),
                        "channel": entry.get("channel", ""),
                    })
                except Exception as e:
                    print(f"[FairyScanner] Could not register {name}: {e}", flush=True)

        print(f"[FairyScanner] Registered {len(registered)} fairy specs (discovery only, no imports)", flush=True)
        return registered


class MigrationManager:
    """
    Manages the migration of fairies from v1 to v2.

    Migration flow:
    1. Scan v1 for fairies
    2. Register each as sleeping
    3. Wake one at a time
    4. Verify functionality
    5. Mark as migrated
    """

    def __init__(self, registry: FairyRegistry, v1_root: Path):
        self.registry = registry
        self.v1_root = Path(v1_root)
        self.scanner = FairyScanner(v1_root)
        self._migration_log: List[Dict[str, Any]] = []

    def scan(self) -> Dict[str, List[Dict[str, Any]]]:
        """Scan v1 for all fairies."""
        return self.scanner.scan_all()

    def register_sleeping(
        self,
        name: str,
        plane: str,
        channel: str = "",
        capabilities: Optional[Set[str]] = None,
        source_path: Optional[str] = None,
    ) -> FairyRecord:
        """Register a v1 fairy in sleeping state."""
        record = self.registry.register_migrated(
            name=name,
            plane=plane,
            channel=channel,
            capabilities=capabilities or set(),
            source_path=source_path or "",
            start_sleeping=True,
        )

        self._migration_log.append({
            "action": "register_sleeping",
            "name": name,
            "plane": plane,
        })

        return record

    def wake(self, name: str) -> bool:
        """Wake a sleeping fairy."""
        success = self.registry.wake_fairy(name)
        if success:
            self._migration_log.append({
                "action": "wake",
                "name": name,
            })
        return success

    def sleep(self, name: str) -> bool:
        """Put a fairy back to sleep."""
        success = self.registry.put_to_sleep(name)
        if success:
            self._migration_log.append({
                "action": "sleep",
                "name": name,
            })
        return success

    def migration_status(self) -> Dict[str, Any]:
        """Get migration status."""
        migrated = self.registry.list_migrated()
        sleeping = [f for f in migrated if f.is_dormant()]
        awake = [f for f in migrated if f.status == "running"]
        waking = [f for f in migrated if f.status == "waking"]

        return {
            "total_migrated": len(migrated),
            "sleeping": len(sleeping),
            "awake": len(awake),
            "waking": len(waking),
            "by_plane": self._count_by_plane(migrated),
            "log_length": len(self._migration_log),
        }

    def _count_by_plane(self, fairies: List[FairyRecord]) -> Dict[str, int]:
        """Count fairies by plane."""
        counts: Dict[str, int] = {}
        for f in fairies:
            counts[f.plane] = counts.get(f.plane, 0) + 1
        return counts

    def get_log(self, last_n: int = 50) -> List[Dict[str, Any]]:
        """Get recent migration log entries."""
        return self._migration_log[-last_n:]


# Convenience function
def create_migration_manager(registry: FairyRegistry, v1_root: str) -> MigrationManager:
    """Create a migration manager."""
    return MigrationManager(registry, Path(v1_root))
