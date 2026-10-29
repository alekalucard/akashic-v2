# W1: who writes her cortex manifold (`state/akashic/cortex.manifold`)

Static read of the code-only mirror (branch `nous/w1-writer-map`, base `main` 189625f), plus one synthetic probe.
Tags: [C] read in code, [M] measured here, [I] inference. Map only; nothing in `code/` was changed.

## Verdict

**More than one writer, depending on one file switch and two env vars.** With the repo launcher's values, there are
two writers. They are two separate read-write mmap handles in two processes, plus a third handle for up to 90 s after a reboot:

| condition | writers on cortex.manifold |
|---|---|
| K2 file `state/k2_serial_owned.json` absent or not `{"on": true}` (unknown here) **and** AssociationCortexFairy awake (`boot_sour.bat:36` puts it in `AKASHIC_WAKE` [C]) **and** `AKASHIC_GRAPH_CORTEX` != `1` (unknown) | **2**: W-A (main process) + W-B (`portal_interior` subprocess) |
| K2 file ON | **1**: W-A only. The cascade copy is skipped (`infrastructure/one_cortex.py:139-158` [C]), so nobody opens a PortalGate for the cortex. |
| `AKASHIC_GRAPH_CORTEX=1`, K2 OFF | **1 on this file**: W-B only. Instance A writes the separate GraphCortexStore (`server.py:6367-6380` [C]), so her cortex is split across two stores (a different problem). |
| AssociationCortexFairy NOT in `AKASHIC_WAKE` with `AKASHIC_COMA=1` | **1 handle opened, idle**: W-A is still opened read-write at `server.py:6421` and stamps the header on open (`manifold_memory.py:926-931` [C]). Neither on_boot runs (`Organ_Template_0_3_0.py:3570-3583` [C]), so no portal and no ticks. |
| `AKASHIC_NOUS_TEST` set | **0**: the cortex is skipped (`server.py:6342`, `portal_gate.py:1763-1766` [C]). |
| Any boot that starts < 90 s after the previous one died | **+1 transient**: the old `portal_interior` keeps its RW handle until its orphan watchdog fires (`portal_interior.py:4788-4860`, timeout 90 s [C]). If the new boot opens a cortex PortalGate, it *reconnects* to that same old process instead (`portal_gate.py:1781-1795` [C]). |

So the answer is **"more than one" on her current launcher, unless the K2 file is ON**. Whether it is ON is not
visible from this mirror (`state/` is not here).

## The writer table

"Instance A" = the serial-block AssociationCortexFairy, "instance B" = the wake-cascade copy (section 2).

| # | writer (handle) | file:line where the RW handle opens | instance | process / thread(s) | what it writes | gated by |
|---|---|---|---|---|---|---|
| W-A | `SYSTEM.manifold.graph("cortex", write=True)`, cached once per AkashicManifold as key `cortex:rw` | `server.py:6421` → `infrastructure/akashic_manifold.py:715-725` → `manifold_memory.py:640-645` (`r+b`, `ACCESS_WRITE`) [C] | A (`server.py:6348`, pre-wired `:6424`, booted `:6433`) | main process. Threads: main (boot, header stamp, `.csr`/`.keys` rebuild at open, `manifold_memory.py:1029-1040`, `:1342-1352`); `AssociationCortexFairy-maintenance` (`fairy.py:4668-4673`), which runs the resonance tick (`:7806-7810`); `cortex-tardis-flush` (`:6258-6261`); `CortexTick` (`:2508-2512`); 2 unnamed deferred seed-charge threads (`:3182`, `:3224`); **every thread of any fairy that calls `get_gate()` while A's LocalManifoldGate is the registered gate** (`portal_gate.py:63-69`) [C] | nodes and edges (`upsert_node`, `link` via LocalManifoldGate `bind`/`wm_store`, `portal_gate.py:664-690`, `:1152-1176`); activation and last_access (`touch_node` on every spread, `manifold_memory.py:3491`, `:2420-2446`); affect_coupling and paradox_residue (resonance `fairy.py:7559-7570`; seed charge `:3215-3217`, `:7359-7365`; consolidation `:7213-7220`); header counters (`manifold_memory.py:657-697`) [C] | `AKASHIC_GRAPH_CORTEX` != "1" (`server.py:6367`, `:6419`); `AKASHIC_NOUS_TEST` unset (`:6342`); SYSTEM.manifold booted (`:4741`); ticks need A awake: `AKASHIC_COMA`/`AKASHIC_WAKE`/`AKASHIC_WAKE_PLANES`/`AKASHIC_SLEEP` (`Organ_Template_0_3_0.py:3440-3477`) [C] |
| W-B | `portal_interior` `self.graph = ManifoldMemory(self.manifold_path)` (readonly defaults to False) | `infrastructure/portal_interior.py:1046` (also `:1058` from_cards, `:1071` fresh create) [C] | B (`server.py:5938`, booted `:5947`) spawns it from `fairy.py:2264-2292`. Path = `<code>/state/akashic/cortex.manifold`, **the same file as W-A** (`fairy.py:2272-2276` vs `akashic_manifold.py:941-942`) [C] | **separate OS process**, detached (`portal_gate.py:1826-1850`). Spawned by B's `cortex-portal-gate` thread (`fairy.py:2360-2363`); fed by B's `cortex-portal-io` thread (`:5987-5990`) and, once B's PortalGate is the registered shared gate, by every `get_gate()` caller in the main process [C]. Interior threads: socket tunnels + `_tick_loop` (`portal_interior.py:4747`, `:4807`) [C] | `upsert_node`/`link` from bind (`:2968-3025`, `:3097-3134`); affect_coupling and paradox_residue on bind (`:3000-3006`, `:3118-3122`); `touch_node` on spread (`:1490`, `:3181`); `decay_all` over every node, every N requests (`:3283-3287`); embeddings (`:1420`); flush every 200 ticks (`:3315`) [C] | K2 file OFF (`one_cortex.py:76-93`); B awake (same coma vars); `HAS_PORTAL_GATE` import ok (`fairy.py:175-179`); `AKASHIC_NOUS_TEST` unset (`portal_gate.py:1763`); main manifold file exists, else it writes `helix_cards/portal_cortex.manifold` instead (`fairy.py:2274-2278`) [C] |
| W-B′ | the previous boot's `portal_interior`, still alive | same as W-B | none (orphan) | separate process, ≤ 90 s after its gate went silent (`portal_interior.py:4795`, `:4847-4860`) [C] | `flush`; requests if a new PortalGate reconnects to it (`portal_gate.py:1781-1795`) [C] | none; a timing window [I] |
| (dead) | `server.SYSTEM.manifold.graph("cortex", write=True)` in `sourpatches_farm.py:1339-1342` and `AkashicInferenceFairy/fairy.py:1212-1215` | none at runtime [I] | n/a | n/a | would upsert/link typed facts | Under `python server.py` (`boot_sour.bat:63`), the running module is `__main__`. `from server import SYSTEM` imports a **second** copy of server.py whose fresh `SystemState` has `manifold = None` (`server.py:1868`, `:3127`). `main()` never runs there, so both return before writing. The repo itself notes `__main__` != server (`plane_battery.py:1036-1041`) [C for the pieces, I for the conclusion]. |
| (offline) | `scripts/seed_*.py`, `retrain_*.py`, `merge_duplicate_nodes.py`, `expand_manifold*.py`, `tools/backfill_embeddings.py` | each opens RW by path [C, grep] | none | a human-run process | bulk upserts / rewrites | not gated: a writer if run while she is up [I] |

No other runtime code opens the cortex read-write. The only `ManifoldMemory(` constructions outside scripts/tools are
the two above plus read-only ones (`akashic_mcp_server.py:5711`, `:5801`; `sour_recall.py:147`;
`phasing_cortex_query.py:80`; `akashic_manifold.py:820`) [C]. The only other `graph(..., write=True)` call is on the
`episodic` and `pool` regions (`MomentBinderFairy/fairy.py:239`, `server.py:7746`) [C]. No raw `mmap.mmap` targets the
cortex (`portal_canary_engine.py:134` maps `audio.manifold` read-only) [C].
ManifoldConstrainedCortexFairy, NeuralMeshFairy and other cortex users hold no handle of their own. They write through
`get_gate()` into W-A or W-B, whichever gate registered last [C for the gate, I for "all of them"].

## 1. Why two handles on one file corrupt it (mechanism) [C + M]

* Each handle keeps a private `_key_index` (`manifold_memory.py:531`). `upsert_node` mints a new slot when the key is not
  in *its own* index (`:2216`, `:2262-2272`, `:2318`). A key learned by both writers therefore gets two records.
* The shared allocator (`:657-697`, added after the five-handle incident) adopts and republishes the header counters,
  so the two handles no longer take the same *fresh* slot. But the adopt-then-publish pair is two separate
  unlocked steps across processes, so it can still race [I]. `_free_node_slots` (`:779-797`) and
  `_evict_coldest_node` (`:2324`) are per-handle, so both writers can reuse the same freed or evicted slot [I].
* The shard locks in `touch_node` (`:2420-2446`) and the "shared map serialises 64-byte records" argument (`:1588-1600`)
  only hold inside ONE mmap object. Across W-A and W-B, every read-modify-write (touch, decay_all, upsert touch,
  affect writes) can lose an update or persist a torn record [I].
* On reopen, `_rebuild_indices` maps each key to the LAST slot holding it (`:814`), so the earlier copy stays active
  but becomes unfindable by name.

**Probe [M]** (`docs/nous/W1/probe_two_writers.py`, synthetic 1,000-slot manifold in a temp dir, `python3 docs/nous/W1/probe_two_writers.py`):

| run | records | distinct keys | keys minted twice | orphaned after reopen |
|---|---|---|---|---|
| CONTROL: 1 writer, 180 keys | 180 | 180 | 0 | 0 |
| CONTROL2: 2 writers, no key learned by both | 180 | 180 | 0 | 0 |
| CASE: 2 writers, 20 of 180 keys (1 in 9) learned by both | 200 | 180 | **20** | **20** |

The probe ran in one process with two mmaps of one file. Her machine runs two processes on Windows, which I did not test.
The duplicate rate equals the share of keys both writers learn. 1 in 9 is the overlap I chose, not a reproduction
of her boot.

## 2. Why AssociationCortexFairy is built twice [C]

* **Builder A**, the serial block on the main thread: `server.py:6328` (">>> STARTING AssociationCortex boot"),
  constructed at `:6348`, then `set_association_cortex` (`:6349`) and `SYSTEM.association_cortex` (`:6353`). The region
  is pre-wired at `:6419-6427` (only here is `_akashic_cortex_region` ever assigned, besides Path B at `:6377`), then
  booted at `:6433`.
* **Builder B**, the wake cascade: `fairies/P20_Somatic/SomaticMindFairy/wake_cascade.py:114` lists the fairy, then
  `boot.fairy.request` → `_handle_fairy_boot_request` (`server.py:5846`, wired `:6004`). Its "already alive" checks are
  `registered_fairies` (`:5877`) and the directory status (`:5892-5903`). A appends itself to `registered_fairies`
  only after its boot, so a request that lands in that window passes both checks. B is then constructed at `:5938` and
  booted at `:5947`, with no region. The repo's own diagnosis (`one_cortex.py:3-11`) says this was measured in 9 of 9
  boots [C: their comment; not re-measured here].
* B's `on_boot` takes the portal branch because `_akashic_cortex_region` is None (`fairy.py:2171-2172`, `elif` at `:2264`).
* **Both** instances run in "portal-first" stub mode, because `HAS_PORTAL_GATE` is a module-level import flag
  (`fairy.py:175-179`, `:2034-2041`). So both local ConceptGraphs are `_read_only = True`. A then switches to MANIFOLD MODE
  and registers a LocalManifoldGate (`:2173-2196`). B opens a PortalGate and registers it (`:2286-2329`).
  `register_gate` is last-wins (`portal_gate.py:63-69`), so the shared gate ends up as whichever opened later.
  B's PortalGate opens after a 1 s sleep plus the interior's manifold load, so it is probably B [I]. The K2 comment
  reports "takes over the shared gate with a PortalGate (Boot N: 11,711 requests)" [C: their comment].

## 3. The resonance tick, per instance [C]

Both instances start the maintenance thread in `on_boot` (`fairy.py:4667-4673`). It calls `_spontaneous_resonance_tick`
about every 7 beats (`:7806-7810`).

| | Instance A (region set) | Instance B (no region) |
|---|---|---|
| affect_coupling / paradox_residue | **written DIRECTLY** into W-A: `_am.write_affect_coupling` / `write_paradox_residue` at `fairy.py:7567-7570` (inside `if _am:` from `:7504-7505`); seed-charge `:7359-7365` (guarded by `_amSeed is not None`, `:7341-7342`) | **not written by the tick**: every such write is behind `_akashic_cortex_region` being set, and B's is None (`:7341`, `:7504`) |
| spread | `_am.spread_activation` → `touch_node` writes activation into W-A (`manifold_memory.py:3491`) | `self._portal_gate.spread(...)` (`fairy.py:7601-7612`) → interior `_handle_spread` → `touch_node` writes into **W-B** (`portal_interior.py:1629-1700`, `manifold_memory.py:3491`) |
| Hebbian | weight written as affect (above) | `bind` of the top-3 seeds via `_portal_io_submit` (`fairy.py:7620-7628`) → interior `upsert_node` + `link` (+ affect on bind, `portal_interior.py:2968-3006`) into **W-B** |
| route | direct mmap, no portal | through the portal single-writer process |

So the tick's `affect_coupling` and `paradox_residue` writes reach the manifold **directly from A only**. B never writes
those two fields from the tick. It does write the same file through the interior (activation via spread, nodes and
edges via bind). The interior is a *second* writer, not a single writer, because W-A is writing at the same time.

## 4. Gates and their defaults

Launcher values the owner gave: `AKASHIC_COMA=1`, `AKASHIC_SHADOW_DEFER=1`, `AKASHIC_SHARED_SHADOW_SCAN=1`. Everything
else is **unknown**. Where the repo's `boot_sour.bat` sets a value, it is shown as "repo launcher says", which may
differ from her live launcher.

| gate | read at | default when unset | effect on these paths | live value |
|---|---|---|---|---|
| `AKASHIC_COMA` | `Organ_Template_0_3_0.py:3440` | off | `=1`: non-P00 fairies skip `on_boot` unless exempted. Both cortex instances are P30 (`fairy.py:1805`) | **1** (known) |
| `AKASHIC_WAKE` | `Organ_Template_0_3_0.py:3476-3477` | empty | names exempt from coma | unknown; repo launcher says it **includes AssociationCortexFairy** (`boot_sour.bat:36`) |
| `AKASHIC_WAKE_PLANES` | `:3472-3474` | empty | whole planes exempt | unknown; repo launcher says `P20` (`boot_sour.bat:29`) |
| `AKASHIC_SLEEP` | `:3445-3446` | empty | names forced asleep | unknown; repo launcher says `DreamFairy,SleepWaveConductorFairy,HarmonicAffectBridgeFairy` (`boot_sour.bat:38`) |
| `AKASHIC_SHADOW_DEFER` | `Organ_Template_0_3_0.py:1466` | off | shadow thread only; **no effect on writer paths** | **1** (known) |
| `AKASHIC_SHARED_SHADOW_SCAN` | `Organ_Template_0_3_0.py:73` | off | shadow thread only; **no effect on writer paths** | **1** (known) |
| `AKASHIC_GRAPH_CORTEX` (+ `_PATH`, `_STORE`) | `server.py:6367-6376` | off | `=1`: A uses GraphCortexStore and W-A is not opened (`:6419`) | unknown |
| `AKASHIC_NOUS_TEST` | `server.py:4736`, `:6342`; `portal_gate.py:1763` | off | set: no cortex at all, no portal | unknown |
| `AKASHIC_CPU_CARTOGRAPHER` | `fairy.py:8031` | off | extra semantic-edge writes, W-A only | unknown |
| `AKASHIC_SEMANTIC_BACKFILL` | `fairy.py:10624` | off | backfill sweep, W-A only | unknown |
| file `state/k2_serial_owned.json` `{"on": true}` | `one_cortex.py:32-35`, `:62-93` | **OFF** when absent | ON: no instance B, so no W-B | unknown (state/ not mirrored) |
| file `state/k4_inject.json` | `portal_gate.py:82-91` | OFF | read-side GPU spread only; not a writer | unknown |
| `_PORTAL_PLANE_CONFIGS` | `server.py:6108` | hard-coded `[]` | no plane is portalised, so the cascade never defers the cortex to a portal plane | n/a |

## 5. Smallest change that would make it ONE writer (described, not built)

**Turn the existing K2 switch on:** create `state/k2_serial_owned.json` containing `{"on": true}` and reboot. No code
change. `one_cortex.cascade_should_skip` then stops builder B once A has started (`one_cortex.py:139-158`), so no
PortalGate for the cortex is opened and `portal_interior` never maps the file. That leaves W-A as the only handle: one
mmap object in one process, where the shard locks and the shared-map serialisation actually hold. The fallback is
already built: if A fails, the cascade is asked once more (`one_cortex.py:161-179`), which brings back today's two
writers but never zero.

Two things it does not cover, and the next smallest step for each:
1. **The 90 s orphan / reconnect window (W-B′).** K2 ON means nobody reconnects. But an interior left over from a
   K2-OFF boot can still flush for up to 90 s while the new W-A opens. Fix: start-up check (or a lock file, below).
2. **Anything else that might open the cortex RW later** (an offline script run while she is up; a future PortalGate).
   Durable guarantee: an exclusive writer lock in `ManifoldMemory._open_existing` for read-write opens.
   Create `<manifold>.writer.lock` with `O_CREAT|O_EXCL`, containing pid and boot id, and remove it on `close()`.
   A second read-write open would then fail loudly or fall back to `readonly=True`. Behind an OFF-when-unset switch,
   e.g. `AKASHIC_CORTEX_SINGLE_WRITER`. This is described only, not built.
