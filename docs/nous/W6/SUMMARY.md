# W6: grow her cortex instead of deleting from it

## Fix round after REVIEW_W6

Tags: [C] code, [M] measured here (synthetic, temp dir), [I] inference. Lines are for this commit. PROTECT_EGO unchanged (reviewer: SHIP).

**What changed (code/tools/grow_cortex.py only; the tool stays OFF unless AKASHIC_CORTEX_GROW=1, so the new refusals need no extra switch)**
- F1 fail CLOSED: `detection_gate` (:262-275) refuses when any process could not be inspected. `blind` is counted at :166, and a pid that exited mid-scan no longer counts. A /proc mounted hidepid=2/4, which hides other users' pids, also counts when not root (:170-184, :240-243). The message gives the count and says --assume-down is ONLY for when she is KNOWN down. The gate runs at the first scan (:479) and again before the swap (:412).
- F2 pre-swap re-check: `final_check` (:404-418) runs IMMEDIATELY before `os.replace` (:539 vs :552): full SHA-256 of the source vs one taken before the copy (:484), a second in-use scan (quiet 0) with the same fail-closed gate, then (size, mtime, inode). Any hit: companions put back, backup hard-link removed (:540-549), temp deleted by `finally`, live file untouched. FULL hash, not sampled: her writes are scattered single records a sample would miss, and the tool already reads the whole file twice. Cost [M]: sha256 ran at 378 MB/s here, so about 2 s per read of a ~740 MB 2M-slot file, two extra reads. The directory is also fsynced before the swap (:537), not only after.
- F3 tests: 11 new tests in `TestSafetyChecks` (test_w6_cortex_capacity.py:324-538), plus a first-scan assertion at :233-234. The runner w6_mutants.py now holds M1-M7, the reviewer's R1-R18 (R7 and R18 re-anchored with the same semantics) and 7 near-misses of this fix (N1-N7), run 4 at a time.

**Results [M]** (`python3 -I code/tests/w6_mutants.py`, about 70 s; full output in test_results.txt)

| Run | Result |
|---|---|
| CONTROL: origin/main, tool absent (legacy expand_manifold_v2) | FAIL 21/22 |
| CONTROL-B: pre-fix grow_cortex.py @ 0f49669 | FAIL 5/22 (blind /proc, hidepid, same-mtime content change, late mmap holder, fsync order) |
| FIX | PASS 22/22 (the 21-test version also passed 3 times in a row) |
| M1-M7, R1-R18, N1-N7 (32 mutants) | all FAIL, **0 survive** |

R1 (fsync) is killed by monkeypatching os.fsync/os.replace and checking that the temp, with its header, and the directory are fsynced before the swap. That checks the order of calls, not durability. R9 had become redundant, because the pre-swap rescan also caught the holder; it is killed by asserting the refusal comes at the first scan, before any copy. R11 (harmless per the reviewer) is killed by a raw header-tail test.

**Format report corrections**
- .embeddings is NOT extended at open. `_ensure_embedding_file` is lazy, "called on first use" (manifold_memory.py:3651). It extends on the first embedding use of a read-write handle (:3680-3684) [C].
- VRAM: `portal_interior.py:1383` loads `read_all_embeddings_as_tensor("cuda")`, an [N,384] fp16 tensor (manifold_memory.py:3790-3795): N*768 B = 1.536 GB at 2M and 3.072 GB at 4M (1.43 / 2.86 GiB) [C + arithmetic, M]. During the load, host RAM briefly holds about twice that: a bytes slice (:3791) plus `.copy()` (:3794), so about 6.1 GB at 4M [C, I]. If CUDA runs out of memory it falls back to CPU (:3798): slower, not broken [I].

**OPEN DESIGN DECISION for the owner: the string arena is NOT grown.** The grow keeps the arena the same size (grow_cortex.py:306). The code says her live arena is full: names have spilled to the `.names` sidecar since 2026-08-11 (manifold_memory.py:2279-2283, and the 98.84% measurement at :766-772) [C]. So after a grow, every new node gets a slot but NO snippet, because `_try_write_string` returns (0,0) (:2055, :2082). [M] here: the new node landed at slot 1000 with snippet='' and its name in the sidecar. The name is kept. Options:
1. Accept it. Snippets for new nodes are lost; keys still spill to .names.
2. A separate offline arena-growth step: move the edges, then re-tag every sidecar offset (the tag is `offset >= arena size`, manifold_memory.py:799, :2143), with its own verify and mutants.
3. Give snippets a sidecar the same way names have one (a runtime change in manifold_memory.py, behind a switch).
4. Compact the arena offline (drop dead strings) to win space back, without growing it.

**Could not verify:** anything on Windows (share-mode open, MoveFileExW, Defender). Real power loss. Her live files (arena fill, sizes, how many processes would be blind on her box). A window of microseconds remains between the final stat and `os.replace`; on POSIX that window cannot be closed without a lock she would honour.

**CHECK THESE 3**
1. grow_cortex.py:539-549: the refusal path after `final_check` puts the companions back only when the original path is absent, and removes the backup only when it is a hard link to the live inode. Is that the right undo if she rebuilt .csr in between?
2. grow_cortex.py:166 and :170-184: a pid counts as blind only if BOTH fd and maps are unreadable, and hidepid counts only from the mount options. A process in ANOTHER pid namespace (a container) is invisible even to root and is not flagged [I]. Run the tool in her namespace, as her user or as root.
3. grow_cortex.py:306 with manifold_memory.py:2055: snippets after a grow (open decision above). Decide before growing her live cortex, and budget about 3.1 GB of VRAM at 4M.

---

## Original W6 report (before the review)

Tags: [C] read in code, [M] measured here (synthetic data only), [I] inference. manifold_memory.py line numbers are for this branch. My insert moved the original :2324 evict def to :2337.

**Format** [C] v2 file layout is `HEADER 4096 | NODES cap*64 | STRING arena | EDGES ecap*24` (manifold_memory.py:245, :292, :604-631). The capacity lives in the header (node_capacity u32, edge_capacity u32). string_offset is 4096+cap*64, so growing the node table means moving the string and edge tables. Key and snippet offsets are relative to string_offset. The .names sidecar tag is `offset >= edge_offset-string_offset` (:2114, :799). Edges store slot ids. .csr and .keys encode N=node_capacity, and their freshness check compares only edge or key counts, never N (:852, :907). .embeddings is 768 B/slot and extends lazily on first embedding use of a read-write handle (:3651, :3680), not at open (corrected in the fix round). GPUSpread builds an (N,N) tensor from graph._node_capacity (gpu_spread.py:245, portal_interior.py:1019), so a stale .csr after a grow would not match. **Bytes per million nodes:** 64 B x 1,000,000 = 64,000,000 B in the manifold. Companions add 768 MB (.embeddings), 4 MB (.csr offsets) and 8 MB (.keys) per million.

**Existing tools, all UNSAFE** (none checks whether the file is open via /proc or a handle):
- scripts/expand_manifold_v2.py:188-189 and :268 read the snippet with the tracer_id as its offset, then write the snippet offset into tracer_id. :180 `flags & 0x2` drops FROZEN nodes and keeps DELETED ones. It renumbers slots, zeroes the reserved affect bytes, and between :348 and :349 no live file exists. [M] on synthetic data: tracer_id wrong on 886/1000 nodes and snippet wrong on 89 of the 90 that have one; the frozen node `who_i_am` dropped (its own verify then refused); reserved bytes zeroed.
- scripts/expand_manifold.py:182 and :208 have the same index bug, and it reads every name inline (the sidecar is ignored).
- tools/expand_manifold.py:133 unpacks a 7-field edge into 5, so it crashes before writing. It would also lose every v2 field (:176).
- [I] The live 2M cortex was probably produced by one of the two scripts (both target 2M/20M). If so, her live tracer_ids may be garbage.

**Built**
- `code/tools/grow_cortex.py`: an offline tool that grows the cortex without renumbering slots. It copies node records byte-for-byte to the same slots, keeps the string arena byte-for-byte at the same size (so no sidecar re-tagging), and copies the edge records byte-for-byte. It writes a temp file, fsyncs it and verifies it by re-reading. Then it hard-links a backup, moves .csr/.keys aside so they rebuild, does an atomic os.replace, and extends .embeddings.
- It refuses to run if the file is in use: /proc fd+maps inode scan (Linux), share-mode-0 CreateFileW (Windows), a psutil check for server.py, a quiet-window check, and an O_EXCL lock. It also re-checks the source's stat before the swap.
- --apply needs `AKASHIC_CORTEX_GROW=1`. No runtime path exists. [M] synthetic 2M->4M (864 MB file) took 7.7 s and added exactly +128,000,000 B.
- `AKASHIC_PROTECT_EGO` (OFF when unset, :2349): eviction skips records where region==REGION_EGO, or tracer is PERSONAL or SEEDED (:2330-2334). If every candidate is protected, nothing is deleted and upsert_node returns -1 (:2273). The refusal is counted (_ego_refusals) and logged to stderr (:2366).
- How reliable the ego markers are: they are the code's own declared markers (REGION_EGO :431; TRACE_PERSONAL and TRACE_SEEDED :175/:181, also exempt from affect decay at :1671). But both fields can change on a touch (region :2235, tracer :2248). P20 and P50 binds put any word into EGO (:463/:466). So this is best-effort protection, not ownership.

**Tests** (code/tests/test_w6_cortex_capacity.py: 11 tests, 1000 slots, temp dir; runner code/tests/w6_mutants.py; output in test_results.txt):
- CONTROL (origin/main plus expand_manifold_v2): FAIL, 10/11.
- FIX: PASS, 11/11, including a crash at all 19 steps (raise and hard os._exit) and the refusal while another process has the file mmap'd.
- Mutants M1-M7: all FAIL (companions not moved, arena grown without re-tagging, old offsets in the header, temp file left behind, region-only guard, delete-anyway fallback, switch ON by default).

**Not verified:** anything on her live files (size, tracer histogram, how many nodes are ego). The Windows in-use path was not run (Linux sandbox). Real power loss was not tested, only a process kill. Boot time grows with capacity, because _rebuild_indices loops over node_capacity (:782).

**CHECK THESE 3**
1. scripts/expand_manifold_v2.py:188-189 and :268 (and scripts/expand_manifold.py:182/:208) mix up record index 12 (tracer_id) with 13/14 (snippet off/len). Check whether her live cortex came from these scripts: run a read-only `tracer_histogram_named()` (manifold_memory.py:3587) for out-of-range tracer ids.
2. manifold_memory.py:852: the .csr freshness check ignores N. After any capacity change the .csr must be moved aside (grow_cortex.py `DERIVED_COMPANIONS`), or GPUSpread size=(N,N) at gpu_spread.py:245 will not match.
3. manifold_memory.py:2235/:2248: region and tracer can be overwritten on a touch, so PROTECT_EGO can miss a self-node relabelled by an Ace/Nous tracer or by a non-semantic region.
