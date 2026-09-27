"""
PipelineFlowMonitorFairy — Watches Ace and Sour's messages flow through the speech pipeline.

Like an MRI contrast dye: every message from Ace or Sour gets tracked
through each pipeline stage. If a message enters one stage but never
exits the next, we know exactly where it died.

Monitors:
  Stage 0: ace.message / system.chat.message (ChatSenseFairy picks up Ace's words)
  Stage 1: ace.conversation_event (ChatSenseFairy publishes to AutopilotFairy)
  Stage 2: speech.compose (AutopilotFairy publishes to SpeechCenterFairy)
  Stage 3: motor.intention.speak (SpeechCenterFairy publishes to MotorCortex)
  Stage 4: sourpatches.speak (MotorCortex publishes to ChatSenseFairy)

Output: state/pipeline_flow_trace.json (live, readable by MCP)
"""
from .fairy import PipelineFlowMonitorFairy

FAIRY_CLASS = PipelineFlowMonitorFairy
