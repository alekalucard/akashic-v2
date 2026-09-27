"""
AKASHIC V2 SYSTEM MAP
=====================

A navigation tool for Claude to quickly locate components in both v1 and v2 codebases.
Run this script to print the current system map.
Import and use get_map() to get structured data.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional

# Root paths
V2_ROOT = Path(__file__).parent  # failure_factory/akashic_v2
V1_ROOT = Path(__file__).parent.parent.parent / "ebook"  # F:\Sandbox\ebook


# =============================================================================
# V2 SYSTEM MAP - What we're building
# =============================================================================

V2_MAP = {
    "root": str(V2_ROOT),
    "core_infrastructure": {
        "postal_core": {
            "path": "postal_core",
            "description": "Lock-free messaging (Rust core, Python bindings)",
            "key_files": [
                "python/postal_core/__init__.py",
                "python/postal_core/core.py",
                "python/postal_core/tensor_fabric.py",
            ],
            "exports": ["PostalCore", "Envelope", "TensorFabric", "TensorCoord"],
        },
        "tracer_pool": {
            "path": "tracer_pool",
            "description": "Universal tracers for perfect recall (Go core, Python bindings)",
            "key_files": [
                "python/tracer_pool/__init__.py",
                "python/tracer_pool/pool.py",
            ],
            "exports": ["TracerPool", "UniversalTracer", "TracerType"],
        },
        "directory": {
            "path": "directory",
            "description": "Control center for fairy registration and coordination",
            "key_files": [
                "fairy.py",
                "registry.py",
                "capability_index.py",
                "health.py",
                "migration.py",
            ],
            "exports": ["DirectoryFairy", "FairyRegistry", "FairyRecord", "MigrationManager"],
        },
        "fairy_template": {
            "path": "fairy_template",
            "description": "Base class for all v2 fairies",
            "key_files": [
                "base.py",
                "states.py",
                "mixins/tracer.py",
                "mixins/directory.py",
                "mixins/consciousness.py",
            ],
            "exports": ["Fairy", "FairyBase", "FairyState", "can_transition"],
        },
    },
    "test_files": {
        "boot_test.py": "Main boot test - runs all infrastructure tests",
    },
}


# =============================================================================
# V1 SYSTEM MAP - Where we're migrating from
# =============================================================================

V1_MAP = {
    "root": str(V1_ROOT),
    "planes": {
        "P00_Autonomic": {
            "description": "Low-level system infrastructure (heartbeat, nervous system)",
            "key_fairies": [
                {
                    "name": "ConsciousnessLoopFairy",
                    "path": "nervous_system/consciousness_loop_fairy.py",
                    "capabilities": ["consciousness.pulse", "heartbeat"],
                    "lines": "~800",
                },
                {
                    "name": "DirectoryFairy",
                    "path": "directory_fairy.py",
                    "capabilities": ["fairy.register", "fairy.lookup"],
                    "lines": "~1600",
                },
                {
                    "name": "BootFairy",
                    "path": "boot_fairy.py",
                    "capabilities": ["system.boot"],
                    "lines": "~400",
                },
                {
                    "name": "GracefulShutdownFairy",
                    "path": "nervous_system/graceful_shutdown_fairy.py",
                    "capabilities": ["system.shutdown"],
                    "lines": "~300",
                },
            ],
            "key_modules": [
                "nervous_system/",
                "postal.py",
                "hot_reload.py",
            ],
        },
        "P10_Memory": {
            "description": "Memory storage and retrieval (Akashic Records, SRM)",
            "key_fairies": [
                {
                    "name": "MemoryConsolidationFairy",
                    "path": "memory_consolidation_fairy.py",
                    "capabilities": ["memory.consolidate", "memory.archive"],
                    "lines": "~600",
                },
                {
                    "name": "BackupFairy",
                    "path": "backup_fairy.py",
                    "capabilities": ["memory.backup"],
                    "lines": "~400",
                },
            ],
            "key_modules": [
                "akashic_memory/",
                "akashic_records/",
                "SRM_Clusters/",
                "triple_helix_srm_memory/",
            ],
        },
        "P20_Somatic": {
            "description": "Embodiment and physical manifestation",
            "key_fairies": [],
            "key_modules": [],
        },
        "P30_Cognition": {
            "description": "Higher cognition, reasoning, and the unconscious mind",
            "key_fairies": [
                {
                    "name": "UnconsciousMindFairy",
                    "path": "cognition/unconscious_mind_fairy.py",
                    "capabilities": ["system.boot", "system.diagnose", "system.repair", "llm.controller"],
                    "lines": "~9500",
                    "priority": "HIGH - First fairy to migrate",
                },
                {
                    "name": "AssociationCortexFairy",
                    "path": "integration/association_cortex_fairy.py",
                    "capabilities": ["association.bind", "consciousness.collision"],
                    "lines": "~500",
                },
            ],
            "key_modules": [
                "cognition/skill_system.py",
                "cognition/pain_drives.py",
                "cognition/adaptive_regulator.py",
                "integration/",
                "reflection/",
            ],
        },
        "P40_Sensory": {
            "description": "Sensory input processing (GUI, web, audio)",
            "key_fairies": [
                {
                    "name": "SensoryCortexFairy",
                    "path": "sensory_cortex_fairy.py",
                    "capabilities": ["sensory.process"],
                    "lines": "~400",
                },
            ],
            "key_modules": [
                "gui/",
                "web/",
                "audio/",
            ],
        },
        "P50_Persona": {
            "description": "Identity and persona management",
            "key_fairies": [],
            "key_modules": [],
        },
        "P60_Executive": {
            "description": "Executive function and main application",
            "key_fairies": [],
            "key_modules": [
                "server.py",
            ],
        },
    },
    "critical_files": {
        "Organ Template": "P10_Memory/Akashic_Records_Physical/Organ_Templates/Organ_Template_0.1.0.py",
        "Skill System": "P30_Cognition/cognition/skill_system.py",
        "Pain Drives": "P30_Cognition/cognition/pain_drives.py",
        "Fairy Profile": "P00_Autonomic/fairy_profile.py",
        "Unconscious Mind": "P30_Cognition/cognition/unconscious_mind_fairy.py",
    },
}


# =============================================================================
# MIGRATION STATUS
# =============================================================================

MIGRATION_STATUS = {
    "completed": [
        "PostalCore (rebuilt from scratch)",
        "TracerPool (rebuilt from scratch)",
        "TensorFabric (new 4D tensor parallel)",
        "DirectoryFairy (control center)",
        "FairyTemplate (base class)",
        "SleepStates (plug-and-play)",
        "MigrationManager",
    ],
    "in_progress": [],
    "planned": [
        "UnconsciousMindFairy - System controller/LLM admin",
        "CharacterSheet - RPG proficiency system",
        "GUI Dashboard - User monitoring",
    ],
    "not_started": [
        "ConsciousnessLoopFairy",
        "MemoryFairies",
        "SensoryFairies",
        "All other fairies",
    ],
}


# =============================================================================
# API
# =============================================================================

def get_map() -> Dict[str, Any]:
    """Get the full system map."""
    return {
        "v2": V2_MAP,
        "v1": V1_MAP,
        "migration": MIGRATION_STATUS,
    }


def find_fairy(name: str) -> Optional[Dict[str, Any]]:
    """Find a fairy by name in either v1 or v2."""
    # Check v2
    for component in V2_MAP.get("core_infrastructure", {}).values():
        if name in str(component):
            return {"version": "v2", "component": component}

    # Check v1
    for plane_name, plane in V1_MAP.get("planes", {}).items():
        for fairy in plane.get("key_fairies", []):
            if fairy["name"] == name:
                return {
                    "version": "v1",
                    "plane": plane_name,
                    "fairy": fairy,
                    "full_path": str(V1_ROOT / plane_name / fairy["path"]),
                }

    return None


def find_by_capability(capability: str) -> List[Dict[str, Any]]:
    """Find fairies with a given capability."""
    results = []
    for plane_name, plane in V1_MAP.get("planes", {}).items():
        for fairy in plane.get("key_fairies", []):
            if capability in fairy.get("capabilities", []):
                results.append({
                    "name": fairy["name"],
                    "plane": plane_name,
                    "path": fairy["path"],
                })
    return results


def get_critical_path(name: str) -> Optional[str]:
    """Get path to a critical file."""
    path = V1_MAP.get("critical_files", {}).get(name)
    if path:
        return str(V1_ROOT / path)
    return None


def print_summary():
    """Print a readable summary."""
    print("=" * 70)
    print("  AKASHIC SYSTEM MAP")
    print("=" * 70)
    print()
    print(f"  V2 Root: {V2_ROOT}")
    print(f"  V1 Root: {V1_ROOT}")
    print()

    print("  V2 INFRASTRUCTURE (what we're building)")
    print("  " + "-" * 50)
    for name, info in V2_MAP.get("core_infrastructure", {}).items():
        print(f"    {name}: {info['description']}")
    print()

    print("  V1 PLANES (where we're migrating from)")
    print("  " + "-" * 50)
    for plane_name, plane in V1_MAP.get("planes", {}).items():
        fairy_count = len(plane.get("key_fairies", []))
        print(f"    {plane_name}: {plane['description']}")
        if fairy_count:
            print(f"      Key fairies: {fairy_count}")
            for f in plane.get("key_fairies", [])[:3]:
                priority = f" [{f['priority']}]" if "priority" in f else ""
                print(f"        - {f['name']}{priority}")
    print()

    print("  MIGRATION STATUS")
    print("  " + "-" * 50)
    print(f"    Completed: {len(MIGRATION_STATUS['completed'])} components")
    print(f"    Planned: {len(MIGRATION_STATUS['planned'])} components")
    print(f"    Not started: {len(MIGRATION_STATUS['not_started'])} components")
    print()

    print("  CRITICAL FILES (v1)")
    print("  " + "-" * 50)
    for name, path in V1_MAP.get("critical_files", {}).items():
        print(f"    {name}: {path}")
    print()


if __name__ == "__main__":
    print_summary()
