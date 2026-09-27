"""
Hardware Infrastructure Module
==============================

Provides hardware sensing and resource management:
- CudaFairy: GPU/CUDA detection and capabilities
- HardwareRegulationFairy: CPU/RAM sensing and tier mapping
- SystemWorkerPoolFairy: ALIVE, but it lives in the ROOT shim tree at
  P00_Autonomic/nervous_system/hardware/system_worker_pool_fairy.py -- NOT in this
  package. server.py imports it directly from there. The relative import that used to
  sit below was therefore dead (wrong directory), and removing it un-breaks this
  package for every downstream importer, including the root re-export shim.
  CORRECTED 2026-08-26: an earlier edit of mine called it 'REPLACED'. It was not.
- MemoryPressureFairy: RAM pressure monitoring and GC

Postal Channels:
  hardware.capabilities  - CPU/RAM/tier updates
  cuda.capabilities      - GPU/CUDA updates
  worker.request         - Request workers from pool
  worker.release         - Release workers back
  worker.submit          - Submit task to pool

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > inf)
"""


__all__ = [
]
