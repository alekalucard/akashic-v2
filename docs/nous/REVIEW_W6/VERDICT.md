# REVIEW W6: cortex capacity (branch nous/w6-cortex-capacity @ 0f49669)

Reviewer: independent; my job was to refute the work, not confirm it. I changed no code on the reviewed branch.
Tags: [C] I read it in code. [M] I measured it here on SYNTHETIC data in a temp dir. [I] inference.
Line numbers are for the reviewed branch. I opened no real *.manifold and ran no server, fairy or launcher.
I checked that `manifold_memory.py` has no side effects on import before loading it: its top level only builds two `threading.local()` and struct constants.

## VERDICT: ACCEPT WITH FIXES

| Change | Verdict | What |
|---|---|---|
| grow tool `code/tools/grow_cortex.py` | **FIX FIRST** | F1 (fail-open when /proc is blind), F2 (no re-check for in-use right before the swap), F3 (the safety checks have no tests: 6 near-miss mutants survive). It preserved data byte-for-byte and was crash-safe in every test I ran. |
| PROTECT_EGO guard `manifold_memory.py:2324-2373` | **SHIP** | OFF when unset [C][M]. Protects region EGO, tracer PERSONAL and tracer SEEDED. When every candidate is protected it deletes nothing and returns -1 [M]. Eviction scan is about 18% slower with it ON [M]. Protection is best-effort (CHECK 3 confirmed). |
| Format report (SUMMARY.md) | **SHIP, correct 2 points** | Layout, offsets, sidecar tag and the N-blind freshness checks are all correct [C]. It leaves out the GPU/RAM cost that grows with N (F5), and ".embeddings auto-extends on a read-write open" is imprecise: it extends lazily on first embedding use (:3651). |
| Claim that the expand_manifold scripts corrupt data | **SHIP (confirmed)** | The index mix-up at [12]/[13] and the `flags & 0x2` test are real [C][M]. Nuance: DELETED records are copied but not resurrected, and the v2 script's own verify refuses to swap whenever a FROZEN node exists [M]. |

### Fixes, ranked (file:line)
1. **F1 MEDIUM, `grow_cortex.py:158-159, :213-214, :408`: a blind /proc counts as "detected".** A pid whose fd/maps it cannot read only adds a *note*. The "proc" method still counts, so the `--assume-down` gate (:408) never fires. [M] I forced `_proc_scan` to return `([], 42)` with psutil absent: `applied=True`, notes = "42 processes could not be inspected". If her server runs as another user, or under hidepid, the tool proceeds on Linux. **Fix:** if `blind > 0`, do not count "proc" as a method (or refuse outright). This only matters on Linux; her live machine is Windows.
2. **F2 MEDIUM, `grow_cortex.py:403` vs `:466`: the in-use scan runs once, before the copy, and is never repeated before the swap.** `recheck_source` (:444) compares only size, mtime and inode, so a process that opens and mmaps the file after the scan, without writing yet, passes. [M] P3: a holder that mmaps the file at step `read_old` → `applied=True`. Its mapping now points at the backup inode, so its later writes go to the backup and are lost [I]. On Windows `os.replace` would most likely fail instead, because her `open()` does not grant FILE_SHARE_DELETE [I]. **Fix:** call `in_use_report(path, quiet_s=0)` again right after `recheck_source`, and refuse on any hit.
3. **F3 MEDIUM (tests), `test_w6_cortex_capacity.py`: these safety checks have no test.** Six of my near-miss mutants SURVIVE the suite [M] (table below): `verify()` disabled (R2), `recheck_source` removed (R6), the lock without `O_EXCL` (R13), the `--assume-down` gate removed (R18), tmp fsync removed (R1; a test cannot catch it without simulating power loss), and the /proc *maps* branch removed (R10). R10 survives because CPython's mmap keeps a dup'd fd. [M]: after `f.close()` the holder still shows fd 4 open on the file, so the fd scan always catches the test's holder and the maps branch is never exercised. **Fix:** add a test that corrupts the temp and expects `GrowRefused("verification FAILED")` (my probe P2 shows the real verify does refuse [M]), a test that mutates the source between copy and swap, a test for a second concurrent grower, and a test where the detector is blind and `assume_down=False`.
4. **F4 LOW-MED (owner decision), `grow_cortex.py:262` keeps the string arena the same size.** New nodes after a grow get slots but NO snippet whenever the arena is full: `_try_write_string` returns (0,0) (:2055). [M] P4: a new node after the grow had `snippet=''`. Keys still spill to `.names`, so no node is lost. Comments at :766-772 and :2282 say the live arena has been full since 2026-08-11 [C], so in practice every new memory will be snippet-less [I]. SUMMARY does not say this. Document it, or plan a second, separate arena-growth step with sidecar re-tagging.
5. **F5 LOW (docs), memory that grows with capacity is not in the format report.** `portal_interior.py:1383` loads `read_all_embeddings_as_tensor("cuda")`, which is [N,384] fp16 (`manifold_memory.py:3790-3794`): 1.54 GB of VRAM (plus the same again in host RAM during the copy) at 2M, and 3.07 GB at 4M [C, arithmetic]. `gpu_spread.py:312` slices N*64 bytes of the node table into numpy. If the GPU runs out of memory, the code catches it and falls back to CPU [C :3798], so the outcome is slower, not broken [I].
6. **F6 LOW, `akashic_manifold.py:125/145`:** the region registry's `node_capacity` metadata stays at the old value after a grow. I found no reader that opens the file with it (:723 opens without capacity) [C], so the effect is cosmetic.

## Findings by attack

### 1. Tests, control and mutants (reproduced)
- `python3 -I code/tests/w6_mutants.py` [M] (48 s) gives exactly the result in test_results.txt: CONTROL FAIL 10/11, FIX PASS 11/11, M1-M7 all FAIL, "MET".
- On MAIN's files: CONTROL uses origin/main's `manifold_memory.py` with the tool absent; 10 of 11 fail. The one that passes is `test_off_by_default_matches_original`, which is a no-regression check, not a control, so that is correct. I also ran main's `manifold_memory.py` with the NEW tool [M]: only the 3 guard tests fail and all grow and crash tests pass, so the tool does not depend on the guard edit. Caveat: on main, the grow-tool controls (`test_refuses_*`, crash tests) fail only because the tool is missing ("does not exist"). That is acceptable because the tool is new, but those tests do not compare the tool's behaviour with anything.
- My near-miss mutants (`r6_mutants.py`, synthetic) [M]:

| Mutant | Result |
|---|---|
| R1 skip both fsyncs of tmp | **SURVIVES** (not testable without power loss) |
| R2 `verify()` returns [] | **SURVIVES** |
| R3 replace before verify (verify after the swap) | killed (crash tests) |
| R4 edge table written 24 B too far | killed (5 tests) |
| R5 string arena written 1 B too far | killed (5) |
| R6 `recheck_source` removed | **SURVIVES** |
| R7 companions moved AFTER replace | killed (crash tests) |
| R8 no backup made | killed (crash tests) |
| R9 in-use hits ignored | killed |
| R10 /proc maps branch removed | **SURVIVES** (fd scan covers the test's holder) |
| R11 header bytes 48..4095 zeroed | **SURVIVES**. Harmless: those bytes are region stats, rewritten on every read-write open (:927-942) [C] |
| R12 new node slots filled with 0x01 | killed (5) |
| R13 lock without O_EXCL | **SURVIVES** |
| R14 grow switch ON when unset | killed |
| R15 guard: all-protected evicts slot 0 anyway | killed |
| R16 guard: SEEDED dropped | killed |
| R17 `.names` moved aside with companions | killed (4) |
| R18 `--assume-down` gate removed | **SURVIVES** |

### 2. Byte-for-byte check and the API after a grow
- Node records, the 16 reserved bytes, the arena, edges, the `.names` sidecar (untouched; tag `offset >= edge_offset-string_offset` is unchanged because the arena size is unchanged, :2117 and :782-799), `.embeddings` (zero tail, :476-478), and `.csr`/`.keys` (moved aside and rebuilt) are all handled [C]. `verify()` re-reads every byte region from disk [C :320-341] and refuses on a corrupted temp [M P2].
- After a grow [M P4]: the file opens; every key resolves; `get_neighbors` is identical for all 1000 keys; a new upsert lands at slot 1000 with 0 deletions; `link` to it works; `_rebuild_indices()` re-run keeps every key. The shipped test also checks raw records, fields, reserved bytes and sidecar resolution [M].
- Places that assume a capacity: GPUSpread takes N from `graph._node_capacity` (portal_interior.py:1019, portal_gate.py:224, wmh_tools.py:122) [C]. `get_gpu_spread` reads N from the .csr header (gpu_spread.py:746-751), which stays consistent because the .csr is rebuilt [C]. The fallback `2000000` defaults apply only when the attribute is missing [C]. The only stale value is F6.

### 3. Crash safety
Every step was crashed by both raise and `os._exit` in the shipped suite, and all passed [M]. Step-by-step analysis [C/I]:
- Up to `fsync_tmp`: only the temp exists. On a raise, `finally` removes it (:481); on a hard kill it stays, and the next run deletes it (:417-418). The live file is untouched.
- `backup` (:450-455): a hard link to the LIVE inode. A crash between this step and the replace leaves `.pre_grow.<ts>` as an *alias* of the live file. It is not a snapshot: her later writes appear in it too [I]. This is harmless, but the name is misleading. Note it for the operator.
- `move_companions` → `replace`: the old manifold is still live, and .csr/.keys are absent or renamed `.pre_grow`. On the next open they are rebuilt with the OLD N, which is correct and costs boot time [C :846-916]. No window loses data.
- `os.replace` (:466): atomic on POSIX, so there is no instant at which neither file is live. The legacy script does have such a window (`os.rename(OLD,BAK); os.rename(NEW,OLD)`, expand_manifold_v2.py:348-349) [C]. On Windows, `os.replace` = MoveFileExW(REPLACE_EXISTING) without WRITE_THROUGH, and `_fsync_dir` is a no-op (:350). After a power loss the rename may roll back to the OLD file, which is intact [I].
- After the replace: the new file is live and verified. If the process dies before `extend_embeddings`, `_ensure_embedding_file` extends .embeddings on the first embedding use of a read-write handle (:3680-3684) [C].
- A hard kill leaves `.grow.lock` behind, and the next run refuses until someone deletes it (:395-397). That is fail-closed.

### 4. PROTECT_EGO
- Parsing: `os.environ.get("AKASHIC_PROTECT_EGO", "0") == "1"` (:2349) [C]. Unset, "0", "true" and "yes" are all OFF. With it OFF, the only change is one env lookup per eviction [C]. No new exception path: the guard is pure comparisons, and `_mlog` writes to stderr (:54-56) [C].
- What it protects: region == REGION_EGO(0), or tracer in {PERSONAL(1), SEEDED(7)} (:2333-2335) [C].
- All candidates protected: nothing is deleted, `upsert_node` returns -1 (:2271-2273), and the refusal is counted [M, shipped test plus R15 killed]. The new key is never written because eviction runs before `_write_string` [C].
- Callers given -1: `upsert_node` already returned -1 before this change (garbage guard :2193/:2212, arena+sidecar failure :2296), so -1 is an existing contract [C]. The callers I checked guard the value: vision_ground.py:2806/2820, self_facts.py:225, AssociationCortexFairy fairy.py:10849, Organ_Template_0_3_0.py:5068 (`>= 0`). Slot-indexed APIs bounds-check `slot < 0` (:1762, :3708, :3749) [C]. Most of the other 29 assigning callers are offline `scripts/seed_*` [C]. I did not audit every one of them.
- Cost: on a full 20k-slot synthetic cortex, 15.0 ms per scan OFF vs 17.7 ms ON (+18%) [M]. Linear extrapolation gives about 1.5 s → 1.8 s per eviction at 2M [I]. The guard does not change how often eviction runs. When it refuses, each refused upsert still costs one full scan, the same scan an eviction would have cost [C].
- Second copies: there is one `manifold_memory.py` in the tree, one `_evict_coldest_node`, and one call site (:2271) [C]. No P00..P60 duplicate exists.

### 5. Claim about the expand_manifold scripts: CONFIRMED
- Field indices: NODE_STRUCT `<IHHHHfIHfHBBIIHII16x` has [11]=region, [12]=tracer, [13]=snip_off, [14]=snip_len (manifold_memory.py:246-264) [C]. expand_manifold_v2.py:188-189 reads the snippet with `(f[12], f[13])`, and :268-269 writes the snippet offset into f[12] and the length into f[13] [C]. scripts/expand_manifold.py:182 and :208-209 do the same [C].
- `flags & 0x2` (expand_manifold_v2.py:180): FLAG_DELETED=1, FLAG_FROZEN=2 (manifold_memory.py:446-448), so it skips FROZEN and keeps DELETED [C].
- [M] (synthetic, 1000 nodes, slot 7 marked DELETED) in the `.expanded` output: tracer_id wrong on 885 nodes, snippet wrong on 88/90, frozen `who_i_am` missing. The DELETED record is copied but not resurrected, because `_rebuild_indices` frees it (:794). The script's own verify then refused to swap, so the live file was untouched. Any cortex with a FROZEN node is therefore protected from this script by its own verify. One without a FROZEN node would be swapped and corrupted [I]. NODE.pack with `16x` zeroes the reserved affect bytes (expand_manifold_v2.py:55) [C].

### 6. Windows in-use refusal (her live machine). NOT RUN; reasoning only
- Her process: `ManifoldMemory` keeps `self._file = open(...)` alive next to the mmap (manifold_memory.py:643-645) [C], so a CRT file handle with FILE_SHARE_READ|FILE_SHARE_WRITE is open the whole time [I]. A new `CreateFileW(GENERIC_READ, share=0)` conflicts with that existing read/write access and fails with ERROR_SHARING_VIOLATION (32) [I]. CPython's Windows mmap also DuplicateHandle()s the file handle, so even a Python mapper that closed its file object still holds one [I; the Linux analogue is [M]: a dup'd fd persists after close].
- Not covered: a NATIVE mapper that closes every file handle and keeps only the section. Share access is released at handle cleanup, so the share-0 open may SUCCEED [I]. The backstop is that `os.replace` onto a user-mapped file then fails with access denied or sharing violation [I]. Order of events in that case: backup link made, companions moved aside, replace raises, `finally` removes the temp. The live file is intact, and it is not a GrowRefused, so the user sees a traceback.
- Any CreateFileW failure, whatever the error code (AV scanner, permissions), is counted as a hit, so the check fails CLOSED (:179-181) [C]. If ctypes itself raises, the exception propagates out of `grow` and `main` (main catches only GrowRefused); the lock is still removed by `finally`, nothing is written, and the tool exits with a traceback [C]. On Windows "win-exclusive-open" is always a counted method, so `--assume-down` is never needed there [C].
- psutil: there is no requirements file in the mirror, but 44 modules import psutil [C], so it is probably in her venv [I]. Its scan matches only `server.py` in a cmdline, and AccessDenied is swallowed (:200) [C]. It is supplementary.
- Quiet window: on Windows, dirty mmap pages do not update mtime until a flush or close, so the 1.5 s check is weak there [I]. It is supplementary, not relied on.
- Lock file: it only stops two growers at once (and R13 shows that is untested). It does not stop her from booting mid-grow. On Windows her boot mid-grow makes `os.replace` fail (fail-safe) [I]. On Linux it does not (F2) [M].
- Could not verify: anything on Windows, NTFS rename atomicity, Defender holding the fresh temp open (it would make `os.replace` fail transiently, fail-safe) [I].

## The 3 claims in SUMMARY's "CHECK THESE 3", re-checked
1. expand_manifold index mix-up: **confirmed** [C][M] (section 5). Whether her live cortex came from these scripts: not verifiable here (no live tree).
2. `.csr` freshness ignores N: **confirmed**. manifold_memory.py:852 compares only `_ch[2] == len(_active_edges)`, :907 only the key count, and gpu_spread.py:245 uses `size=(self.N, self.N)` [C]. M1 is killed [M].
3. Region and tracer are mutable on a touch: **confirmed**. :2234-2235 overwrites the region with any non-SEMANTIC value. :2246-2248 overwrites the tracer when the new tracer has priority >= the existing one: ACE(12) and NOUS(10) beat PERSONAL(10)/SEEDED(9) (:209-216) [C]. So PROTECT_EGO can miss a self-node that has been relabelled.

## What I could not verify
Her live files: size, arena fill, how many nodes are ego, and whether her tracers are already scrambled. Any Windows behaviour (section 6). Real power loss. Eviction cost at 2M (extrapolated from 20k). The other ~20 `upsert_node` callers that assign the return value (mostly offline seed scripts).

## CHECK THESE 3
1. `grow_cortex.py:403` vs `:466`: no in-use re-scan right before `os.replace`. Add `in_use_report(path, 0)` after `recheck_source` (F2, measured on Linux).
2. `grow_cortex.py:213-214, :408`: a blind /proc counts as detection; it should refuse (F1, measured). Also add tests for verify-refusal, source-changed, concurrent lock and the assume-down gate (F3: 6 surviving mutants).
3. `grow_cortex.py:262` with `manifold_memory.py:2055`: after a grow, new nodes get no snippet while the arena is full (F4, measured). Decide this before growing her live cortex. Also budget about 3 GB of VRAM for the [N,384] semantic tensor at 4M (portal_interior.py:1383).

Reproduction scripts (not committed; synthetic only): `r6_mutants.py`, `r6_probe.py`, `r6_legacy.py` in the reviewer scratchpad.
