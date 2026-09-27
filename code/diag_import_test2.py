"""Diagnostic: Import SomaticMindFairy AFTER initializing server subsystems."""
import sys
import time
import os
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "fairies"))
sys.path.insert(0, os.path.join(ROOT, "postal_core", "python"))
sys.path.insert(0, ROOT)
os.environ["AKASHIC_ROOT"] = ROOT

print("=" * 60, flush=True)
print("IMPORT DIAGNOSTIC - WITH SERVER CONTEXT", flush=True)
print("=" * 60, flush=True)

# Step 1: Clear pycache (like server does)
print("[1] Clearing pycache...", flush=True)
import shutil
from pathlib import Path
for pycache in Path(ROOT).rglob("__pycache__"):
    try:
        shutil.rmtree(pycache)
    except Exception:
        pass
print("    Done", flush=True)

# Step 2: Initialize TensorFabric (like server does)
print("[2] Setting up TensorFabric...", flush=True)
t0 = time.time()
try:
    from P00_Autonomic.nervous_system import set_shared_fabric
    from P00_Autonomic.nervous_system.tensor_memory_fabric import TensorMemoryFabric
    fabric = TensorMemoryFabric()
    set_shared_fabric(fabric)
    print(f"    TensorFabric OK ({time.time()-t0:.2f}s)", flush=True)
except Exception as e:
    fabric = None
    print(f"    TensorFabric FAILED: {e}", flush=True)

# Step 3: SpellPool
print("[3] Setting up SpellPool...", flush=True)
t0 = time.time()
try:
    from P00_Autonomic.nervous_system.spellwork.spell_pool import SpellPool
    pool = SpellPool.ignite(n_workers=4, hz=4.0)
    print(f"    SpellPool OK ({time.time()-t0:.2f}s)", flush=True)
except Exception as e:
    print(f"    SpellPool FAILED: {e}", flush=True)

# Step 4: GPU TensorMemory
print("[4] Setting up GPU tensor memory...", flush=True)
t0 = time.time()
try:
    from P00_Autonomic.nervous_system.hardware.gpu_tensor_memory import GPUTensorMemoryFabric
    gpu_fab = GPUTensorMemoryFabric()
    from P00_Autonomic.nervous_system.tensor_memory_fabric import TensorMemoryFabric as TF
    TF._global_singleton = gpu_fab
    set_shared_fabric(gpu_fab)
    fabric = gpu_fab
    print(f"    GPU Fabric OK ({time.time()-t0:.2f}s)", flush=True)
except Exception as e:
    print(f"    GPU Fabric FAILED (using CPU): {e}", flush=True)

# Step 5: DirectoryFairy
print("[5] Setting up DirectoryFairy...", flush=True)
t0 = time.time()
try:
    from directory import DirectoryFairy, set_directory
    directory = DirectoryFairy(fabric)
    set_directory(directory)
    print(f"    DirectoryFairy OK ({time.time()-t0:.2f}s)", flush=True)
except Exception as e:
    print(f"    DirectoryFairy FAILED: {e}", flush=True)

# Step 6: ConsciousnessLoop
print("[6] Setting up ConsciousnessLoop...", flush=True)
t0 = time.time()
try:
    from consciousness import ConsciousnessLoop, CollisionChamber
    loop = ConsciousnessLoop(fabric)
    chamber = CollisionChamber(fabric)
    loop.wire_chamber(chamber)

    # Wire somatic, cognition, persona, etc (like server does)
    loop.wire_to_somatic()
    loop.wire_to_cognition()
    loop.wire_to_persona()
    loop.wire_to_dream_seeds()
    print(f"    ConsciousnessLoop OK ({time.time()-t0:.2f}s)", flush=True)
except Exception as e:
    import traceback
    print(f"    ConsciousnessLoop FAILED: {e}", flush=True)
    traceback.print_exc()

# Step 7: MotorCortex (starts a background thread!)
print("[7] Setting up MotorCortex...", flush=True)
t0 = time.time()
try:
    from fairies.P50_Persona.motor.motor_cortex_fairy import get_motor_cortex, start_motor_cortex
    motor = get_motor_cortex()
    if motor.wire_to_postal(fabric):
        motor.start()
        print(f"    MotorCortex OK - THREAD STARTED ({time.time()-t0:.2f}s)", flush=True)
    else:
        print(f"    MotorCortex wired but not started ({time.time()-t0:.2f}s)", flush=True)
except Exception as e:
    print(f"    MotorCortex FAILED: {e}", flush=True)

# Step 8: Wiring more consciousness connections (like server does)
print("[8] Wiring sensory/motor/Mobius...", flush=True)
t0 = time.time()
try:
    loop.wire_to_sensory()
    loop.wire_to_motor_feedback()
    loop.wire_to_mobius()
    print(f"    All wired OK ({time.time()-t0:.2f}s)", flush=True)
except Exception as e:
    print(f"    Wiring FAILED: {e}", flush=True)

# Now the critical test: import SomaticMindFairy
print("\n" + "=" * 60, flush=True)
print("CRITICAL: Importing SomaticMindFairy (this is where server hangs)", flush=True)
print("=" * 60, flush=True)

# Use a watchdog thread to detect hang
hang_detected = threading.Event()
def watchdog():
    if not hang_detected.wait(30):
        print("\n!!! WATCHDOG: Import has been running for 30 seconds - HANG DETECTED !!!", flush=True)
        # Print all thread stacks
        import traceback as tb
        for thread_id, frame in sys._current_frames().items():
            name = "unknown"
            for t in threading.enumerate():
                if t.ident == thread_id:
                    name = t.name
                    break
            print(f"\n--- Thread {name} (id={thread_id}) ---", flush=True)
            tb.print_stack(frame)

wdog = threading.Thread(target=watchdog, daemon=True)
wdog.start()

t0 = time.time()
print("  Importing...", flush=True)
try:
    from fairies.P20_Somatic.SomaticMindFairy import (
        SomaticMindFairy,
        set_somatic_mind,
        BootOrchestrator,
    )
    hang_detected.set()
    dt = time.time() - t0
    print(f"  SomaticMindFairy imported OK ({dt:.2f}s)", flush=True)
except Exception as e:
    hang_detected.set()
    dt = time.time() - t0
    print(f"  SomaticMindFairy FAILED ({dt:.2f}s): {e}", flush=True)
    import traceback
    traceback.print_exc()

print("\n=== DIAGNOSTIC COMPLETE ===", flush=True)
