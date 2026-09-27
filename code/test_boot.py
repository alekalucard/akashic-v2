"""Quick test of boot sequence"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

print('Testing TensorFabric...')
from postal_core.tensor_fabric import TensorFabric
fabric = TensorFabric()
print('TensorFabric OK')

print('Testing DirectoryFairy creation...')
from directory import DirectoryFairy, set_directory
try:
    directory = DirectoryFairy(fabric, v1_root=str(ROOT / "fairies"))
    print('DirectoryFairy created OK')
    directory.on_boot()
    print('DirectoryFairy.on_boot() OK')
    set_directory(directory)
    print('set_directory OK')
except Exception as e:
    print(f'DirectoryFairy FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Testing FairyScanner...')
try:
    from directory.migration import FairyScanner
    scanner = FairyScanner(ROOT / "fairies")
    all_fairies = []
    for plane in ["P00_Autonomic", "P10_Memory", "P20_Somatic", "P30_Cognition", "P40_Sensory", "P50_Persona"]:
        found = scanner.scan_plane(plane)
        all_fairies.extend(found)
    print(f'FairyScanner: Found {len(all_fairies)} fairies')
except Exception as e:
    print(f'FairyScanner FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\nAll basic tests passed!')
