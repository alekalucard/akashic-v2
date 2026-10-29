# W6: grow her cortex instead of deleting from it

Tags: [C] read in code, [M] measured here (synthetic data only), [I] inference. manifold_memory.py line numbers are for this branch. My insert moved the original :2324 evict def to :2337.

**Format** [C] v2 file layout is `HEADER 4096 | NODES cap*64 | STRING arena | EDGES ecap*24` (manifold_memory.py:245, :292, :604-631). The capacity lives in the header (node_capacity u32, edge_capacity u32). string_offset is 4096+cap*64, so growing the node table means moving the string and edge tables. Key and snippet offsets are relative to string_offset. The .names sidecar tag is `offset >= edge_offset-string_offset` (:2114, :799). Edges store slot ids. .csr and .keys encode N=node_capacity, and their freshness check compares only edge or key counts, never N (:852, :907). .embeddings is 768 B/slot and auto-extends on a read-write open (:3680). GPUSpread builds an (N,N) tensor from graph._node_capacity (gpu_spread.py:245, portal_interior.py:1019), so a stale .csr after a grow would not match. **Bytes per million nodes:** 64 B x 1,000,000 = 64,000,000 B in the manifold. Companions add 768 MB (.embeddings), 4 MB (.csr offsets) and 8 MB (.keys) per million.

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
