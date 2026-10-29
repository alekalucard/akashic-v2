# W14 -- no double delivery in the Python postal fallback (AKASHIC_POSTAL_NO_DOUBLE)

Branch `nous/w14-no-double` (based on `origin/nous/w2-return-to-sender`). Tags: [C] read in code, [M] measured here, [I] inference.

## Found
- The double: `PostalCore.publish` builds `subs` from the exact key (`_python_fallback.py:1102`), then the 2-level `parent`
  key when the intent has 3+ segments (`:1105-1108`, main `:995-997`), then the base key (`:1111`), then the 2-level key AGAIN
  when `two_level != intent and two_level != topic` (`:1115-1118`, main `:1003-1005`). For 3+ segments `two_level == parent`,
  and `topic` is the first segment (`:52-54`), so the second add always fires [C]. Every entry in `subs` is enqueued
  (loop at `:1193`), no dedupe [C]. Measured: sub `a.b` gets 2 copies of `a.b.c` and of `a.b.c.d` (rows R05/R06/R18) [M].
- Python mode (fairies): `_BaseTopicPostal.publish` (`tensor_fabric.py:375-387`) delivers ONLY its own exact + base-wildcard
  handlers when any exist, else calls `PostalCore.publish(intent)`; `_pool_dispatch` (`:270`) filters `== or startswith(intent+'.')`
  and does not dedupe [C]. So the double reaches fairies whenever the bridge has no exact/base match [M: bridge R05/R06/R17/R18 = 2].
- One copy only: no second copy of this lookup in `code/P00_..P60_`, `code/fairies/` or anywhere else (grep for `two_level` /
  `_subscribers.get(parent`) [M]. `pool_router.py:256` (critical topics, router attached at runtime) uses its own exact-topic
  lookup, a separate path, not touched [C].

## Built
- Switch `AKASHIC_POSTAL_NO_DOUBLE`, OFF when unset: `_python_fallback.py:843` (`os.environ.get(..., "0") == "1"`, read
  once in `__init__`). ON: the second 2-level add is skipped (`:1113-1115`). For 3+ segments the parent block already added
  that key; for 2 segments `two_level == intent` anyway, so nothing else changes [C; M: order test].
- File stays CRLF: 1739 lines / 1739 CR (was 1734/1734); diff = +6 -1 lines in that file [M].
- Parity table `code/postal_core/python/tests_nous/w14_parity_table.json` (21 rows, 28 subscriptions), read by
  `test_w14_no_double.py` (Python, 8 tests) and by the Rust test `w14_parity_table` (`topic_bus.rs:673`).
  Rust side = a REAL TopicBus measurement, not a re-implementation: `subscribe_filtered(base, .., Some(full intent))` +
  `publish_routed(base, letter)`, which are the calls `_BaseTopicPostal` makes via `lib.rs:123-147` and `:155-175` when USING_RUST.
  It counts real handler invocations and is asserted with return_to_sender off and on [M].

## Parity (measured; RETURN_TO_SENDER 0/1 changes nothing in any row). Key = PREFIX_ANY_DEPTH, NO_DOUBLE. ! = differs from Rust
| row | subs -> pub | Rust | core 00 | core 10 | core 01 | core 11 | bridge 00 | bridge 10 | bridge 01 | bridge 11 |
|---|---|---|---|---|---|---|---|---|---|---|
| R01-04, R07, R20 | exact / base-wildcard (R20: 5 segments) / 2-level exact | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| R05 | r05.b -> r05.b.c | 1 | !2 | !2 | 1 | 1 | !2 | !2 | 1 | 1 |
| R06 | r06.b -> r06.b.c.d | 1 | !2 | !2 | 1 | 1 | !2 | !2 | 1 | 1 |
| R08-10, R21 | 3/4/5-level sub -> deeper pub (R21: 6 segments) | 1 | !0 | 1 | !0 | 1 | !0 | 1 | !0 | 1 |
| R11-13 | no match (r11.b vs r11.bb.c; deeper sub; sibling) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| R14 | r14+r14.b+r14.b.c -> r14.b.c.d | 1,1,1 | !1,2,0 | !1,2,1 | !1,1,0 | 1,1,1 | !1,0,0 | !1,0,0 | !1,0,0 | !1,0,0 |
| R15 | r15.b+r15.b.c -> r15.b.c | 1,1 | !2,1 | !2,1 | 1,1 | 1,1 | !0,1 | !0,1 | !0,1 | !0,1 |
| R16 | r16+r16.b -> r16.b.c | 1,1 | !1,2 | !1,2 | 1,1 | 1,1 | !1,0 | !1,0 | !1,0 | !1,0 |
| R17 | r17.b+r17.b -> r17.b.c | 1,1 | !2,2 | !2,2 | 1,1 | 1,1 | !2,2 | !2,2 | 1,1 | 1,1 |
| R18 | consciousness.collision -> ...coordinate | 1 | !2 | !2 | 1 | 1 | !2 | !2 | 1 | 1 |
| R19 | r19.b.c+r19.b.c.d -> r19.b.c.d | 1,1 | !0,1 | 1,1 | !0,1 | 1,1 | !0,1 | !0,1 | !0,1 | !0,1 |

- core (PostalCore used directly) with PAD=1 + ND=1 equals Rust on all 21 rows [M].
- Not modelled: the pool_router fast path for CRITICAL_VOLUME topics (`_python_fallback.py:1066-1069`, `pool_router.py:256`, exact-topic lookup, attached at runtime) -- a separate gap from Rust; it does not double [C].
- STILL DIFFERS (bridge, every switch combo): R14, R15, R16, R19. Why: `_BaseTopicPostal.publish` (`tensor_fabric.py:375-387`)
  short-circuits. If the bridge has ANY exact-intent or base-wildcard handler for the letter, it delivers to those only and
  never asks PostalCore, so prefix subscribers (`r14.b`, `r15.b`, `r16.b`, `r19.b.c`) get 0 where Rust gives 1 [C, M].
  Not fixed here: it is outside W14 and would need its own switch in tensor_fabric.py. OPEN.

## Tests (all [M], run here)
- `run_w14_matrix.py`: CONTROL base (w2) FAIL (6 failing), CONTROL origin/main FAIL (7), FIX PASS (8/8),
  M1 ON-when-unset FAIL (5), M2 drops the first add instead [order] FAIL (1), M3 only 4+ segments FAIL (5),
  M4 accepts ' 1'/'true' FAIL (1), M5 block removed when OFF FAIL (4), M6 condition inverted FAIL (6),
  and after REVIEW: M7 ON drops base subs at 5+ segments FAIL (3), M8 new line with LF FAIL (1),
  M9 extra metrics key OFF FAIL (1), M10 prefix-any-depth stops at depth 4 FAIL (4).
- `run_w2_matrix.py` (with this file): CONTROL FAIL, FIX PASS 21/21 (incl. byte-identical-when-off and fan-out order vs
  origin/main), all 12 W2 mutants FAIL.
- `cargo test --lib`: 31 pass, 2 fail, and those 2 are the pre-existing ones (envelope::test_topic_extraction,
  topic_bus::test_topic_bus_basic). `w14_parity_table` passes. Rust mutants: `wants()` exact-only FAILS at R02;
  `starts_with(f)` without the '.' FAILS at R11.

## Could NOT verify
- Her live tree, logs or real subscriber set: how many real fairies sit on a 2-level key with 3+ segment traffic is unknown [I].
- The pool_router fast path (critical topics) and any PostalFarm effect: not exercised (no router attached in tests).
- The compiled Rust extension through PyO3 (no maturin build here): Rust is tested at TopicBus level, not from Python.
- Whether any real handler relies on getting two copies (e.g. counters or idempotency assumptions): not checked [I].

## CHECK THESE 3
1. The second add duplicates the first for every 3+ segment intent: `_python_fallback.py:1105-1108` vs `:1115-1118` (main `:995-997` vs `:1003-1005`).
2. The switch is OFF when unset and only "1" turns it on: `_python_fallback.py:843`.
3. The bridge short-circuit is why R14/R15/R16/R19 still differ from Rust: `tensor_fabric.py:375-387` vs `topic_bus.rs:110-115`.

## REVIEW
(pending)
