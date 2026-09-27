"""Diagnostic: Which import hangs during SomaticMindFairy load?"""
import sys
import time
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "fairies"))
sys.path.insert(0, os.path.join(ROOT, "postal_core", "python"))
sys.path.insert(0, ROOT)
os.environ["AKASHIC_ROOT"] = ROOT

def timed_import(label, import_fn):
    print(f"  [{label}] importing...", end="", flush=True)
    t0 = time.time()
    try:
        result = import_fn()
        dt = time.time() - t0
        print(f" OK ({dt:.2f}s)", flush=True)
        return result
    except Exception as e:
        dt = time.time() - t0
        print(f" FAIL ({dt:.2f}s): {e}", flush=True)
        return None

print("=" * 60, flush=True)
print("IMPORT CHAIN DIAGNOSTIC", flush=True)
print("=" * 60, flush=True)

# Step 1: Organ Template
timed_import("OrganTemplate", lambda: __import__("fairies.P00_Autonomic.organ_template", fromlist=["MyFairy"]))

# Step 2: Directory
timed_import("directory", lambda: __import__("directory", fromlist=["get_directory"]))

# Step 3: Mixins
timed_import("mixins", lambda: __import__("fairies.P20_Somatic.SomaticMindFairy.mixins", fromlist=["DiagnosticMixin"]))

# Step 4: cognition (from SomaticMindFairy)
timed_import("SMF.cognition", lambda: __import__("fairies.P20_Somatic.SomaticMindFairy.cognition", fromlist=["TripleHelix"]))

# Step 5: timing
timed_import("SMF.timing", lambda: __import__("fairies.P20_Somatic.SomaticMindFairy.timing", fromlist=["CircadianClock"]))

# Step 6: inner_monologue
timed_import("SMF.inner_monologue", lambda: __import__("fairies.P20_Somatic.SomaticMindFairy.inner_monologue", fromlist=["InnerMonologue"]))

# Step 7: interest_generator
timed_import("SMF.interest_generator", lambda: __import__("fairies.P20_Somatic.SomaticMindFairy.interest_generator", fromlist=["InterestGenerator"]))

# Step 8: admin_tasks
timed_import("SMF.admin_tasks", lambda: __import__("fairies.P20_Somatic.SomaticMindFairy.admin_tasks", fromlist=["AdminTaskQueue"]))

# Step 9: thought_chains
timed_import("SMF.thought_chains", lambda: __import__("fairies.P20_Somatic.SomaticMindFairy.thought_chains", fromlist=["ThoughtChainEngine"]))

# Step 10: consciousness
timed_import("consciousness", lambda: __import__("consciousness", fromlist=["ConsciousnessLoop"]))

# Step 11: hardware
timed_import("hardware", lambda: __import__("hardware", fromlist=["HardwareFairy"]))

# Step 12: Three Gates
print("  [ThreeGates]", flush=True)
timed_import("  AutonomyFairy", lambda: __import__("fairies.P00_Autonomic.AutonomyFairy.fairy", fromlist=["AutonomyFairy"]))
timed_import("  AutopilotFairy", lambda: __import__("fairies.P00_Autonomic.AutopilotFairy.fairy", fromlist=["AutopilotFairy"]))
timed_import("  EmbodimentFairy", lambda: __import__("fairies.P00_Autonomic.EmbodimentFairy.fairy", fromlist=["EmbodimentFairy"]))

# Step 13: P30_Cognition.cognition (THIS IS THE SUSPECT)
print("  [P30_Cognition] --- THIS IS WHERE IT PROBABLY HANGS ---", flush=True)
timed_import("  P30.prompt_aware", lambda: __import__("P30_Cognition.cognition.prompt_aware_mixin", fromlist=["PromptAwareMixin"]))
timed_import("  P30.logic_fairy", lambda: __import__("P30_Cognition.cognition.logic_fairy", fromlist=["LogicFairy"]))
timed_import("  P30.irrational_logic", lambda: __import__("P30_Cognition.cognition.irrational_logic_fairy", fromlist=["IrrationalLogicFairy"]))
timed_import("  P30.paradox", lambda: __import__("P30_Cognition.cognition.paradox_cognition_fairy", fromlist=["ParadoxCognitionFairy"]))
timed_import("  P30.nous_fairy", lambda: __import__("P30_Cognition.cognition.nous_fairy", fromlist=["NousFairy"]))
timed_import("  P30.working_memory", lambda: __import__("P30_Cognition.cognition.working_memory_hub_fairy", fromlist=["WorkingMemoryHubFairy"]))
timed_import("  P30.dynamic_thinking", lambda: __import__("P30_Cognition.cognition.dynamic_thinking_orchestrator", fromlist=["DynamicThinkingOrchestrator"]))

# Step 14: SRMMemoryFairy
timed_import("SRMMemoryFairy", lambda: __import__("fairies.P10_Memory.SRMMemoryFairy.fairy", fromlist=["SRMMemoryFairy"]))

# Step 15: PersonalAI bridge
timed_import("PersonalAIBridge", lambda: __import__("fairies.P50_Persona.memory.personal_ai_bridge", fromlist=["PersonalAIMemoryBridge"]))

# Step 16: AssociationCortex
timed_import("AssociationCortex", lambda: __import__("fairies.P30_Cognition.AssociationCortexFairy.fairy", fromlist=["AssociationCortexFairy"]))

# Step 17: Ollama thinking
timed_import("OllamaThinking", lambda: __import__("fairies.P20_Somatic.SomaticMindFairy.ollama_thinking", fromlist=["OllamaThinkingEngine"]))

# Step 18: CognitionBridge
timed_import("CognitionBridge", lambda: __import__("fairies.P30_Cognition.cognition.postal_cognition_bridge", fromlist=["CognitionBridge"]))

# Step 19: The full SomaticMindFairy import
print("\n" + "=" * 60, flush=True)
print("FINAL: Full SomaticMindFairy import", flush=True)
print("=" * 60, flush=True)
timed_import("SomaticMindFairy", lambda: __import__("fairies.P20_Somatic.SomaticMindFairy", fromlist=["SomaticMindFairy"]))

print("\n=== ALL IMPORTS COMPLETE ===", flush=True)
