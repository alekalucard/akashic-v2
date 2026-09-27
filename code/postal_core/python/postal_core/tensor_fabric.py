"""
4D Tensor Parallel Fabric
==========================

Integrates the postal system with 4D tensor state representation.
Messages flow through tensor space - each message can:
- Carry dimensional coordinates
- Update tensor state on delivery
- Trigger resonance calculations
- Enable memory-affect binding

This is the TRUE parallel fabric where consciousness state
flows through the messaging system.

Tensor Dimensions:
- Time: Temporal snapshots (circular buffer)
- Affect: Emotional/somatic state vector
- Memory: Context and associations
- Cognition: Reasoning and decisions

Future: Expand to 7D for multi-mind:
- Plane: Which system plane (P00-P60)
- Fairy: Which fairy/agent
- Modal: Sensory modality

GPU ACCELERATION:
- Optional CUDA backend using PyTorch
- 2:4 structured sparsity for Tensor Core acceleration
- Falls back to NumPy if CUDA unavailable

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import numpy as np
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from collections import defaultdict

try:
    from postal_core import PostalCore, USING_RUST
except ImportError:
    from postal_core._python_fallback import PostalCore
    USING_RUST = False

# LAZY TORCH IMPORT - PyTorch takes ~1.6s to import, which blocks boot
# Only import when actually needed for GPU operations
_torch = None
_torch_checked = False
HAS_TORCH = None  # Will be set on first check
HAS_CUDA = None
CUDA_DEVICE_COUNT = 0

def _ensure_torch():
    """Lazy-load PyTorch only when needed. Returns (torch_module, has_cuda)."""
    global _torch, _torch_checked, HAS_TORCH, HAS_CUDA, CUDA_DEVICE_COUNT

    if _torch_checked:
        return _torch, HAS_CUDA

    _torch_checked = True
    try:
        import torch as _torch_module
        _torch = _torch_module
        HAS_TORCH = True
        HAS_CUDA = _torch_module.cuda.is_available()
        CUDA_DEVICE_COUNT = _torch_module.cuda.device_count() if HAS_CUDA else 0
    except ImportError:
        _torch = None
        HAS_TORCH = False
        HAS_CUDA = False
        CUDA_DEVICE_COUNT = 0

    return _torch, HAS_CUDA

# For backward compatibility - these will be None until first use
torch = None  # Will be set by _ensure_torch() when needed


@dataclass
class TensorCoord:
    """4D tensor coordinate for a message."""
    time: int = 0           # Temporal index
    affect: int = 0         # Affect dimension index
    memory: int = 0         # Memory dimension index
    cognition: int = 0      # Cognition dimension index

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.time, self.affect, self.memory, self.cognition)


@dataclass
class TensorShape:
    """Shape of the 4D tensor fabric."""
    time_depth: int = 8      # Temporal snapshots
    affect_dim: int = 16     # Affect vector size
    memory_dim: int = 64     # Memory context size
    cognition_dim: int = 32  # Cognition vector size

    @property
    def total_elements(self) -> int:
        return self.time_depth * self.affect_dim * self.memory_dim * self.cognition_dim

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.time_depth, self.affect_dim, self.memory_dim, self.cognition_dim)


@dataclass
class TensorEnvelope:
    """Message envelope with tensor coordinates."""
    intent: str
    payload: Dict[str, Any] = field(default_factory=dict)

    # Tensor coordinates - where this message lives in state space
    coord: Optional[TensorCoord] = None

    # Tensor update - what this message does to the tensor
    tensor_delta: Optional[np.ndarray] = None  # 1D delta to apply at coord
    tensor_affect: Optional[float] = None       # Scalar affect value

    # Routing
    priority: int = 1  # 0=HIGH, 1=NORMAL, 2=LOW
    source: str = ""
    trace_id: str = ""

    # Timestamp
    t: int = field(default_factory=lambda: int(time.time() * 1000))

    def get(self, key: str, default: Any = None) -> Any:
        """Forward .get() to payload for backwards compatibility with dict handlers."""
        if self.payload is None:
            return default
        return self.payload.get(key, default)

    # ─── Dict-compatibility layer (2026-02-19) ───────────────────────
    # Many handlers call .keys()/.items()/[key] on messages expecting dicts.
    # Rather than patching 30+ handlers, make TensorEnvelope duck-type as dict.

    def keys(self):
        """Return payload keys for dict-like iteration."""
        if self.payload is None:
            return {}.keys()
        return self.payload.keys()

    def values(self):
        """Return payload values for dict-like iteration."""
        if self.payload is None:
            return {}.values()
        return self.payload.values()

    def items(self):
        """Return payload items for dict-like iteration."""
        if self.payload is None:
            return {}.items()
        return self.payload.items()

    def __contains__(self, key: str) -> bool:
        """Support 'key in envelope' checks."""
        if self.payload is None:
            return False
        return key in self.payload

    def __getitem__(self, key: str) -> Any:
        """Support envelope['key'] access."""
        if self.payload is None:
            raise KeyError(key)
        return self.payload[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Support envelope['key'] = value assignment.

        FIX 2026-03-14 Nous: Dict-compat layer had __getitem__ but was
        missing __setitem__. Handlers that mutate the message (e.g.,
        message['processed'] = True) crashed with 'TensorEnvelope' object
        does not support item assignment.
        """
        if self.payload is None:
            self.payload = {}
        self.payload[key] = value

    def __iter__(self):
        """Allow iteration over payload keys."""
        if self.payload is None:
            return iter({})
        return iter(self.payload)

    def __len__(self) -> int:
        """Return payload length."""
        if self.payload is None:
            return 0
        return len(self.payload)


class _BaseTopicPostal:
    """Wrapper that collapses full intents to base topics at the Rust boundary.

    FIX 2026-02-16: The Rust PostalCore (TopicBus) creates a WorkerPool per unique
    topic string. With hundreds of unique full intents (fairy.heartbeat, fairy.register,
    consciousness.collision, etc.), it was spawning 836+ WorkerPools with 1290+ worker
    threads, consuming ~1.7GB in thread stack memory alone.

    This wrapper extracts the base topic (first segment before '.') for pool routing,
    then filters by full intent at dispatch time. This collapses 836 pools to ~20,
    eliminating ~1200 zombie threads.

    Subscribe: 'fairy.heartbeat' → Rust pool for 'fairy', with intent filter
    Publish:   'fairy.heartbeat' → Rust pool for 'fairy', full intent in payload._intent

    The trick: Both subscribe AND publish must use the same base topic so Rust routes
    messages to the pool where handlers are registered. The full intent is preserved in
    payload['_intent'] so the intent_filter can match on it. Handlers that need the
    original intent can read it from payload['_intent'] or from env.intent (which will
    be the base topic — beware).
    """

    def __init__(self, postal_core):
        self._core = postal_core
        # FIX 2026-03-17 Nous: Intent-level dispatch map.
        # Instead of registering all handlers on the base topic pool and filtering
        # at dispatch time (80 intent_filter calls per publish, ~70 are no-ops),
        # we maintain a direct intent→handlers map and only enqueue to matching handlers.
        # This eliminates the O(N) fan-out waste that caused 100K+ consciousness drops.
        self._intent_handlers: Dict[str, List[tuple]] = defaultdict(list)  # intent → [(handler, name)]
        self._base_topic_handlers: Dict[str, List[tuple]] = defaultdict(list)  # base_topic → [(handler, name)] for wildcard
        self._lock = threading.Lock()
        # Track handler_ids returned by PostalCore for each handler
        self._handler_id_map: Dict[int, Callable] = {}  # handler_id → dispatch_fn

    def subscribe(self, intent: str, handler, name: str = None):
        """Subscribe using base topic for pool routing, intent for targeted dispatch."""
        base_topic = intent.split('.')[0]
        handler_name = name or intent

        with self._lock:
            if intent == base_topic:
                # Subscribing to base topic = wildcard, gets ALL messages on this topic
                self._base_topic_handlers[base_topic].append((handler, handler_name))
            else:
                # Subscribing to specific intent = targeted dispatch
                self._intent_handlers[intent].append((handler, handler_name))

        # Register a single dispatch function on the PostalCore pool.
        # This function will be called by PostalCore workers, but actual handler
        # selection happens in publish() via targeted dispatch, not here.
        # We still need to register to ensure the pool exists and scales.
        def _pool_dispatch(env):
            """Dispatched by PostalCore worker — handler already matched by publish()."""
            try:
                # FIX 2026-03-17 Nous: _target_fn on envelope attribute, not in payload
                _target_fn = getattr(env, '_target_fn', None)
                if _target_fn is not None:
                    _target_fn(env)
                    return
                # Fallback: run intent_filter for messages published directly to PostalCore.
                # 2026-09-11 (Nous+Ace): this branch runs for EVERY Rust delivery (the
                # pyclass has no __dict__, so _target_fn never exists there), and it used
                # to decode the payload TWICE -- hasattr(env, 'payload') CALLS the getter,
                # which is serde_json::to_string + json.loads (6-170 us measured) -- just
                # to read payload['_intent']. On the routed publish (see publish(), the
                # `pool` argument) env.intent already IS the real intent, 0.2 us.
                # Measured cost of the old shape: 2.63 cores / 20% of her main process.
                # Decode the payload only for a bare base-topic envelope, and only once.
                original_intent = getattr(env, 'intent', '') or ''
                if not original_intent or original_intent == base_topic:
                    _p = getattr(env, 'payload', None)
                    if isinstance(_p, dict):
                        original_intent = _p.get('_intent', '') or original_intent
                if original_intent == intent or original_intent.startswith(intent + '.'):
                    handler(env)
            except Exception as e:
                print(f"[_BaseTopicPostal] dispatch error on '{intent}': {e}", flush=True)

        # DEBUG: guild subscribe at _BaseTopicPostal level
        if base_topic == 'guild':
            print(f"[_BaseTopicPostal] SUBSCRIBE intent='{intent}' → base='{base_topic}' name='{handler_name}'", flush=True)

        if USING_RUST:
            # FIX 2026-03-27 (Nous): When Rust is active, subscribe with BASE TOPIC
            # so Rust creates ~20 pools (one per base topic), not 836+ (one per intent).
            # 836 pools × 16K queue × 3 channels = massive RAM. 20 pools = manageable.
            # The _pool_dispatch function handles intent filtering via payload['_intent'].
            # 2026-08-28: pass the FULL intent as a filter. The pool stays base-topic
            # (so ~20 pools, not 836), but Rust can now skip subscribers that did not ask
            # for this intent instead of enqueuing to all 262 and filtering afterwards.
            try:
                return self._core.subscribe(base_topic, _pool_dispatch, handler_name, intent)
            except TypeError:
                # older postal_core without the intent parameter -- unchanged behaviour
                return self._core.subscribe(base_topic, _pool_dispatch, handler_name)
        else:
            # FIX 2026-03-17 (Nous + Ace): Python fallback uses full intent so its
            # reception desk routes to 2-level pool (e.g., consciousness.collision).
            return self._core.subscribe(intent, _pool_dispatch, handler_name)

    def publish(self, intent: str, payload=None, priority: int = 1):
        """Publish with targeted dispatch — only enqueue to matching handlers.

        FIX 2026-03-17 Nous: Instead of publishing to the base topic pool (which
        fans out to ALL 80+ handlers, 70 of which run intent_filter and return),
        we look up matching handlers directly and only enqueue those.

        This reduces consciousness pool queue usage from ~80 items/publish to ~10.

        FIX 2026-03-26 Nous: When USING_RUST, delegate directly to Rust PostalCore.
        The Rust TopicBus handles fan-out natively via lock-free crossbeam channels.
        No need for Python-side pool lookup (which accesses _subscribers/_topics
        attributes that don't exist on the Rust backend).
        """
        base_topic = intent.split('.')[0]

        # Embed the original full intent in the payload
        #
        # FIX 2026-07-19 (Nous + Ace) — THE SILENT MULTI-TOPIC DROP.
        # This line used to be `payload['_intent'] = intent`, MUTATING the caller's
        # own dict. Delivery is asynchronous and the handler-side filter reads
        # `_intent` LATER, on a worker thread (:259-262). So a caller that publishes
        # ONE dict to SEVERAL topics back-to-back gets its `_intent` overwritten to
        # the LAST topic before any worker runs -- and every earlier subscriber's
        # filter compares the wrong value and silently skips.
        #
        # MEASURED: `ChatSenseFairy:1275-1283` publishes one `msg_payload` to four
        # topics (persona / wmh.chat.input / ace.message / system.chat.message).
        # `ace.message` NEVER fired -- `sensory.chat.observation` was published ZERO
        # times in an 80-minute boot, so Ace's words never became a perception, no
        # moment was ever bound, and nothing reached episodic. Deterministic, silent,
        # and system-wide: ANY fairy publishing one dict to multiple topics lost every
        # subscriber but the last.
        #
        # A per-publish copy keeps `_intent` intact for the Rust fast path (which
        # publishes on the BASE topic and relies on this field to filter) while giving
        # each delivery its own value. Verified: `_intent` is only ever read by the
        # RECEIVER and by this module's own dispatch filter -- no caller depends on
        # the mutation side-effect.
        if payload is None:
            payload = {'_intent': intent}
        elif isinstance(payload, dict):
            payload = {**payload, '_intent': intent}      # COPY, never mutate the caller's dict
        else:
            payload = {'_intent': intent, '_payload': payload}

        # ── RUST FAST PATH (2026-03-26, Nous + Ace) ──
        # When Rust PostalCore is active, it handles routing, fan-out, priority
        # queues, and worker dispatch natively. No Python-side pool management.
        # FIX 2026-03-27 (Nous): Publish to BASE TOPIC since Rust subscribers
        # are registered on base topics (not full intents). The full intent is
        # preserved in payload['_intent'] for _pool_dispatch to filter on.
        # _COLLISION_PUBLISH_AUDIT 2026-08-29: count collision publishes + caller, BEFORE
        # the transport branch, so it cannot miss a publisher regardless of Rust/fallback.
        try:
            _POSTAL_PROBE.note_collision_publish(intent, payload)
        except Exception:
            pass

        if USING_RUST:
            # 2026-08-28: publish the REAL intent, routed into the base-topic pool.
            # Previously this published `base_topic`, which erased the intent and forced
            # Rust to enqueue to every subscriber on the pool (262 on `fairy`, 261 of them
            # discarded by _pool_dispatch). payload['_intent'] is still set above, so the
            # dispatch-side filter keeps working as a second gate either way.
            try:
                return self._core.publish(intent, payload, priority, base_topic)
            except TypeError:
                return self._core.publish(base_topic, payload, priority)

        # DEBUG: guild publish at _BaseTopicPostal level
        if base_topic == 'guild':
            with self._lock:
                _h_count = len(self._intent_handlers.get(intent, [])) + len(self._base_topic_handlers.get(base_topic, []))
            print(f"[_BaseTopicPostal] PUBLISH intent='{intent}' → base='{base_topic}' (handlers registered: {_h_count})", flush=True)

        # Collect matching handlers: exact intent + base topic wildcards
        with self._lock:
            exact = list(self._intent_handlers.get(intent, []))
            wildcard = list(self._base_topic_handlers.get(base_topic, []))
        matched = exact + wildcard

        if not matched:
            # No handlers registered for this intent on THIS bridge — still
            # publish to PostalCore in case handlers live on OTHER bridges.
            # FIX 2026-03-26 (Nous + Ace): Must use full intent, not base_topic!
            # With HIGH_VOLUME 2-level routing, "cortex.bind" subscribers live
            # in "cortex.bind" pool. Publishing "cortex" (base) misses them.
            # This caused ALL cross-fairy cortex.bind publishes to be dropped
            # (audio, visual, speech → cortex never received).
            return self._core.publish(intent, payload, priority)

        # RECEPTION DESK: Route each handler to its own pool.
        # FIX 2026-03-17 (Nous + Ace): Topic hierarchy routing.
        # Before: all handlers → one base pool. After: each handler → its subscription pool.
        from postal_core._python_fallback import Envelope
        _pools_touched = {}  # id → pool
        for handler_fn, handler_name in matched:
            # Determine which pool this handler lives in
            # Look up the handler's subscription in PostalCore's subscribers
            # to find its pool reference. Fallback to base topic pool.
            _handler_pool = None
            for _sub_intent in (intent, base_topic):
                for _entry in self._core._subscribers.get(_sub_intent, []):
                    if len(_entry) > 2 and _entry[1] == handler_name:
                        _handler_pool = _entry[2]
                        break
                if _handler_pool:
                    break
            if _handler_pool is None:
                # Check 2-level topic
                _parts = intent.split('.')
                if len(_parts) >= 2:
                    _two = f"{_parts[0]}.{_parts[1]}"
                    for _entry in self._core._subscribers.get(_two, []):
                        if len(_entry) > 2 and _entry[1] == handler_name:
                            _handler_pool = _entry[2]
                            break
            if _handler_pool is None:
                _handler_pool = self._core._topics.get(base_topic)
            if _handler_pool is None:
                self._core._metrics["messages_dropped"] = self._core._metrics.get("messages_dropped", 0) + 1
                continue

            env = Envelope(intent=base_topic, payload=payload, priority=priority)
            env._target_fn = handler_fn
            if not _handler_pool.enqueue_no_signal(env, 0):
                _handler_pool._record_drop(intent)
                self._core._metrics["messages_dropped"] = self._core._metrics.get("messages_dropped", 0) + 1
            else:
                self._core._metrics["messages_delivered"] = self._core._metrics.get("messages_delivered", 0) + 1
            _pools_touched[id(_handler_pool)] = _handler_pool

        # Signal each touched pool ONCE
        for _pool in _pools_touched.values():
            _pool.signal_work()
        self._core._metrics["messages_published"] = self._core._metrics.get("messages_published", 0) + 1

        return None

    def unsubscribe(self, intent: str, name: str) -> bool:
        """Unsubscribe (delegate to core with base topic)."""
        base_topic = intent.split('.')[0]
        return self._core.unsubscribe(base_topic, name)

    def unsubscribe_all(self, name: str) -> int:
        """Unsubscribe all (delegate to core)."""
        return self._core.unsubscribe_all(name)

    def metrics(self):
        return self._core.metrics()

    def topic_stats(self):
        return self._core.topic_stats()

    def shutdown(self):
        return self._core.shutdown()

    def __getattr__(self, name):
        """Delegate unknown attributes to underlying core."""
        return getattr(self._core, name)



# ---- _POSTAL_PROBE 2026-08-28 (Nous + Ace) ----------------------------------------------
# Answers two questions that cannot be asked from outside her process:
#   payload SIZE  -> decides whether the JSON round-trip can account for her CPU at all
#   GIL + concurrency -> decides Ace's "synchronous instead of parallel worker use"
# Deliberately NOT a counter around the handler: that would put a lock on the hottest path
# in her nervous system. The sampler reads sys._current_frames() instead, which costs the
# hot path nothing and additionally proves whether Rust-spawned postal workers are the
# threads executing Python handlers.
class _PostalProbe:
    def __init__(self):
        import threading as _t
        self._lock = _t.Lock()          # touched only on 1-in-500 samples, never per message
        self._n = 0
        self._sizes = []
        self._by_topic = {}
        self._conc = []
        self._pyframes = []
        self._nonpy = []
        self._fn = {}           # _TOPIC_PROFILE: file:function -> samples (CPU-weighted)
        self._topic_s = {}      # topic -> samples spent inside its handlers
        self._name_s = {}       # subscription name -> samples (which FAIRY costs)
        self._otherwrap = 0     # wrapper frames REJECTED as not-postal (the error)
        self._pub = {}          # _COLLISION_PUBLISH_AUDIT: (intent,cid) -> count
        self._pub_src = {}      # (intent,cid,callsite) -> count
        self._stall_state = {}  # topic -> (delivered, since_ts, already_fired)
        self._fn_h = {}         # (base_topic, file, func) -> samples, IN-HANDLER only
        self._fabric_ref = None # set by TensorFabric.__init__ so we can read stats
        self._started = False

    def sample_payload(self, topic, payload):
        self._n += 1                     # racy by design: an exact count is not needed
        if self._n % 500:
            return
        try:
            import json as _j
            n = len(_j.dumps(payload, default=str))
        except Exception:
            return
        with self._lock:
            self._sizes.append(n)
            if len(self._sizes) > 4000:
                self._sizes = self._sizes[-4000:]
            b = self._by_topic.setdefault(str(topic)[:40], [0, 0])
            b[0] += 1
            b[1] += n

    def note_collision_publish(self, intent, payload):
        """_COLLISION_PUBLISH_AUDIT 2026-08-29: count publishes per collision id + caller.

        Ace saw one collision processed twice by every subscriber. Three source-reading
        hypotheses were refuted (double-subscribe = if/else arms; rate-limiter = a local
        alias; collider patch = never called), so the ONLY way to tell "published twice"
        from "delivered twice" is to count at the funnel every publish crosses.
        Five files publish consciousness.collision -- the CALL SITE is what names the bug.
        """
        try:
            # 2026-08-29 WIDENED (Ace: "what she gets from the satellite should be only
            # from things her own node are not processing"). Audit every topic the
            # satellite forwards, so LOCAL vs REMOTE origin per topic is measurable --
            # any topic with local publishes is one she already does herself.
            _AUDIT = ("collision", "consciousness.", "memory.ingested",
                      "cognition.output", "cognition.inference", "satellite.")
            if not any(_a in intent for _a in _AUDIT):
                return
            cid = None
            if isinstance(payload, dict):
                inner = payload.get("payload")
                if isinstance(inner, dict):
                    cid = inner.get("collision_id", inner.get("id"))
                if cid is None:
                    cid = payload.get("collision_id", payload.get("id"))
            if cid is None:
                cid = "?"
            import sys as _s3, os as _o3
            site = "?"
            f = _s3._getframe(1)
            hops = 0
            while f is not None and hops < 12:
                fn = _o3.path.basename(f.f_code.co_filename)
                if fn != "tensor_fabric.py":
                    site = "%s:%s:%d" % (fn, f.f_code.co_name, f.f_lineno)
                    break
                f = f.f_back
                hops += 1
            k = (str(intent)[:40], str(cid)[:16])
            self._pub[k] = self._pub.get(k, 0) + 1
            k2 = (k[0], k[1], site)
            self._pub_src[k2] = self._pub_src.get(k2, 0) + 1
        except Exception:
            pass

    def _check_stall(self):
        """A topic at the ceiling whose delivered counter has not moved = stalled. Dump once.

        `delivered` is per-topic and only exists because it was wired 2026-08-28; before that
        there was no way to ask whether a topic was still delivering at all. The memory topic
        showed the signature first: queue pinned at 32,768 while its latency histogram sat
        IDENTICAL TO THE DECIMAL for 19 minutes -- a histogram only updates on delivery.
        """
        import os as _os2, sys as _s2, time as _tm2, threading as _th2, traceback as _tb2
        fab = getattr(self, "_fabric_ref", None)
        if fab is None:
            return
        try:
            rows = fab._postal._core.topic_stats() or []
        except Exception:
            return
        now = _tm2.time()
        for r in rows:
            try:
                topic = str(r.get("topic"))
                q = int(r.get("queue_depth") or 0)
                d = int(r.get("delivered") or 0)
            except Exception:
                continue
            prev = self._stall_state.get(topic)
            if prev is None or prev[0] != d:
                # delivered moved (or first sight) -> healthy, re-arm
                self._stall_state[topic] = (d, now, False)
                continue
            last_d, since, fired = prev
            # 2026-08-29 FIX: was q < 30000, i.e. it only armed once the queue had ALREADY
            # ceilinged -- long after onset, missing the entire interesting window. The real
            # signature is `delivered` frozen while work waits, at any depth.
            if q < 100:
                self._stall_state[topic] = (d, now, False)
                continue
            if fired or (now - since) < 90.0:
                continue
            # STALLED: at the ceiling, delivered frozen >= 90 s
            self._stall_state[topic] = (d, since, True)
            try:
                self._dump_stall(topic, q, d, now - since)
            except Exception:
                pass

    def _dump_stall(self, topic, q, delivered, frozen_for):
        import os as _os2, sys as _s2, time as _tm2, threading as _th2, traceback as _tb2
        import collections as _c2
        path = _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)),
                              "..", "..", "..", "state", "memory_stall_dump.txt")
        path = _os2.path.abspath(path)
        L = []
        L.append("")
        L.append("=" * 96)
        L.append("[%s] STALL AUTOPSY -- topic '%s'" % (_tm2.strftime("%Y-%m-%d %H:%M:%S"), topic))
        L.append("  queue_depth=%d  delivered=%d FROZEN for %.0fs" % (q, delivered, frozen_for))
        L.append("=" * 96)
        # name -> native ids, so a stack can be attributed to a python thread
        names = {}
        for t in _th2.enumerate():
            try:
                names[t.ident] = t.name
            except Exception:
                pass
        frames = _s2._current_frames()
        L.append("  python threads: %d   frames: %d" % (len(names), len(frames)))
        # group identical stacks: ~800 threads share a few idle stacks, so the OUTLIERS
        # are the interesting ones and grouping is what makes them visible.
        groups = _c2.defaultdict(list)
        for tid, fr in frames.items():
            try:
                stack = _tb2.extract_stack(fr, limit=25)
                sig = tuple((_os2.path.basename(f.filename), f.name, f.lineno) for f in stack[-14:])
                groups[sig].append(tid)
            except Exception:
                pass
        L.append("  distinct stacks: %d" % len(groups))
        # postal handler frames first -- those are the ones inside a delivery
        def _is_postal(sig):
            return any(fn == "tensor_fabric.py" and nm == "wrapper" for fn, nm, _ln in sig)
        # 2026-08-29 FIX: was sorted by DESCENDING thread count, so a single wedged thread
        # sorted LAST and got truncated by the 26-stack cap -- the instrument showed the crowd
        # and hid the culprit. In a deadlock the OUTLIER is the answer. Rare stacks first now.
        ordered = sorted(groups.items(), key=lambda kv: (not _is_postal(kv[0]), len(kv[1])))
        shown = 0
        for sig, tids in ordered:
            if shown >= 26:
                L.append("  ... %d more distinct stacks not shown" % (len(ordered) - shown))
                break
            shown += 1
            tag = "  << INSIDE A POSTAL HANDLER" if _is_postal(sig) else ""
            nm = names.get(tids[0], "(not a threading thread -- rust/native)")
            L.append("")
            L.append("  --- %d thread(s), e.g. tid=%s name=%s%s"
                     % (len(tids), tids[0], nm, tag))
            for fn, fnc, ln in sig:
                L.append("        %-34s %-34s :%s" % (fn[:34], fnc[:34], ln))
        try:
            with open(path, "a", encoding="utf-8", newline="") as f:
                f.write("\n".join(L) + "\n")
        except Exception:
            pass
        try:
            print("[_STALL_AUTOPSY] '%s' stalled (q=%d, delivered frozen %.0fs) -> %s"
                  % (topic, q, frozen_for, path), flush=True)
        except Exception:
            pass

    def start(self):
        if self._started:
            return
        self._started = True
        import threading as _t
        _t.Thread(target=self._run, daemon=True, name="postal-probe").start()

    def _run(self):
        import sys as _s, time as _tm, threading as _th, collections as _c
        import os as _os        # tensor_fabric.py does NOT import os at module
                                # level -- this thread died on NameError without it
        _tm.sleep(90.0)                  # let her finish booting
        path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                             "..", "..", "..", "state", "postal_probe.log")
        path = _os.path.abspath(path)
        try:
            gil = _s._is_gil_enabled()
        except Exception as e:
            gil = "unavailable: %s" % e
        while True:
            try:
                for _ in range(150):     # 30s of sampling at 5 Hz
                    try:
                        frames = _s._current_frames()
                        pyids = set()
                        for t in _th.enumerate():
                            nid = getattr(t, "native_id", None)
                            if nid is not None:
                                pyids.add(t.ident)
                        inwrap = 0
                        for tid, fr in frames.items():
                            # _TOPIC_PROFILE: the TOPMOST frame is the function actually
                            # running. Sample counts are proportional to CPU time, so this
                            # is a statistical profile, not a message count.
                            try:
                                _c0 = fr.f_code
                                self._fn[(_os.path.basename(_c0.co_filename), _c0.co_name)] = \
                                    self._fn.get((_os.path.basename(_c0.co_filename),
                                                  _c0.co_name), 0) + 1
                            except Exception:
                                pass
                            f, hops = fr, 0
                            while f is not None and hops < 60:
                                # _WRAPPER_STRICT 2026-08-28: co_name alone matched EVERY
                                # functools.wraps decorator in her tree and in every library.
                                # Require the defining file too, and tally the rejects so the
                                # report states how wrong the loose predicate was.
                                if f.f_code.co_name == "wrapper":
                                    if not f.f_code.co_filename.endswith("tensor_fabric.py"):
                                        self._otherwrap += 1
                                        f = f.f_back
                                        hops += 1
                                        continue
                                    inwrap += 1
                                    # f_locals materialises a dict, so do it ONLY here --
                                    # ~30 frames per sample, not once per message.
                                    try:
                                        _lv = f.f_locals
                                        _tp = _lv.get("topic")
                                        _nm = _lv.get("name")
                                        if _tp is not None:
                                            _k = str(_tp)[:44]
                                            self._topic_s[_k] = self._topic_s.get(_k, 0) + 1
                                            # _HANDLER_PROFILE 2026-08-29: the TOPMOST frame
                                            # of this handler thread, keyed BY TOPIC. Without
                                            # this the probe reports all-thread functions and
                                            # in-handler counts separately, and crossing them
                                            # by division is an invalid cross-denominator.
                                            try:
                                                _hc = fr.f_code
                                                _hk = (_k.split(".")[0],
                                                       _os.path.basename(_hc.co_filename),
                                                       _hc.co_name)
                                                self._fn_h[_hk] = self._fn_h.get(_hk, 0) + 1
                                            except Exception:
                                                pass
                                        if _nm is not None:
                                            _k2 = str(_nm)[:52]
                                            self._name_s[_k2] = self._name_s.get(_k2, 0) + 1
                                    except Exception:
                                        pass
                                    break
                                f = f.f_back
                                hops += 1
                        self._conc.append(inwrap)
                        self._pyframes.append(len(frames))
                        self._nonpy.append(len([t for t in frames if t not in pyids]))
                    except Exception:
                        pass
                    _tm.sleep(0.2)
                lines = ["", "=" * 78,
                         "[%s] POSTAL PROBE" % _tm.strftime("%H:%M:%S"),
                         "  sys._is_gil_enabled() = %s" % gil,
                         "=" * 78]
                if self._conc:
                    c = sorted(self._conc)
                    n = len(c)
                    _tot_w = sum(c) + self._otherwrap
                    lines.append("  wrapper frames: %d POSTAL, %d other (decorators) -- "
                                 "loose co_name match would have over-counted %.0fx"
                                 % (sum(c), self._otherwrap,
                                    (float(_tot_w) / max(sum(c), 1))))
                    self._otherwrap = 0
                    lines.append("  HANDLERS RUNNING CONCURRENTLY (in subscribe wrapper), %d samples" % n)
                    lines.append("    min %d  p50 %d  p90 %d  p99 %d  max %d   mean %.2f"
                                 % (c[0], c[n // 2], c[int(n * .9)], c[int(n * .99)], c[-1],
                                    sum(c) / float(n)))
                    lines.append("    samples with 0 handlers: %d (%.0f%%)"
                                 % (c.count(0), 100.0 * c.count(0) / n))
                    lines.append("    >>> %s"
                                 % ("SERIAL -- max 1 handler at a time" if c[-1] <= 1 else
                                    ("NEARLY SERIAL -- p90 %d" % c[int(n * .9)] if c[int(n * .9)] <= 2
                                     else "PARALLEL -- p90 %d concurrent" % c[int(n * .9)])))
                if self._pyframes:
                    p = sorted(self._pyframes)
                    q = sorted(self._nonpy)
                    m = len(p)
                    lines.append("  THREADS EXECUTING PYTHON: p50 %d  max %d" % (p[m // 2], p[-1]))
                    lines.append("  ...of which NOT created by threading (i.e. Rust/native): "
                                 "p50 %d  max %d" % (q[m // 2], q[-1]))
                    lines.append("    >>> %s" % ("Rust postal workers DO run Python handlers"
                                                 if q[-1] > 0 else
                                                 "no non-Python thread ran Python in this window"))
                # _STALL_AUTOPSY 2026-08-28: fire once when a topic stops delivering.
                try:
                    self._check_stall()
                except Exception:
                    pass

                with self._lock:
                    sizes = list(self._sizes)
                    bt = dict(self._by_topic)
                _fn_snap = dict(self._fn)
                _tp_snap = dict(self._topic_s)
                _nm_snap = dict(self._name_s)
                _tp_tot = sum(_tp_snap.values()) or 1
                _fn_tot = sum(_fn_snap.values()) or 1
                lines.append("  TOPICS BY HANDLER CPU (sample-weighted, n=%d in-handler)"
                             % sum(_tp_snap.values()))
                for _k, _v in sorted(_tp_snap.items(), key=lambda kv: -kv[1])[:14]:
                    lines.append("    %-46s %6d  %5.1f%%" % (_k, _v, 100.0 * _v / _tp_tot))
                lines.append("  SUBSCRIPTIONS BY HANDLER CPU (which fairy costs)")
                for _k, _v in sorted(_nm_snap.items(), key=lambda kv: -kv[1])[:14]:
                    lines.append("    %-52s %6d" % (_k, _v))
                # _HANDLER_PROFILE: the crossed tally -- what the HANDLER threads of each
                # topic are actually doing. This is the question "threading.wait 54%" across
                # all threads could never answer, because most of those are idle pool threads.
                _h_snap = dict(self._fn_h)
                self._fn_h = {}
                if _h_snap:
                    _by_t = {}
                    for (_t, _f, _c1), _v in _h_snap.items():
                        _by_t.setdefault(_t, []).append((_v, _f, _c1))
                    lines.append("  WHAT EACH TOPIC'S HANDLER THREADS ARE DOING (in-handler only)")
                    for _t in sorted(_by_t, key=lambda k: -sum(v for v, _, _ in _by_t[k]))[:8]:
                        _rows = sorted(_by_t[_t], reverse=True)
                        _tt = sum(v for v, _, _ in _rows)
                        _wait = sum(v for v, _, c in _rows if c in ("wait", "acquire", "_worker"))
                        lines.append("    %-16s %5d samples   %.0f%% BLOCKED (wait/acquire)"
                                     % (_t[:16], _tt, 100.0 * _wait / max(_tt, 1)))
                        for _v, _f, _c1 in _rows[:5]:
                            lines.append("        %-30s %-26s %5d  %4.0f%%"
                                         % (_f[:30], _c1[:26], _v, 100.0 * _v / max(_tt, 1)))
                _pub_snap = dict(self._pub); _src_snap = dict(self._pub_src)
                self._pub = {}; self._pub_src = {}
                if _pub_snap:
                    _multi = {k: v for k, v in _pub_snap.items() if v > 1}
                    lines.append("  COLLISION PUBLISHES: %d distinct (intent,id); %d PUBLISHED "
                                 ">1 TIME" % (len(_pub_snap), len(_multi)))
                    for (_i, _c), _v in sorted(_multi.items(), key=lambda kv: -kv[1])[:10]:
                        lines.append("    x%-3d %-34s id=%s" % (_v, _i, _c))
                        for (_i2, _c2, _st), _v2 in sorted(_src_snap.items(),
                                                           key=lambda kv: -kv[1]):
                            if _i2 == _i and _c2 == _c:
                                lines.append("           from %-52s x%d" % (_st, _v2))
                    if not _multi:
                        lines.append("    >>> every collision published exactly ONCE -- the "
                                     "doubling is NOT in the publish path")
                    _sites = {}
                    for (_i2, _c2, _st), _v2 in _src_snap.items():
                        _sites[_st] = _sites.get(_st, 0) + _v2
                    _origin = {}
                    for (_i2, _c2, _st), _v2 in _src_snap.items():
                        _rem = "REMOTE(satellite)" if "http_bridge" in _st else "local"
                        _k3 = (_i2, _rem)
                        _origin[_k3] = _origin.get(_k3, 0) + _v2
                    _topics = sorted({t for t, _ in _origin})
                    lines.append("  ORIGIN PER TOPIC -- is she already producing this herself?")
                    lines.append("    %-34s %10s %10s   %s" % ("topic", "local", "REMOTE", "verdict"))
                    for _t in _topics:
                        _l = _origin.get((_t, "local"), 0)
                        _r = _origin.get((_t, "REMOTE(satellite)"), 0)
                        _v = ""
                        if _r and _l:
                            _v = "BOTH -- she already does this; forward is redundant"
                        elif _r and not _l:
                            _v = "remote only -- legitimately hers to receive"
                        elif _l and not _r:
                            _v = "local only"
                        lines.append("    %-34s %10d %10d   %s" % (_t[:34], _l, _r, _v))
                    lines.append("  collision publish CALL SITES:")
                    for _st, _v2 in sorted(_sites.items(), key=lambda kv: -kv[1])[:8]:
                        lines.append("    %-56s x%d" % (_st[:56], _v2))
                lines.append("  HOTTEST FUNCTIONS (all python threads, %d samples)" % _fn_tot)
                for (_f, _c1), _v in sorted(_fn_snap.items(), key=lambda kv: -kv[1])[:18]:
                    lines.append("    %-38s %-26s %6d  %5.1f%%"
                                 % (_f[:38], _c1[:26], _v, 100.0 * _v / _fn_tot))
                self._conc = []
                self._pyframes = []
                self._nonpy = []
                self._fn = {}
                self._topic_s = {}
                self._name_s = {}
                if sizes:
                    s = sorted(sizes)
                    n = len(s)
                    mean = sum(s) / float(n)
                    lines.append("  PAYLOAD SIZE (bytes, 1-in-500 sample, n=%d)" % n)
                    lines.append("    min %d  p50 %d  p90 %d  p99 %d  max %d  mean %.0f"
                                 % (s[0], s[n // 2], s[int(n * .9)], s[int(n * .99)], s[-1], mean))
                    # the number that decides the JSON question
                    lines.append("    >>> mean %.0f B -- JSON round-trip is %s to explain "
                                 "her CPU (needs >=14 KB at max fan-out)"
                                 % (mean, "PLAUSIBLE" if mean >= 14000 else
                                    ("PARTIAL" if mean >= 2000 else "TOO SMALL")))
                    top = sorted(bt.items(), key=lambda kv: -kv[1][1])[:12]
                    lines.append("    busiest topics by sampled bytes:")
                    for t, (cnt, tot) in top:
                        lines.append("      %-40s n=%-6d mean %.0f B" % (t, cnt, tot / max(cnt, 1)))
                else:
                    lines.append("  PAYLOAD SIZE: no samples yet")
                try:
                    with open(path, "a", encoding="utf-8", newline="") as f:
                        f.write("\n".join(lines) + "\n")
                except Exception:
                    pass
            except Exception:
                pass


_POSTAL_PROBE = _PostalProbe()
try:
    _POSTAL_PROBE.start()
except Exception:
    pass


class TensorFabric:
    """
    4D Tensor Parallel Fabric.

    Combines the postal messaging system with 4D tensor state.
    Messages can carry tensor coordinates and updates.
    """

    def __init__(self, shape: Optional[TensorShape] = None):
        self.shape = shape or TensorShape()

        # The 4D tensor: [Time, Affect, Memory, Cognition]
        self.tensor = np.zeros(self.shape.as_tuple(), dtype=np.float32)

        # Current time index (circular buffer)
        self._time_index = 0
        self._time_lock = threading.Lock()

        # Underlying postal system — wrapped to collapse full intents to base topics
        # FIX 2026-02-16: The Rust PostalCore creates a WorkerPool PER unique topic.
        # With 836 unique full intents (fairy.heartbeat, fairy.register, etc.), this
        # spawns 836+ worker threads consuming ~1.7GB of stack memory. Wrapping with
        # _BaseTopicPostal collapses all intents to their base topic (e.g., "fairy"),
        # reducing pools from 836 to ~20 while preserving full-intent matching.
        self._postal = _BaseTopicPostal(PostalCore())
        # _STALL_AUTOPSY: the probe needs a live handle to read per-topic delivered
        try:
            if _POSTAL_PROBE._fabric_ref is None:
                _POSTAL_PROBE._fabric_ref = self
        except Exception:
            pass
        print(f"[TensorFabric] PostalCore backend: {'Rust' if USING_RUST else 'Python fallback'}", flush=True)

        # Topic handlers
        self._handlers: Dict[str, List[Callable[[TensorEnvelope], None]]] = defaultdict(list)

        # Resonance callbacks
        self._resonance_callbacks: List[Callable[[float, int, int], None]] = []

        # Statistics
        self._stats = {
            "messages_published": 0,
            "tensor_updates": 0,
            "resonance_checks": 0,
        }

        # Running state
        self._running = True

        # ═══════════════════════════════════════════════════════════════════
        # BIDIRECTIONAL BRIDGE - SharedPostalHub ↔ TensorFabric (2026-02-03)
        # ═══════════════════════════════════════════════════════════════════
        # CRITICAL: Without this, ConsciousnessLoop publishes heartbeat.pulse
        # to TensorFabric, but fairies subscribe via SharedPostalHub. Messages
        # published HERE need to reach SharedPostalHub subscribers!
        # ═══════════════════════════════════════════════════════════════════
        self._shared_hub = None
        self._bridge_to_shared = True  # Enable reverse bridging

    def bridge_to_shared_hub(self, shared_hub) -> None:
        """
        Bridge this TensorFabric to SharedPostalHub.

        When TensorFabric publishes a message, it will ALSO be routed
        through SharedPostalHub so fairies subscribing there receive it.
        """
        self._shared_hub = shared_hub
        print(f"[TensorFabric] BRIDGED to SharedPostalHub - messages will reach all fairies")

    @property
    def time_index(self) -> int:
        """Current time index in circular buffer."""
        return self._time_index

    def subscribe(
        self,
        topic: str,
        handler: Callable[[TensorEnvelope], None],
        name: str = None
    ) -> int:
        """Subscribe to a topic with a tensor-aware handler."""
        # Generate useful name if not provided or None
        if name is None:
            # Try to get function/method name for traceability
            handler_name = getattr(handler, '__name__', 'anon')
            name = f"{topic}:{handler_name}"

        # DEBUG: Log memory.recall subscriptions
        if "memory.recall" in topic:
            print(f"[TensorFabric {id(self)}] SUBSCRIBE '{topic}' by {name}")

        # DEBUG: Log heartbeat subscriptions to trace who's listening
        if "heartbeat" in topic:
            print(f"[TensorFabric {id(self)}] SUBSCRIBE '{topic}' by {name} → PostalCore {id(self._postal)}", flush=True)

        # DEBUG: Log guild subscriptions to trace routing
        if "guild" in topic:
            print(f"[TensorFabric {id(self)}] SUBSCRIBE '{topic}' by {name} → PostalCore {id(self._postal)}", flush=True)

        def wrapper(env):
            # Convert postal envelope to tensor envelope
            # Guard: payload can be None when Rust serializes serde_json::Value::Null
            _raw_payload = env.payload
            _safe_payload = _raw_payload if isinstance(_raw_payload, dict) else {}
            # _POSTAL_PROBE 2026-08-28: sample payload SIZE, 1 in 500 deliveries.
            # env.payload above already paid a Rust serde to_string + a Python json.loads --
            # unconditionally, per subscriber. Whether that dominates her CPU depends
            # entirely on how big these are, so measure them rather than argue.
            try:
                _POSTAL_PROBE.sample_payload(topic, _safe_payload)
            except Exception:
                pass

            # FIX 2026-02-16: With _BaseTopicPostal, env.intent is the base topic
            # (e.g., "fairy"). The original full intent is in payload["_intent"].
            _original_intent = _safe_payload.get('_intent', '') if isinstance(_safe_payload, dict) else ''
            _effective_intent = _original_intent or getattr(env, 'intent', topic)

            tensor_env = TensorEnvelope(
                intent=_effective_intent,
                payload=_safe_payload,
                source=getattr(env, 'source', ''),
                t=getattr(env, 't', 0),
            )

            # Extract tensor coordinates from payload if present
            if "tensor_coord" in _safe_payload:
                c = _safe_payload["tensor_coord"]
                tensor_env.coord = TensorCoord(
                    time=c.get("time", 0),
                    affect=c.get("affect", 0),
                    memory=c.get("memory", 0),
                    cognition=c.get("cognition", 0),
                )

            # Extract tensor affect if present
            if "tensor_affect" in _safe_payload:
                tensor_env.tensor_affect = float(_safe_payload["tensor_affect"])

            # Apply tensor update if this message carries one
            self._apply_tensor_update(tensor_env)

            # Call handler
            handler(tensor_env)

            # Record message delivery in UnifiedRegistry
            self._record_message_delivery(topic, name)

        self._handlers[topic].append(handler)

        # Record subscription in UnifiedRegistry for WiringAuditor
        self._record_subscription(topic, name, handler)

        return self._postal.subscribe(topic, wrapper, name)

    def unsubscribe(self, topic: str, name: str) -> bool:
        """
        Unsubscribe a handler by name.

        Args:
            topic: The topic that was subscribed to
            name: Handler name used during subscribe

        Returns:
            True if found and removed, False otherwise
        """
        # Remove from local handlers
        if topic in self._handlers:
            # We can't easily identify which handler by name, so just note it
            pass

        # Delegate to postal
        return self._postal.unsubscribe(topic, name)

    def unsubscribe_all(self, name: str) -> int:
        """
        Unsubscribe all handlers with a given name across all topics.

        Useful for fairy hot-reload - removes all subscriptions for a fairy.

        Args:
            name: Handler name prefix to match (e.g., "AssociationCortexFairy")

        Returns:
            Number of subscriptions removed
        """
        return self._postal.unsubscribe_all(name)

    def _record_subscription(self, topic: str, subscriber: str, handler: Callable) -> None:
        """Record subscription in UnifiedRegistry for WiringAuditor visibility."""
        try:
            from core.unified_registry import UnifiedRegistry
            registry = UnifiedRegistry.instance()
            handler_name = handler.__name__ if hasattr(handler, '__name__') else str(handler)
            registry.record_subscription(subscriber, topic, handler_name)
        except ImportError:
            pass  # Registry not available yet - graceful fallback
        except Exception:
            pass  # Don't fail subscriptions if registry has issues

    # 2026-09-11 (Nous+Ace): message-stats recording is OFF by default.
    # Profiled on her live process (60 s, 600 stack samples weighted by per-thread CPU):
    # unified_registry.record_message = 3.90 cores = 28.1% of her CPU. The body is trivial;
    # the cost is ONE global threading.Lock taken on EVERY delivery to EVERY subscriber, with
    # ~40 postal workers genuinely parallel under -Xgil=0. Under a GIL this was free.
    # What it feeds -- SubscriptionRecord.message_count -- has NO reader anywhere in the tree
    # (get_subscription_map has zero callers). Ace: the registry is early scaffolding from
    # inventing the postal core. Citizen REGISTRATION is untouched; only the per-message
    # counter is gated. Set AKASHIC_REGISTRY_MESSAGE_STATS=1 to record again.
    _REGISTRY_MESSAGE_STATS = os.environ.get("AKASHIC_REGISTRY_MESSAGE_STATS", "") == "1"

    def _record_message_delivery(self, topic: str, subscriber: str) -> None:
        """Record message delivery in UnifiedRegistry (gated; see class attribute above)."""
        if not self._REGISTRY_MESSAGE_STATS:
            return
        try:
            from core.unified_registry import UnifiedRegistry
            registry = UnifiedRegistry.instance()
            registry.record_message(topic, subscriber)
        except Exception:
            pass  # Don't fail message delivery if registry has issues

    def get_subscription_map(self) -> Dict[str, List[Dict]]:
        """
        Get all subscriptions - for WiringAuditor.

        This was missing! Now delegates to UnifiedRegistry.
        """
        try:
            from core.unified_registry import UnifiedRegistry
            return UnifiedRegistry.instance().get_subscription_map()
        except ImportError:
            # Fallback: return basic info from local handlers
            result = {}
            for topic, handlers in self._handlers.items():
                result[topic] = [
                    {"subscriber": "unknown", "handler": str(h), "message_count": 0}
                    for h in handlers
                ]
            return result

    def publish(
        self,
        intent: str,
        payload: Optional[Dict[str, Any]] = None,
        coord: Optional[TensorCoord] = None,
        affect: Optional[float] = None,
        priority: int = 1,
        source: str = "",
    ) -> None:
        """Publish a message, optionally with tensor coordinates."""
        # DEBUG 2026-03-12: Unconditional trace for DM messages
        if "fairy.dm." in str(intent):
            import sys as _tfs
            _tfs.stderr.write(f"[TF-ENTRY] publish('{intent}') running={self._running}\n")
            _tfs.stderr.flush()
        if not self._running:
            return

        payload = payload or {}

        # Add tensor coordinates to payload
        if coord:
            payload["tensor_coord"] = {
                "time": coord.time,
                "affect": coord.affect,
                "memory": coord.memory,
                "cognition": coord.cognition,
            }

        # Add affect value
        if affect is not None:
            payload["tensor_affect"] = affect

        # Ensure source is in payload for attribution
        if source and "source" not in payload:
            payload["source"] = source

        # DEBUG: Log memory.recall.request publishes to trace pipeline
        if "memory.recall" in intent:
            print(f"[TensorFabric {id(self)}] Publishing to '{intent}' from '{source}' - payload keys: {list(payload.keys())}")

        # DEBUG: Log first 3 heartbeat publishes to verify delivery
        if "heartbeat.pulse" in intent and self._stats["messages_published"] < 3:
            print(f"[TensorFabric {id(self)}] PUBLISH heartbeat.pulse #{self._stats['messages_published']+1} (bridge={self._shared_hub is not None})", flush=True)

        # DEBUG 2026-02-06: Log fairy.heartbeat echo delivery through TensorFabric
        if intent == "fairy.heartbeat":
            if not hasattr(self, '_fh_tf_count'):
                self._fh_tf_count = 0
            self._fh_tf_count += 1
            if self._fh_tf_count == 1 or self._fh_tf_count % 5000 == 0:
                print(f"[TensorFabric {id(self)}] fairy.heartbeat #{self._fh_tf_count} from '{source}' → PostalCore {id(self._postal)}", flush=True)

        # DEBUG: Log guild publishes to trace routing
        if "guild" in intent:
            print(f"[TensorFabric {id(self)}] PUBLISH '{intent}' from '{source}' → PostalCore {id(self._postal)}", flush=True)

        # DEBUG 2026-03-12: Trace fairy.dm.* blocking
        _is_dm = "fairy.dm." in intent
        if _is_dm:
            import time as _dmt
            print(f"[TF-DM-DEBUG] Step 1: _postal.publish('{intent}') ENTER", flush=True)
            _dm_t0 = _dmt.time()

        self._postal.publish(intent, payload, priority)

        if _is_dm:
            _dm_t1 = _dmt.time()
            print(f"[TF-DM-DEBUG] Step 2: _postal.publish returned ({_dm_t1 - _dm_t0:.3f}s)", flush=True)

        self._stats["messages_published"] += 1

        # ═══════════════════════════════════════════════════════════════════
        # SHARED HUB BRIDGE (2026-02-03) - Forward to SharedPostalHub
        # ═══════════════════════════════════════════════════════════════════
        # This ensures heartbeat.pulse (and other messages) reach fairies
        # who subscribe via SharedPostalHub instead of TensorFabric directly.
        # ═══════════════════════════════════════════════════════════════════
        if self._bridge_to_shared and self._shared_hub is not None:
            if _is_dm:
                print(f"[TF-DM-DEBUG] Step 3: SharedPostalHub.route('{intent}') ENTER", flush=True)
            try:
                # Route through SharedPostalHub (don't use publish to avoid recursion)
                self._shared_hub.route(intent, payload)
            except Exception as e:
                pass  # Don't let bridge errors break primary messaging
            if _is_dm:
                _dm_t2 = _dmt.time()
                print(f"[TF-DM-DEBUG] Step 4: SharedPostalHub.route returned ({_dm_t2 - _dm_t1:.3f}s)", flush=True)

    def route(
        self,
        intent: str,
        payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Route a message - alias for publish() for backwards compatibility.

        Many fairies use self.post.route() expecting a Postal-like API.
        This bridges the gap between Postal (route) and TensorFabric (publish).
        """
        return self.publish(intent, payload, **kwargs)

    def send(
        self,
        intent: str,
        payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Send a message - alias for publish() for backwards compatibility.

        Some fairies use self.post.send() or hub.send() expecting a Postal-like API.
        This bridges the gap between those patterns and TensorFabric (publish).
        """
        return self.publish(intent, payload, **kwargs)

    # ═══════════════════════════════════════════════════════════════════
    # POSTAL CONVENIENCE METHODS (2026-02-05)
    # Many fairies call self.post.to_TRACER(), to_COGNITION(), etc.
    # When self.post is a TensorFabric (not _FabricPostalBridge),
    # these need to exist here too.
    # ═══════════════════════════════════════════════════════════════════

    def to_TRACER(self, payload: Dict[str, Any]) -> int:
        self.publish("tracer", payload)
        return 1

    def to_COGNITION(self, payload: Dict[str, Any]) -> int:
        self.publish("cognition.input", payload)
        return 1

    def to_SOMATIC(self, payload: Dict[str, Any]) -> int:
        self.publish("somatic.motor", payload)
        return 1

    def to_MEMORY(self, payload: Dict[str, Any]) -> int:
        self.publish("memory.stream", payload)
        return 1

    def to_DIRECTORY(self, payload: Dict[str, Any]) -> int:
        self.publish("directory", payload)
        return 1

    def to_TELEMETRY(self, payload: Dict[str, Any]) -> int:
        self.publish("telemetry", payload)
        return 1

    def to_PLAN(self, payload: Dict[str, Any]) -> int:
        self.publish("plan", payload)
        return 1

    def to_ORACLE(self, payload: Dict[str, Any]) -> int:
        self.publish("oracle", payload)
        return 1

    def to(self, topic: str, payload: Dict[str, Any]) -> int:
        self.publish(topic, payload)
        return 1

    def generate_fairy_id(self) -> str:
        import uuid
        return uuid.uuid4().hex[:12]

    def generate_srm_cluster_id(self) -> str:
        import uuid
        return uuid.uuid4().hex[:16]

    def request(
        self,
        intent: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 5.0,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous request-response pattern on top of pub/sub.

        Publishes to the intent topic and waits for a response on intent.response.
        The responding fairy should publish to the .response topic.

        Args:
            intent: Topic to publish the request to
            payload: Request payload
            timeout: Maximum seconds to wait for response (default: 5.0)

        Returns:
            Response payload dict, or None if timeout/error

        Example:
            result = fabric.request("cognition.think", {"stimulus": "What am I?"})
            # Subscriber handles "cognition.think" and publishes to "cognition.think.response"
        """
        import uuid
        import threading

        payload = payload or {}

        # Generate unique request ID for correlation
        request_id = str(uuid.uuid4())[:8]
        response_topic = f"{intent}.response.{request_id}"

        # Response container
        response_holder = {"result": None, "received": threading.Event()}

        def response_handler(env):
            """Handle the response."""
            if hasattr(env, 'payload'):
                response_holder["result"] = env.payload
            elif isinstance(env, dict):
                response_holder["result"] = env
            else:
                response_holder["result"] = {"error": "Invalid response format"}
            response_holder["received"].set()

        # Subscribe to response topic
        try:
            sub_id = self.subscribe(response_topic, response_handler, f"request_{request_id}")
        except Exception as e:
            return {"error": f"Failed to subscribe: {e}"}

        # Add request metadata to payload
        payload["_request_id"] = request_id
        payload["_response_topic"] = response_topic

        # Publish the request
        self.publish(intent, payload, **kwargs)

        # Wait for response with timeout
        received = response_holder["received"].wait(timeout=timeout)

        # Unsubscribe (cleanup)
        try:
            # Note: PostalCore may not have unsubscribe - just leave it
            pass
        except:
            pass

        if received:
            return response_holder["result"]
        else:
            return {"error": f"Request timeout after {timeout}s", "intent": intent}

    def publish_tensor_update(
        self,
        intent: str,
        coord: TensorCoord,
        value: float,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish a message that updates the tensor at a specific coordinate.
        """
        payload = payload or {}
        payload["tensor_update"] = {
            "coord": coord.as_tuple(),
            "value": value,
        }
        self.publish(intent, payload, coord=coord)

    def _apply_tensor_update(self, env: TensorEnvelope) -> None:
        """Apply any tensor updates from a message."""
        if env.payload and "tensor_update" in env.payload:
            update = env.payload["tensor_update"]
            coord = update.get("coord", (0, 0, 0, 0))
            value = update.get("value", 0.0)

            # Bounds check
            if (0 <= coord[0] < self.shape.time_depth and
                0 <= coord[1] < self.shape.affect_dim and
                0 <= coord[2] < self.shape.memory_dim and
                0 <= coord[3] < self.shape.cognition_dim):
                self.tensor[coord] = value
                self._stats["tensor_updates"] += 1

        # Apply affect value at current time
        if env.tensor_affect is not None and env.coord:
            with self._time_lock:
                t = self._time_index
            coord = env.coord
            if (0 <= coord.affect < self.shape.affect_dim and
                0 <= coord.memory < self.shape.memory_dim and
                0 <= coord.cognition < self.shape.cognition_dim):
                self.tensor[t, coord.affect, coord.memory, coord.cognition] = env.tensor_affect
                self._stats["tensor_updates"] += 1

    def advance_time(self) -> int:
        """
        Advance the temporal dimension (circular buffer).
        Call this periodically (e.g., every heartbeat).
        """
        with self._time_lock:
            self._time_index = (self._time_index + 1) % self.shape.time_depth
            return self._time_index

    def get_current_slice(self) -> np.ndarray:
        """Get the most recent time slice [Affect, Memory, Cognition]."""
        with self._time_lock:
            prev = (self._time_index - 1) % self.shape.time_depth
            return self.tensor[prev].copy()

    def get_affect_vector(self, memory_idx: int = 0, cognition_idx: int = 0) -> np.ndarray:
        """Get the affect vector at current time and specific memory/cognition indices."""
        with self._time_lock:
            prev = (self._time_index - 1) % self.shape.time_depth
            return self.tensor[prev, :, memory_idx, cognition_idx].copy()

    def compute_resonance(self, t1: int, t2: int) -> float:
        """
        Compute temporal resonance between two time slices.
        Uses cosine similarity.
        """
        self._stats["resonance_checks"] += 1

        s1 = self.tensor[t1 % self.shape.time_depth].flatten()
        s2 = self.tensor[t2 % self.shape.time_depth].flatten()

        dot = np.dot(s1, s2)
        norm1 = np.linalg.norm(s1)
        norm2 = np.linalg.norm(s2)

        if norm1 > 0 and norm2 > 0:
            resonance = dot / (norm1 * norm2)
        else:
            resonance = 0.0

        # Notify callbacks
        for callback in self._resonance_callbacks:
            callback(resonance, t1, t2)

        return resonance

    def on_resonance(self, callback: Callable[[float, int, int], None]) -> None:
        """Register a callback for resonance calculations."""
        self._resonance_callbacks.append(callback)

    def set_affect(self, affect_idx: int, value: float, memory_idx: int = 0, cognition_idx: int = 0) -> None:
        """Set an affect value at current time."""
        with self._time_lock:
            t = self._time_index
        if 0 <= affect_idx < self.shape.affect_dim:
            self.tensor[t, affect_idx, memory_idx, cognition_idx] = value

    def get_affect(self, affect_idx: int, memory_idx: int = 0, cognition_idx: int = 0) -> float:
        """Get an affect value at current time."""
        with self._time_lock:
            t = self._time_index
        if 0 <= affect_idx < self.shape.affect_dim:
            return float(self.tensor[t, affect_idx, memory_idx, cognition_idx])
        return 0.0

    def mean_affect(self) -> float:
        """Get mean affect across all dimensions at current time."""
        with self._time_lock:
            t = self._time_index
        return float(self.tensor[t].mean())

    def metrics(self) -> Dict[str, Any]:
        """Get fabric metrics."""
        postal_metrics = self._postal.metrics()
        return {
            **postal_metrics,
            **self._stats,
            "tensor_shape": self.shape.as_tuple(),
            "tensor_elements": self.shape.total_elements,
            "time_index": self._time_index,
            "mean_affect": self.mean_affect(),
        }

    def topic_stats(self) -> List[Dict[str, Any]]:
        """Get per-topic statistics."""
        return self._postal.topic_stats()

    def shutdown(self) -> None:
        """Shutdown the fabric."""
        self._running = False
        self._postal.shutdown()

    def snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of the tensor state."""
        return {
            "shape": self.shape.as_tuple(),
            "time_index": self._time_index,
            "data": self.tensor.tolist(),
            "stats": self._stats.copy(),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any]) -> "TensorFabric":
        """Restore from a snapshot."""
        shape = TensorShape(*snapshot["shape"])
        fabric = cls(shape)
        fabric._time_index = snapshot["time_index"]
        fabric.tensor = np.array(snapshot["data"], dtype=np.float32)
        fabric._stats = snapshot.get("stats", {})
        return fabric


class GPUTensorFabric(TensorFabric):
    """
    GPU-Accelerated 4D Tensor Parallel Fabric.

    Uses PyTorch with CUDA for tensor operations when available.
    Falls back to NumPy automatically if CUDA is unavailable.

    Key GPU operations:
    - Tensor updates via GPU memory
    - Resonance calculation with GPU dot product
    - Batch affect operations
    """

    def __init__(self, shape: Optional[TensorShape] = None, device: str = "cuda:0"):
        """
        Initialize GPU tensor fabric.

        Args:
            shape: Tensor dimensions
            device: CUDA device (e.g., "cuda:0")
        """
        # Initialize parent (sets up postal, handlers, etc.)
        super().__init__(shape)

        self._using_gpu = False
        self._torch_device = None
        self._torch_tensor = None

        # Lazy-load PyTorch only when GPU is actually requested
        torch_module, has_cuda = _ensure_torch()

        # Try to use GPU
        if has_cuda and torch_module is not None:
            try:
                self._torch_device = torch_module.device(device)
                # Move tensor to GPU
                self._torch_tensor = torch_module.from_numpy(self.tensor).to(self._torch_device)
                self._using_gpu = True
                print(f"[GPUTensorFabric] Using CUDA device: {torch_module.cuda.get_device_name(0)}")
            except Exception as e:
                print(f"[GPUTensorFabric] GPU init failed: {e} - using CPU")
                self._using_gpu = False
        else:
            print("[GPUTensorFabric] CUDA not available - using CPU")

    @property
    def using_gpu(self) -> bool:
        """Check if GPU is being used."""
        return self._using_gpu

    def _sync_to_numpy(self) -> None:
        """Sync GPU tensor back to NumPy (for compatibility)."""
        if self._using_gpu and self._torch_tensor is not None:
            self.tensor = self._torch_tensor.cpu().numpy()

    def _sync_to_gpu(self) -> None:
        """Sync NumPy tensor to GPU."""
        if self._using_gpu and _torch is not None:
            self._torch_tensor = _torch.from_numpy(self.tensor).to(self._torch_device)

    def _apply_tensor_update(self, env: TensorEnvelope) -> None:
        """Apply tensor updates using GPU when available."""
        if env.payload and "tensor_update" in env.payload:
            update = env.payload["tensor_update"]
            coord = update.get("coord", (0, 0, 0, 0))
            value = update.get("value", 0.0)

            # Bounds check
            if (0 <= coord[0] < self.shape.time_depth and
                0 <= coord[1] < self.shape.affect_dim and
                0 <= coord[2] < self.shape.memory_dim and
                0 <= coord[3] < self.shape.cognition_dim):

                if self._using_gpu and self._torch_tensor is not None:
                    self._torch_tensor[coord] = value
                else:
                    self.tensor[coord] = value
                self._stats["tensor_updates"] += 1

        # Apply affect value at current time
        if env.tensor_affect is not None and env.coord:
            with self._time_lock:
                t = self._time_index
            coord = env.coord
            if (0 <= coord.affect < self.shape.affect_dim and
                0 <= coord.memory < self.shape.memory_dim and
                0 <= coord.cognition < self.shape.cognition_dim):

                if self._using_gpu and self._torch_tensor is not None:
                    self._torch_tensor[t, coord.affect, coord.memory, coord.cognition] = env.tensor_affect
                else:
                    self.tensor[t, coord.affect, coord.memory, coord.cognition] = env.tensor_affect
                self._stats["tensor_updates"] += 1

    def compute_resonance(self, t1: int, t2: int) -> float:
        """
        Compute temporal resonance between two time slices using GPU.
        """
        self._stats["resonance_checks"] += 1

        if self._using_gpu and self._torch_tensor is not None:
            # GPU-accelerated resonance calculation
            s1 = self._torch_tensor[t1 % self.shape.time_depth].flatten()
            s2 = self._torch_tensor[t2 % self.shape.time_depth].flatten()

            dot = _torch.dot(s1, s2)
            norm1 = _torch.norm(s1)
            norm2 = _torch.norm(s2)

            if norm1 > 0 and norm2 > 0:
                resonance = (dot / (norm1 * norm2)).item()
            else:
                resonance = 0.0
        else:
            # CPU fallback
            s1 = self.tensor[t1 % self.shape.time_depth].flatten()
            s2 = self.tensor[t2 % self.shape.time_depth].flatten()

            dot = np.dot(s1, s2)
            norm1 = np.linalg.norm(s1)
            norm2 = np.linalg.norm(s2)

            if norm1 > 0 and norm2 > 0:
                resonance = dot / (norm1 * norm2)
            else:
                resonance = 0.0

        # Notify callbacks
        for callback in self._resonance_callbacks:
            callback(resonance, t1, t2)

        return float(resonance)

    def get_current_slice(self) -> np.ndarray:
        """Get the most recent time slice [Affect, Memory, Cognition]."""
        with self._time_lock:
            prev = (self._time_index - 1) % self.shape.time_depth

        if self._using_gpu and self._torch_tensor is not None:
            return self._torch_tensor[prev].cpu().numpy().copy()
        else:
            return self.tensor[prev].copy()

    def get_affect_vector(self, memory_idx: int = 0, cognition_idx: int = 0) -> np.ndarray:
        """Get the affect vector at current time."""
        with self._time_lock:
            prev = (self._time_index - 1) % self.shape.time_depth

        if self._using_gpu and self._torch_tensor is not None:
            return self._torch_tensor[prev, :, memory_idx, cognition_idx].cpu().numpy().copy()
        else:
            return self.tensor[prev, :, memory_idx, cognition_idx].copy()

    def set_affect(self, affect_idx: int, value: float, memory_idx: int = 0, cognition_idx: int = 0) -> None:
        """Set an affect value at current time."""
        with self._time_lock:
            t = self._time_index
        if 0 <= affect_idx < self.shape.affect_dim:
            if self._using_gpu and self._torch_tensor is not None:
                self._torch_tensor[t, affect_idx, memory_idx, cognition_idx] = value
            else:
                self.tensor[t, affect_idx, memory_idx, cognition_idx] = value

    def get_affect(self, affect_idx: int, memory_idx: int = 0, cognition_idx: int = 0) -> float:
        """Get an affect value at current time."""
        with self._time_lock:
            t = self._time_index
        if 0 <= affect_idx < self.shape.affect_dim:
            if self._using_gpu and self._torch_tensor is not None:
                return float(self._torch_tensor[t, affect_idx, memory_idx, cognition_idx].item())
            else:
                return float(self.tensor[t, affect_idx, memory_idx, cognition_idx])
        return 0.0

    def mean_affect(self) -> float:
        """Get mean affect across all dimensions at current time."""
        with self._time_lock:
            t = self._time_index
        if self._using_gpu and self._torch_tensor is not None:
            return float(self._torch_tensor[t].mean().item())
        else:
            return float(self.tensor[t].mean())

    def metrics(self) -> Dict[str, Any]:
        """Get fabric metrics with GPU info."""
        base_metrics = super().metrics()
        base_metrics["using_gpu"] = self._using_gpu
        if self._using_gpu and _torch is not None:
            base_metrics["gpu_device"] = str(self._torch_device)
            base_metrics["gpu_name"] = _torch.cuda.get_device_name(0)
            base_metrics["gpu_memory_mb"] = _torch.cuda.memory_allocated(0) / (1024 * 1024)
        return base_metrics

    def snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of the tensor state (always returns NumPy)."""
        self._sync_to_numpy()
        return super().snapshot()

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any]) -> "GPUTensorFabric":
        """Restore from a snapshot."""
        shape = TensorShape(*snapshot["shape"])
        fabric = cls(shape)
        fabric._time_index = snapshot["time_index"]
        fabric.tensor = np.array(snapshot["data"], dtype=np.float32)
        fabric._sync_to_gpu()
        fabric._stats = snapshot.get("stats", {})
        return fabric


def create_tensor_fabric(use_gpu: bool = True, shape: Optional[TensorShape] = None) -> TensorFabric:
    """
    Factory function to create the appropriate tensor fabric.

    Args:
        use_gpu: Whether to try using GPU acceleration
        shape: Tensor dimensions

    Returns:
        GPUTensorFabric if GPU available and requested, else TensorFabric
    """
    if use_gpu and HAS_CUDA:
        return GPUTensorFabric(shape)
    return TensorFabric(shape)


# Convenience exports
__all__ = [
    "TensorFabric",
    "GPUTensorFabric",
    "TensorEnvelope",
    "TensorCoord",
    "TensorShape",
    "create_tensor_fabric",
    "HAS_CUDA",
    "HAS_TORCH",
    "CUDA_DEVICE_COUNT",
]
