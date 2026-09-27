# P50_Persona/motor - Motor Output Systems
# "The bridge between wanting and doing"

from .motor_cortex_fairy import (
    MotorCortexFairy,
    ActionType,
    ActionPriority,
    ActionPlan,
    ActionResult,
    get_motor_cortex,
    start_motor_cortex,
    speak,
    notify,
)

from .speech_center_fairy import (
    SpeechCenterFairy,
    SpeechStyle,
    OutputChannel,
    SpeechAct,
    get_speech_center,
    formulate_speech,
    formulate_notification,
)

__all__ = [
    # Motor Cortex
    "MotorCortexFairy",
    "ActionType",
    "ActionPriority",
    "ActionPlan",
    "ActionResult",
    "get_motor_cortex",
    "start_motor_cortex",
    "speak",
    "notify",
    # Speech Center
    "SpeechCenterFairy",
    "SpeechStyle",
    "OutputChannel",
    "SpeechAct",
    "get_speech_center",
    "formulate_speech",
    "formulate_notification",
]
