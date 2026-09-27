import sys
# ══════════════════════════════════════════════════════════════════════════════
# WORKING MEMORY BOOT PATCH
# ══════════════════════════════════════════════════════════════════════════════
#
# INSERT THIS INTO server.py BEFORE UnconsciousMindFairy boot (around line 1835)
#
# This boots the WorkingMemoryHub which is WHERE:
# - UnconsciousMindFairy operates
# - ALL fairies feed INTO (reflective loop)
# - ALL fairies pull FROM (context)
# - Autopilot/Scheduler/Embodiment coordinate
# - Pattern learning/teaching happens
#
# ══════════════════════════════════════════════════════════════════════════════

WORKING_MEMORY_BOOT_BLOCK = '''
        # ══════════════════════════════════════════════════════════════════════
        # WORKING MEMORY HUB - Central Processing Workspace
        # This is WHERE UnconsciousMindFairy operates (not separate from)
        # All fairies feed INTO and pull FROM this hub
        # ══════════════════════════════════════════════════════════════════════
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import boot_working_memory
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            
            postal = get_shared_postal_hub()
            working_memory = boot_working_memory(post=postal)
            self._working_memory_hub = working_memory
            
            sys.stderr.write(f"[boot] [BRAIN] WorkingMemoryHub ONLINE" + "\n")
            sys.stderr.write(f"       ├─ Reflective loop capacity: {working_memory.REFLECTIVE_CAPACITY}" + "\n")
            sys.stderr.write(f"       ├─ Reasoning loop capacity: {working_memory.REASONING_CAPACITY}" + "\n")
            sys.stderr.write(f"       └─ Dual loops processing, tracer-based" + "\n")
        except ImportError as e:
            sys.stderr.write(f"[boot] WorkingMemoryHub not available: {e}" + "\n")
        except Exception as e:
            sys.stderr.write(f"[boot] WorkingMemoryHub error: {e}" + "\n")
            import traceback
            traceback.print_exc()
'''

# ══════════════════════════════════════════════════════════════════════════════
# MODIFY UnconsciousMindFairy to use WorkingMemoryHub
# ══════════════════════════════════════════════════════════════════════════════

UNCONSCIOUS_HUB_WIRING = '''
        # Wire UnconsciousMindFairy to operate IN the WorkingMemoryHub
        if hasattr(self, '_working_memory_hub') and hasattr(self, '_unconscious_mind'):
            try:
                # Give UnconsciousMind reference to the hub it operates in
                self._unconscious_mind._working_memory_hub = self._working_memory_hub
                
                # Hub gets reference to the mind that processes in it
                self._working_memory_hub._unconscious_mind = self._unconscious_mind
                
                sys.stderr.write(f"[boot] [LINK] UnconsciousMindFairy ↔ WorkingMemoryHub wired" + "\n")
            except Exception as e:
                sys.stderr.write(f"[boot] Hub wiring error: {e}" + "\n")
'''

# ══════════════════════════════════════════════════════════════════════════════
# WIRE OTHER FAIRIES TO WORKING MEMORY
# ══════════════════════════════════════════════════════════════════════════════

FAIRY_HUB_WIRING = '''
        # Wire other fairies to WorkingMemoryHub
        if hasattr(self, '_working_memory_hub'):
            hub = self._working_memory_hub
            
            # Autopilot
            if hasattr(self, '_autopilot_fairy') and self._autopilot_fairy:
                try:
                    hub._autopilot = self._autopilot_fairy
                    self._autopilot_fairy._working_memory_hub = hub
                    sys.stderr.write(f"[boot] [LINK] AutopilotFairy ↔ WorkingMemoryHub wired" + "\n")
                except Exception as e:
                    sys.stderr.write(f"[boot] Autopilot→Hub wiring error: {e}" + "\n")
            
            # Goal Scheduler
            if hasattr(self, '_goal_scheduler') and self._goal_scheduler:
                try:
                    hub._scheduler = self._goal_scheduler
                    self._goal_scheduler._working_memory_hub = hub
                    sys.stderr.write(f"[boot] [LINK] GoalScheduler ↔ WorkingMemoryHub wired" + "\n")
                except Exception as e:
                    sys.stderr.write(f"[boot] Scheduler→Hub wiring error: {e}" + "\n")
            
            # Embodiment
            if hasattr(self, '_embodiment_fairy') and self._embodiment_fairy:
                try:
                    hub._embodiment = self._embodiment_fairy
                    self._embodiment_fairy._working_memory_hub = hub
                    sys.stderr.write(f"[boot] [LINK] EmbodimentFairy ↔ WorkingMemoryHub wired" + "\n")
                except Exception as e:
                    sys.stderr.write(f"[boot] Embodiment→Hub wiring error: {e}" + "\n")
            
            # ClaudeFairy (the newborn to teach)
            if hasattr(self, '_claude_fairy') and self._claude_fairy:
                try:
                    hub._claude_fairy = self._claude_fairy
                    self._claude_fairy._working_memory_hub = hub
                    sys.stderr.write(f"[boot] [LINK] ClaudeFairy ↔ WorkingMemoryHub wired (newborn + "\n")")
                except Exception as e:
                    sys.stderr.write(f"[boot] ClaudeFairy→Hub wiring error: {e}" + "\n")
            
            # Probability Oracle
            if hasattr(self, '_probability_oracle') and self._probability_oracle:
                try:
                    hub._probability_oracle = self._probability_oracle
                    sys.stderr.write(f"[boot] [LINK] ProbabilityOracle ↔ WorkingMemoryHub wired" + "\n")
                except Exception as e:
                    sys.stderr.write(f"[boot] Oracle→Hub wiring error: {e}" + "\n")
            
            # ContinuousReflectionPump - feeds INTO reflective loop
            if hasattr(self, '_reflection_pump') and self._reflection_pump:
                try:
                    self._reflection_pump._working_memory_hub = hub
                    sys.stderr.write(f"[boot] [LINK] ReflectionPump ↔ WorkingMemoryHub wired" + "\n")
                except Exception as e:
                    sys.stderr.write(f"[boot] ReflectionPump→Hub wiring error: {e}" + "\n")
'''

sys.stderr.write("Working Memory Boot Patch ready!\n")
sys.stderr.write("\n")
sys.stderr.write("INSTRUCTIONS:\n")
sys.stderr.write("1. Insert WORKING_MEMORY_BOOT_BLOCK BEFORE UnconsciousMindFairy boot (~line 1835)")
sys.stderr.write("2. Insert UNCONSCIOUS_HUB_WIRING right AFTER UnconsciousMindFairy boot (~line 1850)")
sys.stderr.write("3. Insert FAIRY_HUB_WIRING after all fairies are booted (near end of _start_somatic)")
