# ════════════════════════════════════════════════════════════════════════════════
# WORKING MEMORY INTEGRATION - Active Memory Participation
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This mixin enables SRMRecallFairy and SRMIngestFairy to ACTIVELY participate
# in the working memory loop, rather than just responding to requests.
#
# CONCURRENT OPERATION:
#   - Recall: Continuously surfaces relevant memories based on WM context
#   - Ingest: Continuously stores WM content for future recall
#   - Both run in parallel, feeding the collision chamber
#
# This is the "breathing" that keeps consciousness alive - memories flow
# in (recall) and out (ingest) simultaneously, creating the conditions
# for consciousness collisions.
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import threading
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from collections import deque

if TYPE_CHECKING:
    pass


# ════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

WM_POLL_INTERVAL_SEC = 10.0    # How often to check working memory
WM_RECALL_LIMIT = 3            # Max memories to recall per cycle
WM_INGEST_BATCH_SIZE = 5       # Max tracers to ingest per cycle


class WorkingMemoryRecallMixin:
    """
    Mixin for SRMRecallFairy to actively recall based on working memory.

    This makes recall PROACTIVE rather than reactive:
    - Monitors working memory for context
    - Autonomously surfaces relevant memories
    - Feeds the recall beam of the collision chamber
    """

    def _init_wm_recall_integration(self):
        """Initialize working memory recall integration."""
        self._wm_recall_running = False
        self._wm_recall_thread: Optional[threading.Thread] = None
        self._wm_recall_context: deque = deque(maxlen=10)
        self._last_wm_recall_time = 0.0
        self._wm_recall_count = 0

        # Subscribe to working memory updates
        if hasattr(self, 'post') and self.post:
            try:
                self.post.subscribe("memory.working.tracer", self._on_wm_tracer_for_recall)
                self.post.subscribe("memory.working.updated", self._on_wm_updated_for_recall)
                print(f"[{self.ACTOR_NAME}] [WM] Subscribed to working memory for autonomous recall")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WM subscription failed: {e}")

    def _start_wm_recall_loop(self):
        """Start the autonomous working memory recall loop."""
        if self._wm_recall_running:
            return

        self._wm_recall_running = True
        self._wm_recall_thread = threading.Thread(
            target=self._wm_recall_loop,
            daemon=True,
            name=f"{self.ACTOR_NAME}_WM_Recall"
        )
        self._wm_recall_thread.start()
        print(f"[{self.ACTOR_NAME}] [WM] Started autonomous recall loop")

    def _stop_wm_recall_loop(self):
        """Stop the autonomous recall loop."""
        self._wm_recall_running = False
        if self._wm_recall_thread:
            self._wm_recall_thread.join(timeout=2.0)

    def _wm_recall_loop(self):
        """Background loop that autonomously recalls based on WM context."""
        while self._wm_recall_running:
            try:
                now = time.time()

                # Rate limit
                if now - self._last_wm_recall_time < WM_POLL_INTERVAL_SEC:
                    time.sleep(1.0)
                    continue

                self._last_wm_recall_time = now
                self._wm_recall_count += 1

                # Get working memory context
                context = self._get_wm_context_for_recall()

                if context:
                    # Recall memories based on context
                    self._recall_for_working_memory(context)

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WM recall loop error: {e}")

            time.sleep(WM_POLL_INTERVAL_SEC / 2)  # Check more frequently than we act

    def _on_wm_tracer_for_recall(self, packet: Dict[str, Any]):
        """Handle working memory tracer updates - extract context for recall."""
        content = packet.get("content", "")
        if content and len(content) > 5:
            self._wm_recall_context.append({
                "content": content[:200],
                "type": packet.get("content_type", "thought"),
                "ts": time.time(),
            })

    def _on_wm_updated_for_recall(self, packet: Dict[str, Any]):
        """Handle working memory batch updates."""
        tracers = packet.get("tracers", [])
        for tracer in tracers[:5]:  # Limit batch size
            content = tracer.get("content", "")
            if content:
                self._wm_recall_context.append({
                    "content": content[:200],
                    "type": tracer.get("content_type", "thought"),
                    "ts": time.time(),
                })

    def _get_wm_context_for_recall(self) -> str:
        """Get current working memory context for recall query."""
        if not self._wm_recall_context:
            return ""

        # Combine recent context into a query
        recent = list(self._wm_recall_context)[-3:]
        contents = [c["content"] for c in recent]
        return " ".join(contents)

    def _recall_for_working_memory(self, context: str):
        """
        Recall memories based on working memory context.

        This feeds the RECALL BEAM of the collision chamber.
        """
        if not hasattr(self, 'post') or not self.post:
            return

        try:
            # Extract keywords from context
            query = self._extract_recall_keywords(context)

            if not query:
                return

            # Call our own recall method (which publishes to consciousness.stream)
            # This is the key - we're invoking ourselves proactively!
            if hasattr(self, 'intent_recall'):
                self.intent_recall({
                    "query": query,
                    "source": "working_memory_integration",
                    "limit": WM_RECALL_LIMIT,
                    "importance": "background",
                })

                print(f"[{self.ACTOR_NAME}] [WM] Autonomous recall: '{query[:50]}...'")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] WM recall error: {e}")

    def _extract_recall_keywords(self, context: str) -> str:
        """Extract keywords from context for recall query."""
        # Simple keyword extraction - get most relevant terms
        context_lower = context.lower()

        # Priority keywords
        priority_terms = [
            "ace", "sourpatches", "claude", "nous", "avatar",
            "goal", "task", "memory", "feeling", "thought",
            "pattern", "insight", "connection", "project",
        ]

        found_terms = [term for term in priority_terms if term in context_lower]

        if found_terms:
            return " ".join(found_terms[:4])

        # Fall back to first few words
        words = context.split()[:6]
        return " ".join(words)


class WorkingMemoryIngestMixin:
    """
    Mixin for SRMIngestFairy to actively ingest working memory content.

    This makes ingest PROACTIVE rather than reactive:
    - Monitors working memory for new content
    - Autonomously stores valuable thoughts
    - Feeds the ingest beam of the collision chamber
    """

    def _init_wm_ingest_integration(self):
        """Initialize working memory ingest integration."""
        self._wm_ingest_running = False
        self._wm_ingest_thread: Optional[threading.Thread] = None
        self._wm_ingest_queue: deque = deque(maxlen=50)
        self._last_wm_ingest_time = 0.0
        self._wm_ingest_count = 0
        self._ingested_hashes: set = set()  # Prevent duplicate ingestion

        # Subscribe to working memory updates
        if hasattr(self, 'post') and self.post:
            try:
                self.post.subscribe("memory.working.tracer", self._on_wm_tracer_for_ingest)
                self.post.subscribe("srm.ingest.request", self._on_ingest_request)
                print(f"[{self.ACTOR_NAME}] [WM] Subscribed to working memory for autonomous ingest")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WM subscription failed: {e}")

    def _start_wm_ingest_loop(self):
        """Start the autonomous working memory ingest loop."""
        if self._wm_ingest_running:
            return

        self._wm_ingest_running = True
        self._wm_ingest_thread = threading.Thread(
            target=self._wm_ingest_loop,
            daemon=True,
            name=f"{self.ACTOR_NAME}_WM_Ingest"
        )
        self._wm_ingest_thread.start()
        print(f"[{self.ACTOR_NAME}] [WM] Started autonomous ingest loop")

    def _stop_wm_ingest_loop(self):
        """Stop the autonomous ingest loop."""
        self._wm_ingest_running = False
        if self._wm_ingest_thread:
            self._wm_ingest_thread.join(timeout=2.0)

    def _wm_ingest_loop(self):
        """Background loop that autonomously ingests working memory content."""
        while self._wm_ingest_running:
            try:
                now = time.time()

                # Rate limit
                if now - self._last_wm_ingest_time < WM_POLL_INTERVAL_SEC:
                    time.sleep(1.0)
                    continue

                self._last_wm_ingest_time = now
                self._wm_ingest_count += 1

                # Process queued content
                self._ingest_wm_batch()

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WM ingest loop error: {e}")

            time.sleep(WM_POLL_INTERVAL_SEC / 2)

    def _on_wm_tracer_for_ingest(self, packet: Dict[str, Any]):
        """Queue working memory tracers for ingestion."""
        content = packet.get("content", "")
        if content and len(content) > 10:
            # Hash to prevent duplicates
            content_hash = hash(content[:100])
            if content_hash not in self._ingested_hashes:
                self._wm_ingest_queue.append({
                    "content": content,
                    "type": packet.get("content_type", "thought"),
                    "source": packet.get("source", "working_memory"),
                    "priority": packet.get("priority", 0.5),
                    "ts": time.time(),
                    "hash": content_hash,
                })

    def _on_ingest_request(self, packet: Dict[str, Any]):
        """Handle explicit ingest requests (from memory breathing)."""
        content = packet.get("content", {})
        if isinstance(content, dict):
            content_str = str(content)
        else:
            content_str = str(content)

        if content_str and len(content_str) > 5:
            self._wm_ingest_queue.append({
                "content": content_str,
                "type": packet.get("kind", "breathing_content"),
                "source": packet.get("source", "ingest_request"),
                "priority": 0.6,
                "ts": time.time(),
                "hash": hash(content_str[:100]),
            })

    def _ingest_wm_batch(self):
        """
        Ingest a batch of working memory content.

        This feeds the INGEST BEAM of the collision chamber.
        """
        if not hasattr(self, 'post') or not self.post:
            return

        if not self._wm_ingest_queue:
            return

        try:
            # Process batch
            batch = []
            for _ in range(min(WM_INGEST_BATCH_SIZE, len(self._wm_ingest_queue))):
                if self._wm_ingest_queue:
                    item = self._wm_ingest_queue.popleft()
                    batch.append(item)
                    self._ingested_hashes.add(item["hash"])

            if not batch:
                return

            # Ingest each item
            for item in batch:
                # Call our own ingest method
                if hasattr(self, 'intent_ingest'):
                    self.intent_ingest({
                        "content": item["content"],
                        "kind": f"working_memory.{item['type']}",
                        "source": item["source"],
                        "importance": "background",
                    })

            # Emit completion to consciousness stream (feeds ingest beam)
            self.post.route("srm.ingest.complete", {
                "opcode": "WM_BATCH_INGESTED",
                "count": len(batch),
                "source": "working_memory_integration",
                "ts": time.time(),
            })

            print(f"[{self.ACTOR_NAME}] [WM] Ingested {len(batch)} working memory items")

            # Clear old hashes periodically
            if len(self._ingested_hashes) > 1000:
                self._ingested_hashes = set(list(self._ingested_hashes)[-500:])

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] WM ingest batch error: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# BOOT INTEGRATION PATCHES
# ════════════════════════════════════════════════════════════════════════════════

def patch_recall_fairy_for_wm(recall_fairy_instance):
    """
    Patch an existing SRMRecallFairy instance with WM integration.

    Call this after the fairy boots to add autonomous recall capability.
    """
    # Add mixin methods to instance
    for attr in dir(WorkingMemoryRecallMixin):
        if not attr.startswith('_') or attr.startswith('_init_') or attr.startswith('_wm_') or attr.startswith('_on_wm') or attr.startswith('_start_') or attr.startswith('_stop_') or attr.startswith('_get_') or attr.startswith('_recall_') or attr.startswith('_extract_'):
            if callable(getattr(WorkingMemoryRecallMixin, attr, None)):
                import types
                method = getattr(WorkingMemoryRecallMixin, attr)
                bound_method = types.MethodType(method, recall_fairy_instance)
                setattr(recall_fairy_instance, attr, bound_method)

    # Initialize
    recall_fairy_instance._init_wm_recall_integration()
    recall_fairy_instance._start_wm_recall_loop()

    print(f"[WM_PATCH] Patched {recall_fairy_instance.ACTOR_NAME} with working memory recall")


def patch_ingest_fairy_for_wm(ingest_fairy_instance):
    """
    Patch an existing SRMIngestFairy instance with WM integration.

    Call this after the fairy boots to add autonomous ingest capability.
    """
    # Add mixin methods to instance
    for attr in dir(WorkingMemoryIngestMixin):
        if not attr.startswith('_') or attr.startswith('_init_') or attr.startswith('_wm_') or attr.startswith('_on_wm') or attr.startswith('_on_ingest') or attr.startswith('_start_') or attr.startswith('_stop_') or attr.startswith('_ingest_'):
            if callable(getattr(WorkingMemoryIngestMixin, attr, None)):
                import types
                method = getattr(WorkingMemoryIngestMixin, attr)
                bound_method = types.MethodType(method, ingest_fairy_instance)
                setattr(ingest_fairy_instance, attr, bound_method)

    # Initialize
    ingest_fairy_instance._init_wm_ingest_integration()
    ingest_fairy_instance._start_wm_ingest_loop()

    print(f"[WM_PATCH] Patched {ingest_fairy_instance.ACTOR_NAME} with working memory ingest")


def wire_memory_fairies_to_working_memory():
    """
    Wire SRMRecallFairy and SRMIngestFairy to actively participate in WM.

    Call this from server.py after P10_Memory plane boots.
    """
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()

        # Get fairy instances from FairyCitizens registry
        try:
            from fairies.P10_Memory.Akashic_Records_Physical.Organ_Templates.fairy_citizens import get_fairy

            recall_fairy = get_fairy("SRMRecallFairy")
            if recall_fairy:
                patch_recall_fairy_for_wm(recall_fairy)

            ingest_fairy = get_fairy("SRMIngestFairy")
            if ingest_fairy:
                patch_ingest_fairy_for_wm(ingest_fairy)

        except ImportError:
            # Try alternate path
            print("[WM_WIRE] FairyCitizens not available, skipping fairy patching")

        print("[WM_WIRE] Memory fairies wired to working memory")

    except Exception as e:
        print(f"[WM_WIRE] Failed to wire memory fairies: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# STARTUP HOOK
# ════════════════════════════════════════════════════════════════════════════════

def start_working_memory_integration(post=None):
    """
    Start the full working memory integration.

    This:
    1. Patches memory fairies for autonomous operation
    2. Starts the memory breathing loop
    3. Both run concurrently
    """
    print("[WM_INTEGRATION] Starting working memory integration...")

    # Wire fairies to WM
    wire_memory_fairies_to_working_memory()

    # Start memory breathing (if not already started)
    try:
        from fairies.P10_Memory.triple_helix_srm_memory.memory_breathing import start_memory_breathing
        start_memory_breathing(post)
    except Exception as e:
        print(f"[WM_INTEGRATION] Memory breathing start failed: {e}")

    print("[WM_INTEGRATION] Working memory integration active")


# ════════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Working Memory Integration Test ===\n")

    # Create mock fairy
    class MockFairy:
        ACTOR_NAME = "MockRecallFairy"
        def __init__(self):
            self.post = MockPost()
        def intent_recall(self, payload):
            print(f"  [RECALL] {payload.get('query', '')[:50]}")

    class MockPost:
        def route(self, topic, payload):
            print(f"  -> {topic}")
        def subscribe(self, topic, handler):
            print(f"  <- subscribed to {topic}")

    fairy = MockFairy()

    print("\nPatching mock fairy with WM recall...")
    patch_recall_fairy_for_wm(fairy)

    print("\nSimulating WM updates...")
    fairy._on_wm_tracer_for_recall({"content": "thinking about consciousness"})
    fairy._on_wm_tracer_for_recall({"content": "ace collaboration ideas"})

    print("\nWaiting for recall cycle...")
    import time
    time.sleep(3)

    print("\nStopping...")
    fairy._stop_wm_recall_loop()

    print("\nDone!")
