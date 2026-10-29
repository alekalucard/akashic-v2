# W1 SUMMARY: writers on her cortex manifold

Full map: `docs/nous/W1/WRITER_MAP.md`. Map only: nothing under `code/` was changed, so there is no switch.
Tags: [C] read in code, [M] measured here, [I] inference.

**Verdict: more than one writer on her launcher, unless the K2 file is ON.** Whether it is ON can't be seen from this mirror.

* **W-A**, main process: `SYSTEM.manifold.graph("cortex", write=True)` (`server.py:6421` → `akashic_manifold.py:723`) [C].
  Instance A writes through it from its maintenance, TARDIS and tick threads, plus every `get_gate()` caller while A's
  LocalManifoldGate is the registered gate.
* **W-B**, the `portal_interior` subprocess: `ManifoldMemory(path)` read-write (`portal_interior.py:1046`), on the **same**
  `state/akashic/cortex.manifold` (`fairy.py:2272-2276`) [C]. It is spawned by instance B.
* **W-B′**: the previous boot's interior keeps its handle for up to 90 s (`portal_interior.py:4795`) [C].

**Why two cortexes [C].** A is built by the serial block (`server.py:6348`). B is built by the wake cascade
(`wake_cascade.py:114` → `server.py:5938`). Only A gets a region (`server.py:6424`), so B takes the portal branch
(`fairy.py:2264-2292`).

**Resonance tick [C].** `affect_coupling` and `paradox_residue` are written directly into W-A, by A only
(`fairy.py:7504-7570`). B's tick writes neither field. It sends spread and bind to the interior (`fairy.py:7601-7628`),
which writes activation, nodes and edges into W-B.

**Probe [M]** (`probe_two_writers.py`, synthetic 1,000-slot manifold):

| run | keys minted twice |
|---|---|
| 1 writer | 0 |
| 2 writers, no shared keys | 0 |
| 2 writers sharing 20 of 180 keys | 20 (all 20 orphaned on reopen) |

Cause: each handle keeps a private `_key_index` (`manifold_memory.py:531`, `:2216`, `:2318`).
CONTROL/MUTANT rule: not applicable, since nothing was built. The probe's two controls play that role.

**Gates.**
* Known values: `AKASHIC_COMA=1` (gates both `on_boot`s). `AKASHIC_SHADOW_DEFER` and `AKASHIC_SHARED_SHADOW_SCAN` have no effect on writer paths.
* Unknown: `AKASHIC_WAKE`, `AKASHIC_WAKE_PLANES`, `AKASHIC_SLEEP`, `AKASHIC_GRAPH_CORTEX`, `AKASHIC_NOUS_TEST`,
  `state/k2_serial_owned.json`. The repo's `boot_sour.bat:36` wakes AssociationCortexFairy.

**Smallest change to one writer:** create `state/k2_serial_owned.json` with `{"on": true}` (already built, no code
change). For a durable guarantee, a later step would add an O_EXCL writer lock file on RW opens (described only).

**Could not verify:**
* the live env values and whether the K2 file exists;
* the gate-registration order at runtime;
* Windows cross-process behaviour (the probe was one process on Linux);
* whether GoBoot can wake a comatose cortex a second time (`boot_orchestrator.py:1003-1010`, not traced to the end);
* that the `from server import SYSTEM` cortex writers (`sourpatches_farm.py:1339`, `AkashicInferenceFairy/fairy.py:1212`)
  really get a fresh `SYSTEM` with `manifold=None` under `python server.py` [I].

## CHECK THESE 3

1. B never gets a region, so it spawns a read-write interior on the same file. `_akashic_cortex_region` is assigned
   only at `server.py:6377` and `:6424`. Then follow `fairy.py:2171-2172` → `:2264-2292` → `portal_interior.py:1046`.
2. The resonance tick's affect writes are A-only: `fairy.py:7504-7505` (`if _am:`) guards `:7567-7570`. B goes to
   `:7601-7628` (portal spread and bind).
3. The `from server import SYSTEM` writers are dead: `boot_sour.bat:63` runs `server.py` as `__main__`, and
   `server.py:1868` defaults `manifold = None`. Compare the repo's own note at `plane_battery.py:1036-1041`.
