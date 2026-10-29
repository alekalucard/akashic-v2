# REVIEW W2: return to sender (`nous/w2-return-to-sender` @ 811c5b9 vs `origin/main` @ 189625f)

Reviewer brief: refute, not confirm. Tags: [C] read in code, [M] measured here by a run, [I] inference.
Nothing of hers was run (no server, no fairy, no boot). Python tests construct in-process `PostalCore` objects, which start
worker/farm threads in the test process only. The module top level is stdlib imports and constants: no threads, sockets or files.
No code on the reviewed branch was changed.

## VERDICT: ACCEPT WITH FIXES

| change | decision | what |
|---|---|---|
| Python return to sender (`_python_fallback.py:713-800, 824-827, 1159-1162, 1220-1248`) | **FIX FIRST** | (1) Restore CRLF line endings: the file went from CRLF to LF, a 1586-line rewrite. (2) Check `_sender` before `source` (`:741`). (3) Add the missing switch-parsing and delivery-order tests (F4, F5). |
| Python prefix-any-depth (`_python_fallback.py:827, 1101-1105`) | **SHIP** (it lives in the same file, so it waits for the CRLF fix) | Correct and tested both ways. A mutant is caught. |
| Rust ReturnOffice + hook (`return_office.rs`, `topic_bus.rs:46-70, 152-164, 260-297`) | **FIX FIRST** | (1) Add a test that `TopicBusConfig::default()` is OFF when the env var is unset, `" 1"` or `"true"`. The ON-when-unset mutant passes every Rust test today. (2) Same sender precedence (`return_office.rs:64`). No deadlock was found. |
| pyo3 getter `returns()` (`lib.rs:191-199`) | **SHIP** | It only adds a getter. It compiles. Not exercised from Python (no maturin). |
| Tests and bench (`tests_nous/*`, Rust `w2_*`) | **SHIP + extend** | The matrix reproduces. Three of my own mutants pass the suite (F4, F5). |
| `docs/nous/W2/SUMMARY.md` | **FIX** | The Rust cost claim is low on this machine (F7). The CRLF rewrite is not mentioned. |

## Findings, by severity

**F1 (HIGH, merge hygiene). CRLF to LF rewrite of `_python_fallback.py`.** [M]
* `origin/main` holds the file with CRLF on all 1586 lines. The branch file has 0 CR. `git diff --stat` shows 1721+/1586-.
* `git diff --ignore-cr-at-eol` shows 136+/1-. The only removed line is `from collections import defaultdict` (now `, deque`), plus `import os`.
* **No hidden change.** Every hunk is a W2 hunk: `_python_fallback.py:11,16,713-800,824-827,1101-1105,1159-1162,1220-1248`. [M]
* The other changed files were already LF on main (`topic_bus.rs`, `lib.rs`: 0 CR). Only this file flipped. [M]
* Why it matters for her:
  * There is no `.gitattributes` and no `core.autocrlf`. [M]
  * `sync_code.py:3-6,525,540` is a one-way byte copy (`shutil.copy2`, size+mtime compare) from her tree `F:\...\akashic_v2` into `code/`. [C]
  * Her live file is therefore CRLF. Porting this branch verbatim turns her whole file into a rewrite, which breaks blame in her tree.
  * The next mirror sync then flips the file back to CRLF, and every later diff is all noise. [I]
  * Python runs with either line ending, so runtime is not affected. [I]
* **Minimal correction:**
  * Convert this one file back to CRLF, for example `python -c "p='…/_python_fallback.py'; b=open(p,'rb').read(); open(p,'wb').write(b.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))"`.
  * I measured the result: `diff` against main gives exactly 136 added and 1 removed lines.
  * Do NOT add a `.gitattributes`. The mirror must stay byte-exact to her tree, and renormalizing would rewrite about 1174 CRLF files (`git ls-files --eol`: 1174 crlf, 254 lf, 3 mixed). [M]

**F2 (MEDIUM). The wrong sender wins when a payload uses `source` as a label.** [C]+[M]
* Both routers try `payload["source"]` before `payload["_sender"]` (`_python_fallback.py:741`, `return_office.rs:64`).
* `source` is often a label, not a fairy name:
  * `brainstem_reflex_fairy.py:1603` publishes `{"source": "brainstem_withdrawal"}`.
  * `FairyPostalWrapper` adds `_sender` with `setdefault` (`shared_postal_hub.py:246-248`).
  * `TensorFabric.publish` adds `source` only if it is absent (`tensor_fabric.py:1275-1276`), so the caller's label wins.
* Measured: `{"source":"brainstem_withdrawal","_sender":"BrainstemReflexFairy"}` was returned to `postal.returned.brainstem_withdrawal`. [M]
* About 1478 `"source":` payload keys exist in `code/`. [M]
* Fix: check `_sender` first. It is always a sender, because the wrapper injects it.

**F3 (MEDIUM). Rust: the switch default is untested.** [M]
* The Rust tests set `cfg.return_to_sender` by hand (`topic_bus.rs:541,622`). None of them reads the environment.
* My mutant `env_flag` -> `v != "0"` / `unwrap_or(true)` (ON when unset) passed every Rust test (26 pass, plus the same 2 old failures).
* The code itself is correct [C] `topic_bus.rs:46-48`. A test I added in a scratch copy shows default OFF for unset, `""`, `"0"`, `" 1"`, `"true"` and `"TRUE"`, and ON only for `"1"`. [M]
* The owner requires mutant-proof switch tests, so add one.

**F4 (LOW). Python: switch parsing is untested.** [M]
* My mutant that also accepts `"true"` and `" 1"` passes all 12 Python tests.
* The code is correct [C] `_python_fallback.py:826-827`. Measured: only `"1"` turns either switch on. `""`, `" 1"`, `"1 "`, `"true"`, `"TRUE"`, `"yes"` and `"on"` are all OFF. [M]
* The switch is read once at construction: setting it after `PostalCore()` has no effect. [M]

**F5 (LOW). "Byte-identical" does not cover delivery order or `topic_stats()`.** [M]
* `run_scenario` sorts the deliveries (`test_w2_return_to_sender.py:99`). My mutant that reverses `subs` before fan-out passes.
* By reading the code, the OFF path is identical [C]:
  * `_return_office is None`.
  * `_prefix_any_depth` is False.
  * The only new statement on the publish path is the `if` at `:1160`.
  * `metrics()` and `topic_stats()` are unchanged (`:1339-1386`).
* So the claim is true in code. The test simply does not prove order.

**F6 (LOW-MEDIUM). Only a per-intent rate bound, with no global cap.** [M]
* 10 000 unique unwanted intents produced 10 002 re-published returns in about one second.
* The window table is bounded by clearing it once it holds more than 4096 entries (`_python_fallback.py:779`, `return_office.rs:119`). Clearing it mid-second also resets intents that were already at their limit. [C]
* The floor requirement is met: rate 0 is clamped to 1, and returns still flow (Python and Rust tests, rerun). [M]
* Risk [I]: per-recipient intents such as `fairy.heartbeat.routed.<Name>` with no subscriber return every letter (4 Hz is below the rate of 10). Each return costs one extra publish.
* Nothing subscribes to `postal.returned.*` today ([M] grep), so every delivered return is a wasted publish plus a `return_undeliverable` ring entry.
* Suggestion: a global per-second cap, with its own floor.

**F7 (LOW). The Rust cost claim is understated here.** [M]
* SUMMARY claims about +120-160 ns.
* I measured OFF 206-236 ns and ON 526-532 ns per no-subscriber publish (3 release runs), which is about +300 ns. Different machine.
* Per undeliverable letter: 2-3 `String` allocations under ReturnOffice mutexes, plus a deep `serde_json::Value` clone of the payload when a return is sent (`return_office.rs:93-101,118-121,155-161`). None of it runs under a pool lock or DashMap guard. [C]
* Python matches the claim: no subscriber OFF 5.96/6.24 µs, ON 7.09/6.88 µs. Subscribed 37.8-39.0 µs either way (noise). [M]

**F8 (LOW). Smaller inconsistencies.** [C]/[M]
* **Ring time units differ.** The Python ring `t` is in float seconds (`_python_fallback.py:766`). The Rust ring `t` is in ms (`return_office.rs:100`).
* **Env parsing differs.** For `AKASHIC_RETURN_RATE=" 7"`, Python gives 7 and Rust falls back to 10, because `str::parse` does not trim. [M]
* **`_returned` can be spoofed.** A normal payload with `"_returned": True` is treated as a dead return: counted `return_undeliverable`, not returned (`_python_fallback.py:1223-1224`, `return_office.rs:77`). [M]
* **The dead-return ring entry has an empty sender.** The return payload uses the key `sender`, not `source`/`_sender`. [M]
* **The Python return carries `letter` by reference, not as a copy** (`:1239`). `_BaseTopicPostal` already copies (`tensor_fabric.py:339`). [C]

**Checked and NOT a problem**
* **Rust deadlock or re-entrancy.** The DashMap read guard `entry` (`topic_bus.rs:261`) ends with its `if let` block at `:276`. The return hook at `:280-287` runs after it.
  * The re-entrant `publish_routed("postal", …)` may `ensure_topic` → `insert` with no guard held.
  * The nested call stops at once, because `process` returns `None` for a return.
  * ReturnOffice mutexes (parking_lot, not re-entrant) are never held across a publish. `note` releases the ring lock before taking the counter lock. `may_send` releases the window lock before taking the counter lock. Only `snapshot` nests (counters → ring), and nothing takes them in the opposite order. So there is no lock-order inversion. [C]
  * Measured: publishing into pool `postal` itself, plus `publish()` and `publish_priority()`, all return correctly. [M]
* **Other Rust entry points.** `publish()` (`:234`), `publish_priority()` (`:301`), the global `publish()` and pyo3 `publish` (`lib.rs:174-177, 254`) all go through `publish_routed`. [C]
* **Python entry points.**
  * PoolRouter fast path (`:1050-1054, 1631-1660`): it returns only if `dispatched > 0`. Otherwise it falls through to the hook. [C]
  * `_BaseTopicPostal.publish` (fallback mode, `tensor_fabric.py:372-424`): it bypasses `PostalCore.publish` only when bridge-local handlers matched, which means the letter was delivered. With no match it calls `core.publish(intent)` (`:382`), and the hook applies. [C]
* **Recursion.** At most one nested publish. Even with the guard removed (matrix M2), a return has no `source`/`_sender`, so it is not returned again. [C]+[M]
* **Exceptions.** The hook raises nothing new. Non-dict payloads (list, str) and a non-str `source` all end in counted `no_sender`. Bad `AKASHIC_RETURN_RATE`/`RING` values fall back to the default. Negative values and 0 are clamped to 1. [M]
* **Thread safety.** The ring, window and counters sit under `threading.Lock` / parking_lot. The ring is a `deque(maxlen)` or a `VecDeque` with `pop_front`. [C]
* **Second copies of the code.** None. There is a single `_python_fallback.py`, `topic_bus.rs` and `tensor_fabric.py` in `code/`. The duplicated `shared_postal_hub.py` (P00 vs fairies/P00) is not touched by W2. [M]

## Tests reproduced

| run | claimed | mine |
|---|---|---|
| `run_w2_matrix.py`: CONTROL (main's file) | fails 10/12 | **fails 10/12** [M] |
| FIX | 12/12 | **12/12** [M] |
| M1-M5 | each fails | **each fails** (2, 1, 1, 1, 1 failures) [M] |
| Tests that PASS on main | n/a | `test_off_misses_deep_prefix` (an OFF regression guard, which should pass) and `test_off_matches_original`, which is **blind on main by construction** (it compares main with main). It only bites against OFF-path mutants: my R2 (fix the double 2-level delivery) is caught. [M] |
| My extra Python mutants | n/a | R1 reverse order: **passes (blind)**. R2 OFF path change: caught. R3 prefix ON when unset: caught. R4 switch accepts "true"/" 1": **passes (blind)**. R5 `_sender` before `source`: **passes (blind)**. R6 rate table unbounded: **passes (blind)**. [M] |
| `cargo check` | passes, 8 warnings | passes, 8 warnings. Main also has 8. [M] |
| `cargo test` | 26 pass, 2 pre-existing fail | **26 pass, 2 fail, 1 ignored**. On main's `lib.rs`/`topic_bus.rs` (without return_office): 19 pass and the same 2 fail (`test_topic_extraction`, `test_topic_bus_basic`). [M] |
| Rust control | W2 tests do not compile on main | True: the API is absent. My Rust mutant "drop the `return` after the hook" is caught (2 W2 tests). Mutant "ON when unset" is **not caught** (F3). [M] |
| Python bench | 5.6/6.6 µs, 37.9/38.9 µs | 5.96/7.09 and 6.24/6.88 µs; 38.5/37.8 and 37.8/39.0 µs [M] |
| Rust release bench `w2_cost` | 268-436 / 408-431 ns | 236/529, 206/526, 229/532 ns [M] |

## Could not verify

* Building the pyo3 extension and calling `returns()` from Python. There is no maturin. The getter compiles under `cargo check`.
* Which router her live build loads (Rust or the fallback), and her real traffic, so whether rate 10 per intent is safe (F6).
* Her live file's line endings directly. I inferred CRLF from the byte-copy mirror (F1).

## CHECK THESE 3

1. **The SUMMARY's three claims (each checked).**
   * (a) Guard dropped before the return publish: **TRUE**. `topic_bus.rs:261-276` scope, hook at `:280-287`. [C]+[M]
   * (b) Switch OFF adds only one `if`: **TRUE**. `_python_fallback.py:1160`, plus a `_prefix_any_depth` check at `:1103` in the lookup. The byte-identical test is blind to order (F5). [C]+[M]
   * (c) Sender keys: **TRUE but incomplete**. `tensor_fabric.py:1275-1276`, `shared_postal_hub.py:246-248`. Precedence is wrong (F2).
2. Restore CRLF on `_python_fallback.py` before anything is ported to her tree (F1).
3. Add a Rust env-default test and the Python `" 1"`/`"true"` OFF tests (F3, F4). Make `_sender` beat `source` (F2).
