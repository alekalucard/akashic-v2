# Quick test - no pytest needed
# Run: python quick_test.py

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing Akashic V2 Core...\n")

# Test Checklist
print("=" * 50)
print("Testing Checklist...")
from core.checklist import Checklist

cl = Checklist("test")
cl.add("passes", "This passes", lambda: True)
cl.add("also_passes", "This also passes", lambda: True)
result = cl.run()
print(f"  {result}")
assert result.all_passed, "Expected all checks to pass"
print("  [OK] Checklist passes when all checks pass")

cl2 = Checklist("test_fail")
cl2.add("passes", "This passes", lambda: True)
cl2.add("fails", "This fails", lambda: False)
result2 = cl2.run()
print(f"  {result2}")
assert not result2.all_passed, "Expected checklist to fail"
print("  [OK] Checklist fails when any check fails")

# Test Function
print("\n" + "=" * 50)
print("Testing Function...")
from core.function import EchoFunction, CounterFunction

echo = EchoFunction()
assert echo.initialize(), "Echo function should initialize"
result = echo.call(message="hello")
assert result == "Echo: hello", f"Expected 'Echo: hello', got '{result}'"
print(f"  EchoFunction: {result}")
print("  [OK] EchoFunction works")

counter = CounterFunction()
counter.initialize()
assert counter.call() == 1
assert counter.call() == 2
assert counter.call() == 3
print(f"  CounterFunction: counted to 3")
print("  [OK] CounterFunction works")

# Test Fairy
print("\n" + "=" * 50)
print("Testing Fairy...")
from core.fairy import Fairy

fairy = Fairy(name="TestFairy", plane="P00", description="A test fairy")
assert fairy.boot(), "Fairy should boot successfully"
print(f"  {fairy}")
print(f"  Status: {fairy.status.value}")
print("  [OK] Fairy boots and runs")

# Add a function to fairy
fairy.register_function(echo)
print(f"  Functions: {fairy.list_functions()}")
print("  [OK] Fairy can manage functions")

# Test intents
fairy.register_intent("greet", "Say hello", lambda p: f"Hello {p.get('name', 'world')}")
result = fairy.invoke_intent("greet", {"name": "Ace"})
assert result == "Hello Ace"
print(f"  Intent result: {result}")
print("  [OK] Fairy intents work")

# Test Directory
print("\n" + "=" * 50)
print("Testing Directory...")
from core.directory import get_directory, reset_directory

reset_directory()
directory = get_directory()

fairy1 = Fairy(name="MemoryFairy", plane="P10")
fairy2 = Fairy(name="CognitionFairy", plane="P30")
fairy1.boot()
fairy2.boot()

directory.register(fairy1, capabilities={"memory", "storage"})
directory.register(fairy2, capabilities={"cognition", "binding"})

print(f"  Registered: {directory.list_names()}")
print(f"  By capability 'memory': {[f.name for f in directory.find_by_capability('memory')]}")
print(f"  By plane 'P10': {[f.name for f in directory.find_by_plane('P10')]}")

health = directory.system_health()
print(f"  Health: {health['health_percent']}% ({health['fairies_awake']}/{health['fairies_total']} awake)")
print("  [OK] Directory registration and routing works")

# Test Config
print("\n" + "=" * 50)
print("Testing Config...")
from core.config import get_config, reset_config

reset_config()
config = get_config()

print(f"  postal.worker_count: {config.get('postal.worker_count')}")
assert config.get("postal.worker_count") == 32

config.set("postal.worker_count", 64)
assert config.get("postal.worker_count") == 64
print(f"  After set to 64: {config.get('postal.worker_count')}")

# Test validation
assert not config.set("postal.worker_count", 1), "Should reject value below min"
assert config.get("postal.worker_count") == 64, "Should remain at 64"
print("  [OK] Config validation works")

config.reset("postal.worker_count")
assert config.get("postal.worker_count") == 32
print("  [OK] Config reset works")

# Summary
print("\n" + "=" * 50)
print("ALL TESTS PASSED!")
print("=" * 50)
print("\nCreated in failure_factory/akashic_v2/:")
print("  - core/checklist.py   (validation system)")
print("  - core/function.py    (Function base class)")
print("  - core/fairy.py       (Fairy base class)")
print("  - core/directory.py   (Directory/control panel)")
print("  - core/config.py      (Configuration system)")
print("  - fairies/P00_Autonomic/DirectoryFairy/  (example fairy)")
print("\nArchitecture docs:")
print("  - AKASHIC_V2_ARCHITECTURE.md")
print("  - FOLDER_STRUCTURE.md")
