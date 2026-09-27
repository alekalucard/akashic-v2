# Akashic V2 Core
# Functions are machines. Fairies are caretakers.

from .checklist import Checklist, CheckResult, CheckStatus
from .function import Function, FunctionStatus
from .fairy import Fairy, FairyStatus
from .directory import Directory, get_directory
from .config import Config, get_config

# Unified Registry - Single source of truth for fairy registration
from .unified_registry import (
    UnifiedRegistry,
    FairyIdentity,
    SubscriptionRecord,
    BootReceipt,
    PhaseRecord,
    get_registry,
    register_fairy,
    get_subscription_map,
)

__all__ = [
    'Checklist', 'CheckResult', 'CheckStatus',
    'Function', 'FunctionStatus',
    'Fairy', 'FairyStatus',
    'Directory', 'get_directory',
    'Config', 'get_config',
    # Unified Registry exports
    'UnifiedRegistry',
    'FairyIdentity',
    'SubscriptionRecord',
    'BootReceipt',
    'PhaseRecord',
    'get_registry',
    'register_fairy',
    'get_subscription_map',
]
