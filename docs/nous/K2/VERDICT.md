# K2 (one_cortex) verdict: ON WITH CONDITIONS

Review only. No code was changed. Base: origin/main 189625f. Tags: [C] read in code, [M] measured here (synthetic data, temp dir), [I] inference.

## Verdict

**ON WITH CONDITIONS.** K2 does what it says. When the cascade's request for AssociationCortexFairy arrives after the serial block has started, the cascade copy (B) is not built (server.py:5884-5885 [C], one_cortex.py:139-158 [C/M]). With no B, nothing in the main process constructs a `PortalGate("cortex")`, so no portal_interior.py is spawned and nothing reconnects to one. The serial cortex (A) works in manifold mode (fairy.py:2172-2265 [C]), its `LocalManifoldGate` is the only `register_gate` call (fairy.py:2192 [C]; the other caller, fairy.py:2330, is on B's portal branch only), and every `get_gate()` caller lands on that gate.

The switch fails closed. A missing file, a BOM, a non-boolean, non-JSON or UTF-16 file, a non-dict body, a bad "names" field, or a directory at the path all read as OFF [M: k2_switch_floor_test.out]. Nothing in the tree writes the file [M: grep]. The switch is read once per process [C one_cortex.py:96-108; M]. The floor never produces a third cortex. It produces zero only in one narrow case, described in condition 5.

## Conditions

1. **Write the switch file exactly.** Put `{"on": true}` as UTF-8 **without a BOM** at `<her root>/state/k2_serial_owned.json`, the `state/` beside server.py (one_cortex.py:55-56 [C]). A BOM silently means OFF [M]. On Windows, PowerShell 5 `Set-Content -Encoding utf8` and some editors add a BOM [I]. Check log pattern 1 below.
2. **Start with no leftover interior.** No `portal_interior.py` process from the previous boot may be alive when she starts. Interiors are detached and live up to 90 s after the last gate contact before they flush and close the shared file (portal_gate.py:1836-1855, portal_interior.py:4795, 4847-4860 [C]). With K2 nobody reconnects to such an interior, but until it times out it is a second read-write opener of cortex.manifold. So wait at least 2 minutes after the previous server exits, or confirm the PID in state/portal_interior.pid is gone (portal_gate.py:1740-1746 [C]).
3. **Turn K4 on at the same time** (`state/k4_inject.json {"on": true}`), or accept flat spreads. Without K4, the only GPUSpread left (the LocalManifoldGate's) has `_manifold = None` (gpu_spread.py:122 [C]; the K4 comment cites :110, which is stale). Its max-affect path then uses flat weights. Today the interior's copy is injected (portal_interior.py:1021 [C]). The author's own note says K2 makes this gate the only one (portal_gate.py:76-79 [C]). This is a quality regression, not a writer-safety issue.
4. **Use the normal boot mode** (`boot_sour.bat` with no argument: AssociationCortexFairy is in AKASHIC_WAKE, boot_sour.bat:36 [C]). In `boot_sour.bat coma` mode (AKASHIC_WAKE is cleared, boot_sour.bat:54-58), A is comatose (Organ_Template_0_3_0.py:3426-3477, 3572-3583 [C]). K2 then skips B and leaves her with an inert cortex. Today B is comatose by the same gate (same ACTOR_NAME, same env, no `boot` override in fairy.py [C]), so this is **not a regression**: zero live cortexes either way. Nothing in code calls `.wake()` [M: grep], so neither copy ever wakes.
5. **Know the one floor gap (zero cortexes).** In `_floor`, the name is added to `_FALLBACK_SENT` before `publish` is called (one_cortex.py:167-177 [C]). If `fabric.publish` raises, the re-request is never sent and never retried. A has failed and B was skipped, so she has no working cortex [M: "publish raises" case]. The log line is `[K2] AssociationCortexFairy fallback re-request failed (` (one_cortex.py:226). If it appears, reboot with the file deleted. A serial build that hangs is not covered either (documented at one_cortex.py:39-40).
6. **Accept what goes quiet** (details in SUMMARY.md, section 2):
   - The interior's `decay_all(0.001)` over cortex.manifold (portal_interior.py:3287, the only caller [M]).
   - Its auto-consolidation (portal_interior.py:3294-3307).
   - Its 200-tick flush (portal_interior.py:3313-3317).
   - The battery tick loop (portal_interior.py:4965-4993).
   - The cortex tick-feedback publishes `portal.energy.surplus` / `energy.flow.tick` with source `cortex_drain_above_floor` / `cortex_overflow` (fairy.py:7927, 7937 [C]). Plane batteries lose that feed (plane_battery.py:230, hardware_regulation_fairy.py:475/492 subscribe [C]).

   Revert: delete the file and reboot (one_cortex.py:29 [C]).

## The 3 log patterns that prove one writer (first boot)

1. **The switch is ON:** `[Server] [K2] serial-owned: ON for AssociationCortexFairy` (server.py:5639, text from one_cortex.py:115-116). If it says `OFF (`, the file was not read as ON.
2. **B was skipped:** `[K2] AssociationCortexFairy owned by serial boot (started), cascade copy skipped` (one_cortex.py:153), followed by `[K2] AssociationCortexFairy serial boot done: directory record stamped running` (one_cortex.py:200). There must be **no** `[Server] [CASCADE] Booting AssociationCortexFairy` (server.py:5912). If you see `[K2] AssociationCortexFairy cascade request before serial start: not skipped (today's path)` (one_cortex.py:155) instead, K2 did nothing this boot and she still has two cortexes.
3. **One gate, no interior:** exactly one `[PortalGate] Registered shared gate: LocalManifoldGate` (portal_gate.py:71), preceded by `AssociationCortex -> AkashicManifold: PRE-WIRED` (server.py:6425). There must be **zero** `[PortalGate] Registered shared gate: PortalGate`, zero `[PortalGate] Spawning:` (portal_gate.py:1814) and zero `[PortalGate] PERSISTENT PORTAL` (portal_gate.py:1788). If `Pre-wire failed` (server.py:6428) appears, A itself takes the portal branch and spawns the interior. That is still one cortex and one interior, but the writer is the subprocess.
