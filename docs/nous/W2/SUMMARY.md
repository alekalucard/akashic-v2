# W2 SUMMARY: return to sender (branch `nous/w2-return-to-sender`)

Tags: [C] read in code, [M] measured here, [I] inference.

## Switches (both OFF when unset, read once per router instance)

* `AKASHIC_RETURN_TO_SENDER` turns on returns.
* Its tuning knobs: `AKASHIC_RETURN_RATE` (default 10 per intent per second, floor 1) and `AKASHIC_RETURN_RING` (default 256).
* `AKASHIC_POSTAL_PREFIX_ANY_DEPTH` is separate and affects the Python fallback only.

## Built

**Both routers** (`_python_fallback.py` `_ReturnOffice` and `_return_to_sender`; Rust `src/return_office.rs` plus the hook in
`topic_bus.rs` `publish_routed`). When no subscriber wants a letter:
* It counts `messages_returned` and does NOT count it as published.
* It records (sender, intent, t, reason) in a bounded ring.
* It sends the letter back on `postal.returned.<sender>` with the original payload under `letter`.
* A return that is itself undeliverable is counted (`return_undeliverable`) and never returned again.
* Re-publishing is rate-bounded per intent. Counting and the ring are not rate-bounded.
* New getter `returns()` on the Python `PostalCore` and the pyo3 `PostalCore`. `metrics()` is unchanged.

**Python prefix switch:** with `AKASHIC_POSTAL_PREFIX_ANY_DEPTH=1`, the fallback also looks up prefixes of depth 3 to n-1. This is the
Rust rule from `topic_bus.rs:86-91`.

## How an envelope names its sender [C]

* Both `Envelope` types have a `source` field, but neither router's `publish()` takes or sets it
  (`_python_fallback.py` `publish(intent, payload, priority)`; `lib.rs` `publish(intent, payload, priority, pool)`).
* The sender only reaches the router inside the payload: `payload["source"]` (set by `TensorFabric.publish`,
  `tensor_fabric.py:1271-1272`, from `_FabricPostalBridge`, `Organ_Template_0_3_0.py:844`) or `payload["_sender"]` (set by
  `FairyPostalWrapper`, `shared_postal_hub.py:246-248`).
* The return office reads those two keys, then `Envelope.source`. With none of them, the letter is counted
  (`returns_no_sender`) and not sent anywhere.

**Proposed, not built:** nothing subscribes to `postal.returned.<name>` yet, so today every return becomes
`return_undeliverable`. That is counted, not lost. The smallest addition: one
`self.post.subscribe(f"postal.returned.{self.ACTOR_NAME}", ...)` in the organ template's `_wire_infrastructure`.
That is an Organ Template edit, so it needs Ace's permission.

## Tests [M]

**Python:** `code/postal_core/python/tests_nous/` (12 tests; matrix in `run_w2_matrix.py`).

| variant | result |
|---|---|
| CONTROL (original from origin/main) | fails 10 of 12 |
| FIX | passes 12 of 12, including switch-off byte-identical (same metrics and same deliveries as the original file on a fixed scenario) |
| M1 switch ON when unset | fails |
| M2 no return-of-return guard | fails |
| M3 prefix range includes the intent | fails |
| M4 rate floor dropped | fails |
| M5 letter also counted as published | fails |

**Rust:** `cargo check` passes (same 8 warnings as before). `cargo test`: 26 pass. The same 2 tests that already failed on untouched main
still fail (`test_topic_extraction`, `test_topic_bus_basic`, stale expectations). R1 to R3, mirrors of M5, M2 and M4, each fail the
W2 tests. On original code the W2 tests do not compile, because the return API is absent: that is the Rust control.

## Cost per publish [M]

| path | switch OFF | switch ON |
|---|---|---|
| Python, no subscriber | 5.6 µs | 6.6 µs |
| Python, subscribed | 37.9 µs | 38.9 µs (unchanged code path; noise) |
| Rust release, no subscriber | 268–436 ns | 408–431 ns (about +120–160 ns in the steadier runs) |

The subscribed path's code is unchanged.

## Found on the way [M]

The original Python fallback delivers every letter of 3+ segments TWICE to a 2-level subscriber. Sub `a.b` received
`a.b.c` twice and `a.b.c.d` twice. Cause: 2-level is added at `_python_fallback.py:989-992` and again at `:997-1001`.
Not fixed, because the switch-off path must stay byte-identical.

## Could not verify

* Building the pyo3 extension and calling `returns()` from Python (no maturin; I installed nothing).
* That her live build loads Rust, not the fallback.
* Live traffic rates, so whether 10 per second per intent is the right default.

## CHECK THESE 3

1. `src/topic_bus.rs` `publish_routed`: the return runs only after the DashMap guard is dropped. Holding it while
   `ensure_topic("postal")` takes a write lock could deadlock.
2. `_python_fallback.py` `publish`: with the switch off, the only new work is one `if not subs and self._return_office is not None`.
   The byte-identical test (`TestSwitchOffByteIdentical`) compares against the git original.
3. Sender keys: `tensor_fabric.py:1271-1272` and `shared_postal_hub.py:246-248`. Without them, returns land in `returns_no_sender`.
