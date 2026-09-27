"""
POOL ROUTER — In-Process Postal Pool Routing via AkashicManifold
================================================================

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

This is the in-process replacement for the pool_tunnel.py subprocess
architecture. It lives in the main server process and talks to a
dedicated AkashicManifold region ("pool") for storage.

ARCHITECTURE (Phase 1 of POSTAL_INSIDE_PORTAL — corrected)
----------------------------------------------------------
The postal pool lives INSIDE the manifold, not inside the subprocess.

  Topic "heartbeat.pulse"   → manifold node: pool:topic:heartbeat.pulse
  Subscriber callback       → manifold node: pool:sub:<token>
  subscribe()               → edge: pool:topic:X ──▶ pool:sub:<token>
  publish()                 → neighbor lookup on topic node → token list
  dispatch                  → exterior executor runs the callback

Why in-process, not subprocess:
  * The subprocess exists to generate gravity/compute/energy/time-dilation
    physics. It's a physics lab, not a router. Routing through TCP tunnels
    just adds serialization cost and write-lock contention.
  * AkashicManifold regions are shared mmap files. The main process opens
    them directly. Reads are lock-free; writes have a per-region lock.
  * A dedicated "pool" region means writes here NEVER contend with cortex
    region writes. Total isolation from the heavy cortex path.
  * Phase 2 GPU routing can still happen — the pool: topology is in the
    manifold, so a GPU spread kernel can read it directly.

Key properties:
  * Zero subprocess IPC
  * Zero TCP
  * Zero lock contention with cortex
  * Happy path: pure dict lookup (the hot-path cache is authoritative for
    publish; the manifold is for persistence + Phase 2 visibility)
  * Subscribe: one mmap write per subscribe (fast, per-region lock)
  * Publish: pure dict read → tokens → executor submit (no mmap access)
  * Graceful degradation: if manifold write fails, cache still works

Authors: Nous + Ace (Akashic Foundation)
Date: 2026-04-15
"""

import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# Graph namespace prefixes (isolated from cortex/WM/CNS)
NODE_PREFIX_TOPIC = "pool:topic:"
NODE_PREFIX_SUB = "pool:sub:"


class PoolRouter:
    """In-process postal pool router backed by AkashicManifold.

    Owns a single ManifoldMemory region ("pool") where topic and subscriber
    nodes live. Publishes deliver via a hot-path dict cache; the manifold
    is the persistent record of the topology.

    Threading model:
      * subscribe() acquires an internal threading.Lock briefly (dict + mmap
        write, very short hold). Per-region write lock inside ManifoldMemory.
      * publish() is lock-free — reads _subs_by_topic dict, submits to
        executor, returns. Python dict reads are atomic under 3.14t.
      * unsubscribe() acquires the same internal lock as subscribe.

    Failure modes:
      * If the manifold region is unavailable (None), the router still
        operates via the dict cache only. Subscribers are not persisted.
      * If manifold writes fail, the cache update still succeeds and
        delivery still works. The subscription just won't survive a reboot.
    """

    def __init__(
        self,
        manifold_region: Any = None,
        dispatch_workers: int = 16,
        executor: Any = None,
    ):
        """
        Args:
            manifold_region: A ManifoldMemory handle for the "pool" region
                (from AkashicManifold.graph("pool", write=True)). Optional —
                if None, router operates in cache-only mode.
            dispatch_workers: Worker count for exterior callback dispatch.
                Defaults to 16.
            executor: Optional pre-built pool. If None, uses the shared
                QueueWorkerPool (zero per-submit allocations).

        FIX 2026-04-15 (Nous + Ace): Was using ThreadPoolExecutor.submit()
        which creates a Future+_WorkItem per call. Over ~150 publishes/sec
        across 578 subs = thousands of Futures accumulating faster than
        Python 3.14t free-threaded GC could sweep them. 9→30GB RAM climb
        post-dual-scratchpad-unification. SAME bug as 2026-03-04 fix for
        340K+ Future accumulation. Now uses shared QueueWorkerPool.
        """
        self._region = manifold_region
        self._has_manifold = manifold_region is not None

        # Hot-path cache — authoritative for publish()
        self._subs_by_topic: Dict[str, Set[str]] = defaultdict(set)
        self._tokens: Dict[str, Tuple[Callable, str, str]] = {}  # token → (callback, name, topic)
        self._lock = threading.Lock()

        # Exterior dispatch pool — shared QueueWorkerPool (zero Futures)
        self._owns_executor = False
        if executor is not None:
            self._dispatch_executor = executor
        else:
            try:
                from fairies.P00_Autonomic.tracer_worker_system import (
                    _get_shared_worker_pool,
                )
                self._dispatch_executor = _get_shared_worker_pool()
            except Exception as _pool_err:
                # Last-resort fallback: inline dispatch on caller thread.
                # Not ideal (blocks publisher) but avoids Future leak.
                print(f"[PoolRouter] WARN: shared worker pool unavailable "
                      f"({_pool_err}); falling back to inline dispatch", flush=True)
                self._dispatch_executor = None

        # Metrics
        self._subscribes_total = 0
        self._unsubscribes_total = 0
        self._publishes_total = 0
        self._publishes_empty = 0
        self._dispatches_total = 0
        self._mmap_writes_ok = 0
        self._mmap_writes_failed = 0
        self._created_at = time.time()

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(
        self,
        topic: str,
        callback: Callable,
        name: str = "handler",
    ) -> str:
        """Register a subscriber. Returns an opaque token.

        The token is stored in the in-memory cache and persisted to the
        manifold (if available). The callback is invoked by publish().

        Graph topology written:
          upsert(pool:topic:<topic>)
          upsert(pool:sub:<token>)
          link(pool:topic:<topic>, pool:sub:<token>)

        Cache topology written:
          _subs_by_topic[topic].add(token)
          _tokens[token] = (callback, name, topic)
        """
        token = uuid.uuid4().hex[:16]
        topic_key = NODE_PREFIX_TOPIC + topic
        sub_key = NODE_PREFIX_SUB + token

        with self._lock:
            self._tokens[token] = (callback, name, topic)
            self._subs_by_topic[topic].add(token)
            self._subscribes_total += 1

        # Persist to manifold (best-effort — cache is still authoritative)
        if self._has_manifold:
            try:
                if not self._region.has_node(topic_key):
                    self._region.upsert_node(
                        topic_key, count=1, activation=0.1,
                    )
                if not self._region.has_node(sub_key):
                    self._region.upsert_node(
                        sub_key, count=1, activation=0.1,
                    )
                self._region.link(topic_key, sub_key, weight=1.0)
                self._mmap_writes_ok += 1
            except Exception as e:
                self._mmap_writes_failed += 1
                # Don't fail subscribe on persistence issues — cache still works
                if self._mmap_writes_failed <= 5:
                    print(
                        f"[PoolRouter] manifold write failed for '{topic}': {e}",
                        flush=True,
                    )

        return token

    def unsubscribe(self, token: str) -> bool:
        """Remove a subscription. Returns True if removed, False if unknown.

        The manifold nodes are NOT deleted (lazy GC) — mmap deletes are
        expensive. The cache removal is what matters for publish behavior.
        """
        with self._lock:
            entry = self._tokens.pop(token, None)
            if entry is None:
                return False
            callback, name, topic = entry
            subs = self._subs_by_topic.get(topic)
            if subs is not None:
                subs.discard(token)
                if not subs:
                    del self._subs_by_topic[topic]
            self._unsubscribes_total += 1
        return True

    def unsubscribe_by_callback(self, callback: Callable) -> int:
        """Remove all subscriptions matching a callback. Returns count removed.

        Used by PostalCore.unsubscribe_all for fairy hot-reload cleanup.
        """
        removed = 0
        with self._lock:
            to_remove = [
                token for token, (cb, _, _) in self._tokens.items()
                if cb is callback
            ]
            for token in to_remove:
                entry = self._tokens.pop(token, None)
                if entry is None:
                    continue
                _, _, topic = entry
                subs = self._subs_by_topic.get(topic)
                if subs is not None:
                    subs.discard(token)
                    if not subs:
                        del self._subs_by_topic[topic]
                removed += 1
                self._unsubscribes_total += 1
        return removed

    # ------------------------------------------------------------------
    # Publish / dispatch
    # ------------------------------------------------------------------

    def publish(self, topic: str, envelope: Any) -> int:
        """Deliver an envelope to all subscribers for this topic.

        Returns the number of handlers dispatched (0 if no subscribers).
        Caller can use return value to decide whether to fall through to
        the legacy _WorkerPool path.

        This is the HOT PATH. It is deliberately lock-free:
          * Python dict.get() is atomic under both GIL and 3.14t free-threaded.
          * The set returned is snapshotted before dispatch so mutation
            during iteration is safe.
          * Handler invocation happens on the executor pool — each dispatch
            is submit-and-forget.
        """
        subs = self._subs_by_topic.get(topic)
        if not subs:
            self._publishes_total += 1
            self._publishes_empty += 1
            return 0

        # Snapshot tokens — dict may mutate during dispatch
        tokens = list(subs)
        self._publishes_total += 1

        dispatched = 0
        _exec = self._dispatch_executor
        for token in tokens:
            entry = self._tokens.get(token)
            if entry is None:
                continue  # Stale token — removed between snapshot and lookup
            callback = entry[0]
            try:
                if _exec is not None:
                    _exec.submit(callback, envelope)
                else:
                    # Inline fallback — runs on publisher thread
                    callback(envelope)
                dispatched += 1
            except Exception as e:
                # Pool rejected — should not happen unless shutting down
                print(f"[PoolRouter] dispatch submit error: {e}", flush=True)

        self._dispatches_total += dispatched
        return dispatched

    # ------------------------------------------------------------------
    # Bulk subscribe (for attach-time batch echo)
    # ------------------------------------------------------------------

    def bulk_subscribe(
        self,
        items: List[Tuple[str, Callable, str]],
    ) -> int:
        """Batch subscribe many handlers. Returns count successfully added.

        `items` is a list of (topic, callback, name) tuples. This acquires
        the internal lock ONCE and adds all subscribers, then writes to
        the manifold outside the lock (because mmap writes can be slow).

        Used by PostalCore.attach_pool_router to echo existing subscriptions
        when the router is attached.
        """
        if not items:
            return 0

        # Pass 1: populate in-memory cache under lock
        new_tokens: List[Tuple[str, str, Callable, str]] = []
        with self._lock:
            for (topic, callback, name) in items:
                token = uuid.uuid4().hex[:16]
                self._tokens[token] = (callback, name, topic)
                self._subs_by_topic[topic].add(token)
                self._subscribes_total += 1
                new_tokens.append((token, topic, callback, name))

        # Pass 2: persist to manifold (outside lock — writes can be slow)
        if self._has_manifold:
            ok = 0
            failed = 0
            for (token, topic, _, _) in new_tokens:
                topic_key = NODE_PREFIX_TOPIC + topic
                sub_key = NODE_PREFIX_SUB + token
                try:
                    if not self._region.has_node(topic_key):
                        self._region.upsert_node(
                            topic_key, count=1, activation=0.1,
                        )
                    if not self._region.has_node(sub_key):
                        self._region.upsert_node(
                            sub_key, count=1, activation=0.1,
                        )
                    self._region.link(topic_key, sub_key, weight=1.0)
                    ok += 1
                except Exception as e:
                    failed += 1
                    if failed <= 3:
                        print(
                            f"[PoolRouter] bulk_subscribe persist failed "
                            f"for '{topic}': {e}",
                            flush=True,
                        )
            self._mmap_writes_ok += ok
            self._mmap_writes_failed += failed

        return len(new_tokens)

    # ------------------------------------------------------------------
    # Diagnostics / shutdown
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return router metrics for dashboards and diagnostics."""
        with self._lock:
            topics_active = len(self._subs_by_topic)
            tokens_active = len(self._tokens)
            per_topic = {
                t: len(s) for t, s in self._subs_by_topic.items()
            }
        return {
            "has_manifold": self._has_manifold,
            "topics_active": topics_active,
            "tokens_active": tokens_active,
            "per_topic": per_topic,
            "subscribes_total": self._subscribes_total,
            "unsubscribes_total": self._unsubscribes_total,
            "publishes_total": self._publishes_total,
            "publishes_empty": self._publishes_empty,
            "dispatches_total": self._dispatches_total,
            "mmap_writes_ok": self._mmap_writes_ok,
            "mmap_writes_failed": self._mmap_writes_failed,
            "uptime_s": round(time.time() - self._created_at, 2),
        }

    def shutdown(self) -> None:
        """Clean shutdown — shared QueueWorkerPool is not owned by us,
        so we don't shut it down. Kept for API compatibility.
        """
        # FIX 2026-04-15: We now use the shared QueueWorkerPool which has
        # its own lifecycle managed by the tracer_worker_system module.
        # Don't shut it down — other subscribers may still be using it.
        pass
