"""P30_Cognition - Cognition plane fairies.

The cognitive substrate that produces thought.
The waking mind doesn't see these directly - they produce
what BECOMES conscious thought via the Three Gates.

Key components:
- QuantumEmulatorFairy: Emotional superposition (multiple feelings at once)
- QuantumInterferenceFairy: Signal vs noise detection
- ProbabilityOracleFairy: Weighted decision guidance
- AttentionControllerFairy: Focus management, pause-to-think
- AssociationCortexFairy: Multi-modal concept binding
- PainDrives: Push-based motivation (feeds into Autonomy gate)

NOTE: All imports are LAZY to avoid circular import issues at startup.
Use the get_* functions to access fairies when needed.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# LAZY IMPORT INFRASTRUCTURE
# Avoids circular imports by deferring imports until actually needed
# ═══════════════════════════════════════════════════════════════════════════════

_cache = {}

def _lazy_import(module_path, names):
    """Lazily import names from a module, caching results."""
    cache_key = module_path
    if cache_key not in _cache:
        try:
            import importlib
            module = importlib.import_module(module_path, package=__name__)
            _cache[cache_key] = {name: getattr(module, name, None) for name in names}
            _cache[cache_key]["_available"] = True
        except ImportError:
            _cache[cache_key] = {name: None for name in names}
            _cache[cache_key]["_available"] = False
    return _cache[cache_key]


# ═══════════════════════════════════════════════════════════════════════════════
# QUANTUM EMULATOR - Emotional Superposition (LAZY)
# ═══════════════════════════════════════════════════════════════════════════════
def get_quantum_emulator_fairy():
    """Get QuantumEmulatorFairy instance (lazy import)."""
    data = _lazy_import(".QuantumEmulatorFairy", ["get_quantum_emulator_fairy"])
    fn = data.get("get_quantum_emulator_fairy")
    return fn() if fn else None

def QuantumEmulatorFairy_class():
    """Get QuantumEmulatorFairy class (lazy import)."""
    data = _lazy_import(".QuantumEmulatorFairy", ["QuantumEmulatorFairy"])
    return data.get("QuantumEmulatorFairy")


# ═══════════════════════════════════════════════════════════════════════════════
# QUANTUM INTERFERENCE - Signal vs Noise (LAZY)
# ═══════════════════════════════════════════════════════════════════════════════
def get_quantum_interference_fairy():
    """Get QuantumInterferenceFairy instance (lazy import)."""
    data = _lazy_import(".QuantumInterferenceFairy", ["get_quantum_interference_fairy"])
    fn = data.get("get_quantum_interference_fairy")
    return fn() if fn else None


# ═══════════════════════════════════════════════════════════════════════════════
# PROBABILITY ORACLE - Decision Guidance (LAZY)
# ═══════════════════════════════════════════════════════════════════════════════
def get_probability_oracle_fairy():
    """Get ProbabilityOracleFairy instance (lazy import)."""
    data = _lazy_import(".ProbabilityOracleFairy", ["get_probability_oracle_fairy"])
    fn = data.get("get_probability_oracle_fairy")
    return fn() if fn else None


# ═══════════════════════════════════════════════════════════════════════════════
# ATTENTION CONTROLLER - Focus Management (LAZY)
# ═══════════════════════════════════════════════════════════════════════════════
def get_attention_controller_fairy():
    """Get AttentionControllerFairy instance (lazy import)."""
    data = _lazy_import(".AttentionControllerFairy", ["get_attention_controller_fairy"])
    fn = data.get("get_attention_controller_fairy")
    return fn() if fn else None


# ═══════════════════════════════════════════════════════════════════════════════
# ASSOCIATION CORTEX - Multi-modal Concept Binding (LAZY)
# ═══════════════════════════════════════════════════════════════════════════════
def get_association_cortex():
    """Get AssociationCortex instance (lazy import)."""
    data = _lazy_import(".AssociationCortexFairy", ["get_association_cortex"])
    fn = data.get("get_association_cortex")
    return fn() if fn else None

def set_association_cortex(cortex):
    """Set AssociationCortex instance (lazy import)."""
    data = _lazy_import(".AssociationCortexFairy", ["set_association_cortex"])
    fn = data.get("set_association_cortex")
    if fn:
        fn(cortex)

def create_association_cortex(*args, **kwargs):
    """Create AssociationCortex (lazy import)."""
    data = _lazy_import(".AssociationCortexFairy", ["create_association_cortex"])
    fn = data.get("create_association_cortex")
    return fn(*args, **kwargs) if fn else None


# ═══════════════════════════════════════════════════════════════════════════════
# PAIN DRIVES - Push-based Motivation (LAZY)
# ═══════════════════════════════════════════════════════════════════════════════
def get_pain_drive_manager():
    """Get PainDriveManager instance (lazy import)."""
    data = _lazy_import(".pain_drives", ["get_pain_drive_manager"])
    fn = data.get("get_pain_drive_manager")
    return fn() if fn else None

def create_core_pain_drives():
    """Create core pain drives (lazy import)."""
    data = _lazy_import(".pain_drives", ["create_core_pain_drives"])
    fn = data.get("create_core_pain_drives")
    return fn() if fn else None


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION CHAIN - Motor Planning (LAZY)
# ═══════════════════════════════════════════════════════════════════════════════
def get_action_chain_fairy():
    """Get ActionChainFairy instance (lazy import)."""
    data = _lazy_import(".ActionChainFairy", ["get_action_chain_fairy"])
    fn = data.get("get_action_chain_fairy")
    return fn() if fn else None


# ═══════════════════════════════════════════════════════════════════════════════
# AVAILABILITY CHECKS (also lazy)
# ═══════════════════════════════════════════════════════════════════════════════
def is_quantum_emulator_available():
    return _lazy_import(".QuantumEmulatorFairy", []).get("_available", False)

def is_quantum_interference_available():
    return _lazy_import(".QuantumInterferenceFairy", []).get("_available", False)

def is_oracle_available():
    return _lazy_import(".ProbabilityOracleFairy", []).get("_available", False)

def is_attention_available():
    return _lazy_import(".AttentionControllerFairy", []).get("_available", False)

def is_cortex_available():
    return _lazy_import(".AssociationCortexFairy", []).get("_available", False)

def is_pain_drives_available():
    return _lazy_import(".pain_drives", []).get("_available", False)

def is_action_chain_available():
    return _lazy_import(".ActionChainFairy", []).get("_available", False)


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD __all__ - Export lazy accessor functions
# ═══════════════════════════════════════════════════════════════════════════════
__all__ = [
    # Quantum Emulator
    "get_quantum_emulator_fairy",
    "QuantumEmulatorFairy_class",
    "is_quantum_emulator_available",
    # Quantum Interference
    "get_quantum_interference_fairy",
    "is_quantum_interference_available",
    # Probability Oracle
    "get_probability_oracle_fairy",
    "is_oracle_available",
    # Attention Controller
    "get_attention_controller_fairy",
    "is_attention_available",
    # Association Cortex
    "get_association_cortex",
    "set_association_cortex",
    "create_association_cortex",
    "is_cortex_available",
    # Pain Drives
    "get_pain_drive_manager",
    "create_core_pain_drives",
    "is_pain_drives_available",
    # Action Chain
    "get_action_chain_fairy",
    "is_action_chain_available",
    # Availability helpers
    "get_available_components",
    "get_missing_components",
    # Backward compatibility - legacy HAS_* flags
    "HAS_QUANTUM_EMULATOR",
    "HAS_QUANTUM_INTERFERENCE",
    "HAS_ORACLE",
    "HAS_ATTENTION",
    "HAS_CORTEX",
    "HAS_PAIN_DRIVES",
    "HAS_ACTION_CHAIN",
    "COGNITION_COMPONENTS",
]


# ═══════════════════════════════════════════════════════════════════════════════
# AVAILABILITY SUMMARY (lazy check)
# ═══════════════════════════════════════════════════════════════════════════════
def get_available_components():
    """Get which cognition components are available (checks lazily)."""
    return {
        "quantum_emulator": is_quantum_emulator_available(),
        "quantum_interference": is_quantum_interference_available(),
        "oracle": is_oracle_available(),
        "attention": is_attention_available(),
        "cortex": is_cortex_available(),
        "pain_drives": is_pain_drives_available(),
        "action_chain": is_action_chain_available(),
    }

def get_missing_components():
    """Get which cognition components failed to load."""
    available = get_available_components()
    return {k: v for k, v in available.items() if not v}


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY - Legacy HAS_* flags and COGNITION_COMPONENTS
# NOTE: These are set to False/empty at import time to avoid circular imports.
# Use the is_*_available() functions for accurate runtime checks.
# ═══════════════════════════════════════════════════════════════════════════════
HAS_QUANTUM_EMULATOR = False  # Use is_quantum_emulator_available() instead
HAS_QUANTUM_INTERFERENCE = False  # Use is_quantum_interference_available() instead
HAS_ORACLE = False  # Use is_oracle_available() instead
HAS_ATTENTION = False  # Use is_attention_available() instead
HAS_CORTEX = False  # Use is_cortex_available() instead
HAS_PAIN_DRIVES = False  # Use is_pain_drives_available() instead
HAS_ACTION_CHAIN = False  # Use is_action_chain_available() instead

# COGNITION_COMPONENTS dict - use get_available_components() for accurate check
COGNITION_COMPONENTS = {}
