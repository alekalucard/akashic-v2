# P20_Somatic/integration/__init__.py
# Somatic Integration System - Embodiment, Circadian, and Consciousness Hierarchy

from .somatic_integration import (
    SomaticIntegration,
    get_body,
    start_body,
    feel,
    inject_emotion,
)

# Circadian Integration Helpers
from .circadian_integration import (
    get_circadian_status,
    get_tick_modulation,
    get_drive_modulation,
    get_chemistry_modulation,
    is_active_hours,
    is_rest_hours,
    record_goal_event,
    should_create_goal,
)

# Consciousness Hierarchy
from .consciousness_hierarchy import (
    HierarchyLevel,
    HIERARCHY_ROLES,
    DATA_FLOWS,
    SomaticIntegrationPacket,
    EmbodiedFeelPacket,
    get_fairy_role,
    get_upstream_fairies,
    get_downstream_fairies,
    HIERARCHY_TOPICS,
    get_somatic_subscription_topics,
    get_soul_subscription_topics,
    wire_hierarchy_subscriptions,
    describe_hierarchy,
)

__all__ = [
    # Somatic
    "SomaticIntegration",
    "get_body",
    "start_body",
    "feel",
    "inject_emotion",
    # Circadian helpers
    "get_circadian_status",
    "get_tick_modulation",
    "get_drive_modulation",
    "get_chemistry_modulation",
    "is_active_hours",
    "is_rest_hours",
    "record_goal_event",
    "should_create_goal",
    # Consciousness Hierarchy
    "HierarchyLevel",
    "HIERARCHY_ROLES",
    "DATA_FLOWS",
    "SomaticIntegrationPacket",
    "EmbodiedFeelPacket",
    "get_fairy_role",
    "get_upstream_fairies",
    "get_downstream_fairies",
    "HIERARCHY_TOPICS",
    "get_somatic_subscription_topics",
    "get_soul_subscription_topics",
    "wire_hierarchy_subscriptions",
    "describe_hierarchy",
]
