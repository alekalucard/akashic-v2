# Intent Fabric - Parallel Autonomy Layer
# Gives fairies will, desire, and emergent intent

from .fairy_intent_tracker import (
    IntentFabric,
    FairyIntent,
    SomaticState,
    ChemistrySnapshot,
    IntentType,
    WillStrength
)

from .background_agent_daemon import (
    BackgroundAgentDaemon,
    Task,
    create_sample_task
)

from .forum_awareness import (
    ForumAwareness,
    ForumPost,
    get_random_forum_prompt,
    FORUM_PROMPTS
)

__all__ = [
    # Intent Tracking
    'IntentFabric',
    'FairyIntent',
    'SomaticState',
    'ChemistrySnapshot',
    'IntentType',
    'WillStrength',

    # Background Agent
    'BackgroundAgentDaemon',
    'Task',
    'create_sample_task',

    # Forum Awareness
    'ForumAwareness',
    'ForumPost',
    'get_random_forum_prompt',
    'FORUM_PROMPTS'
]
