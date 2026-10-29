# W9: activation decay in the one writer

Branch: `nous/w9-decay-in-writer`.

**Switch: `AKASHIC_DECAY_IN_WRITER`.** It is on only when the value is exactly `"1"`: `os.environ.get("AKASHIC_DECAY_IN_WRITER", "0") == "1"` (fairy.py:7818, and `writer_decay_on` in portal_gate.py). When it is unset, behaviour is the same as today.

Tags: [C] = read in code, [M] = measured here, [I] = inference.

## What I found

**Only the portal interior calls `ManifoldMemory.decay_all`.**
- The call is `decay_all(0.001)` in `_handle_tick`, at portal_interior.py:3287 [C].
- manifold_constrained_cortex_fairy.py:1122 also calls `decay_all`, but on `ManifoldGraphAdapter(acf._graph)` (:968). That is the Python dict graph, which is cleared in manifold mode [C].
- So with K2 on, nothing in her cortex fades [C/I].

**The serial cortex (A) never reaches the interior's decay.**
- In manifold mode, A's `_portal_gate` is a LocalManifoldGate (fairy.py:2191-2194) [C].
- `_start_portal_io` is called only in the portal branch (fairy.py:2319). So A's every-5-beat tick command (fairy.py:7885, :7961) is never sent [C].
- Even if it were sent, `LocalManifoldGate.send` would answer "Unknown cmd" [C].

**When the interior decays:**
- The interior decays only when it receives a "tick" through a PortalGate in this process [C].
- A tick costs 0 tokens (:701), and every request increments `_requests_processed` (:1221) [C].
- It decays when `_requests_processed % interval == 0`, where `interval = max(20, int(100/max(2,tau)))` (:3284) and tau is clamped to [2, 20] (:3274) [C].

## What I built

Three code files changed. On the switch-OFF path the change only adds code; nothing existing is altered. Line endings are LF, and the CRLF count was 0 before and after.

- **`manifold_memory.py:2531` — new `decay_keys(keys, rate)`.** It runs `decay_all`'s body over one chunk of keys [C]:
  - Same rate, same >0.01 floor, same PERSONAL/SEEDED affect exemption (:1671).
  - It looks each slot up at write time.
  - It holds the slot's shard lock while it works.
  - It writes only the 4-byte activation float (:2556), so a stale copy can never undo another thread's write to count, degree or flags.
  - `decay_all` itself is unchanged.
- **`portal_gate.py`:**
  - New `cortex_interior_alive` (:123) and `WriterDecay` (:148).
  - New `LocalManifoldGate.maybe_writer_decay` (:1431). It keeps one WriterDecay per graph and returns "unsupported" for a graph without `decay_keys`.
  - PortalGate's constructor now adds the gate to a WeakSet (:1860). This is the only line that runs with the switch OFF. It holds a weak reference and does nothing else.
- **`fairy.py:7815-7828`.** The maintenance loop calls into the gate only when the switch is "1" and the gate's graph is this fairy's own region.

**Cadence (interior requests translated to beats):**
- The host sends one tick every 5 beats. About 1 tick in `interval` lands on a multiple of the interval, so the interior decays about once per `5*interval` beats.
- The writer uses exactly that, counted in beats: 250 beats when tau <= 2, 100 beats when tau >= 5.
- I used beats rather than wall-clock time because beats are the clock that actually drives the interior.
- A simulation with random extra traffic matches the interior's rate to within 8% (test_interior_model_rate_matches_period) [M].

**Never two places at once:**
- The writer will not start while any `portal_interior.py` PortalGate in this process is open, and it re-checks between chunks.
- It also stops between chunks if the switch goes off or the manifold is closed.
- One process-wide lock lets only one writer pass run at a time.
- If the check itself raises an error, it reports the interior as alive, so the writer stays off [C][M].

## Cost of one pass [M]

Synthetic 256 MB file, 2,000,000 active nodes, measured with bench_w9_stall.py on Python 3.13 (GIL on, 4 cores).

| Pass | Time | Max chunk | Max stall seen by a concurrent `touch_node` writer |
|---|---|---|---|
| Unchunked `decay_all` (the interior's) | 4.4 s in one call, which never yields | — | 9.6-58 ms |
| Chunked, 10k keys, 10 ms pause | 5.8 s wall alone; 13 s alongside a writer | 33 ms alone; 114-141 ms alongside a writer | 17.5-21.5 ms (reviewer's rerun: about 34 ms) |

- The writer's baseline gap is 3-4 ms.
- The pass runs in its own daemon thread, so the maintenance loop never waits on it.
- The key snapshot costs 16 MB.
- With the GIL on, the scheduler already bounds the stall, so chunking mainly adds abort points.

## Tests [M]

Run with `python docs/nous/W9/run_w9_matrix.py` (20 tests).

- **Branch:** 20/20 OK.
- **origin/main's files:** the CONTROL `test_control_writer_decays_when_on` **FAILS** on an assertion, because activation stays at 0.5. The other 19 tests error.
- **Mutants:** all 10 near-misses fail, so the matrix passes.

| Mutant | Near-miss |
|---|---|
| M1 | switch default ON |
| M2 | interior check ignores tunnels |
| M3 | no re-check between chunks |
| M4 | exemption dropped |
| M5 | wrong cadence |
| M6 | floor changed |
| M7 | fairy hook not gated by the switch |
| M8 | WriterDecay per gate instead of per graph |
| M9 | whole-record write |
| M10 | no closed-manifold check |

## Could NOT verify

- **Free-threaded runtime:** her runtime is free-threaded 3.14t, and I have not measured stall or lock behaviour there.
- **Tau and beat rate:** I could not confirm her real tau or beat rate. I assumed about 1 beat per second, from the fairy.py:7914 comment. I also could not confirm whether A's `_portal_time_dilation` ever moves off 1.0 in manifold mode.
- **An interior in another process:** grep found nothing that ticks an interior other than this process's own gate [I], but I could not rule it out.
- **One-chunk overlap:** if B opens its gate during a chunk, the writer and the interior can both decay nodes for up to one chunk (at most about 140 ms) [I].
- **`GraphCortexStore`:** the store used when `AKASHIC_GRAPH_CORTEX=1` is outside this repo. The writer returns "unsupported" for it.
- **Live system:** nothing ran against her live tree or a real manifold.

## CHECK THESE 3

1. **portal_interior.py:3284-3287, fairy.py:7885 and fairy.py:7961.** Check that the interior's cadence really is one decay per `interval` ticks with one tick every 5 beats, so that 5*interval beats is the right translation.
2. **portal_gate.py:123-145 (`cortex_interior_alive`).** Check that the interior can decay only while a PortalGate in this process is open. Ticks come only from fairy.py:7961 through `_portal_io`, which starts only at fairy.py:2319.
3. **manifold_memory.py:2528-2556.** Check that writing only offset 12 (`'<IHHHHf'`) produces the same float32 that `decay_all` writes, and that no other field in the record needs refreshing.

## REVIEW

A fresh reviewer session was given only the diff and the task, and asked to refute the change. It ran two rounds; round 1 was on dd7125d/e187361.

Round 1 found no BLOCKER or MAJOR. I fixed its findings #2, #11, #13 and #16, and logged #8. Then the reviewer ran round 2 on d15ea2a.

Final verdict table, verbatim from round 2 (changed rows plus new ones):

| # | finding | severity | evidence | suggested fix |
|---|---|---|---|---|
| 1 | Tip: 20/20 tests OK. Matrix: main + M1-M10 all fail, "MATRIX: PASS" | OK | test file + run_w9_matrix [M] | - |
| 2 | My own copy of main (git archive): control now FAILS on an assertion, not an AttributeError | OK (was note) | test_control_writer_decays_when_on, my run: failures=1 [M] | - |
| 8 | First refusal logged, then every 100th; portal_id still not checked (fail-safe) | MINOR, accepted | portal_gate.py:185-187 [C] | - |
| 11 | decay_keys writes only the 4-byte activation (offset 12) under the shard lock. Same float32 and same offset as _write_node (manifold_memory.py:1628-1641). Byte test passes. Race test: an unlocked thread rewrote every node's count field while 300 decay passes ran. Only bytes 12-14 (activation) and 16-17 (the other thread's count) changed; nothing was clobbered; activation 5.0 -> 4.700 exact | FIXED | manifold_memory.py:2553-2556 [C][M] | - |
| 13 | Unsupported graph returns "unsupported", logged once. Residual: maybe_writer_decay still does `self.graph._w9_writer_decay = wd` before maybe_start. A graph that refuses setattr would print "[WriterDecay] error" on every maintenance iteration | MINOR | portal_gate.py:~1430 [C]; GraphCortexStore setattr behaviour [I] | Do the hasattr(decay_keys/_key_index) check in maybe_writer_decay before the setattr |
| 16 | Pass aborts when the manifold is closed: close() sets _mm=None (manifold_memory.py:3625). Close landing mid-chunk -> ValueError, caught in _run_pass_locked | FIXED | portal_gate.py:233; test_closed_manifold_stops_pass; M10 [C][M] | - |
| N1 | Switch OFF on the new code: writer_decay_on() is still checked first in maybe_writer_decay and maybe_start, ahead of the unsupported check and the refusal log. Nothing new runs or prints when unset | OK | portal_gate.py:165-172, ~1423 [C]; test_off_when_unset [M] | - |
| N2 | Activation-only write means a concurrent unlocked upsert can overwrite a decay (one 0.001 decay lost). It can no longer clobber other fields | OK | [I] | - |
| 15 | SUMMARY.md still missing on the tip (still referenced at portal_gate.py:95) | MINOR, open | git ls-tree [M] | Commit it; include max chunk ~114 ms / writer gap ~34 ms (GIL 3.13) and a 3.14t remeasure |

Overall verdict, verbatim: "no BLOCKER or MAJOR. Safe to merge with the switch OFF by default once SUMMARY.md lands. #13 residual is optional."

**Changes after round 2:**
- **#13 FIXED.** `maybe_writer_decay` now checks for support before the setattr. The test uses a `__slots__` store that refuses setattr, and the matrix still passes.
- **#15 FIXED.** This file is committed.

**OPEN (accepted limits):**
- **#8:** the interior check does not filter on portal_id. It fails safe: any open interior turns the writer off.
- **#7:** the interior and the writer can overlap for up to one chunk.
- **N2:** a concurrent unlocked upsert can overwrite one 0.001 decay.
- **Not remeasured:** stall numbers on free-threaded 3.14t.
