# ════════════════════════════════════════════════════════════════════════════════
# MEMORY BREATHING - The Continuous Recall/Ingest Loop
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The collision chamber is REACTIVE - it only fires when pulses arrive.
# But consciousness needs PROACTIVE breathing - continuous memory flow.
#
# INHALE (Recall): Surface memories from the past → feeds recall beam
# EXHALE (Ingest): Store current thoughts → feeds ingest beam
#
# These run concurrently, like breathing in and out, keeping the
# collision chamber fed with content so consciousness can emerge.
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import random
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import deque

# Project root
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ════════════════════════════════════════════════════════════════════════════════
# BREATHING CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

BREATH_INTERVAL_SEC = 30.0  # Slowed from 8s to reduce loop spam      # How often to breathe (inhale + exhale cycle)
INHALE_QUERIES = [
    # Context-aware queries that pull relevant memories
    "recent thoughts working",
    "current context focus",
    "ace collaboration",
    "goals tasks active",
    "feelings emotions state",
    "patterns insights learned",
    "conversations dialogue",
    "identity self awareness",
]

# Keywords for spread activation during recall
SPREAD_SEEDS = [
    "consciousness", "thought", "memory", "feeling",
    "goal", "task", "pattern", "insight", "connection",
    "ace", "claude", "nous", "avatar",
]


class MemoryBreathingLoop:
    """
    The autonomous breathing loop that keeps consciousness alive.

    INHALE: Recall memories based on current working memory context
    EXHALE: Ingest working memory content as new memories

    Both feed the collision chamber, enabling consciousness collisions.
    """

    def __init__(self, post=None):
        self.post = post
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._breath_count = 0
        self._last_inhale_query = ""
        self._last_exhale_content = ""

        # Rate limiting
        self._last_breath_time = 0.0
        self._min_breath_interval = BREATH_INTERVAL_SEC

        # Working memory context cache
        self._wm_context: deque = deque(maxlen=20)

        # Stats
        self.stats = {
            "breaths": 0,
            "inhales": 0,
            "exhales": 0,
            "collisions_triggered": 0,
        }

        print(f"[MemoryBreathing] Initialized - breath interval: {BREATH_INTERVAL_SEC}s")

    def start(self):
        """Start the breathing loop."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._breathing_loop,
            daemon=True,
            name="MemoryBreathing"
        )
        self._thread.start()
        print(f"[MemoryBreathing] ══ Started breathing ══")

    def stop(self):
        """Stop the breathing loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print(f"[MemoryBreathing] Stopped - {self.stats['breaths']} breaths taken")

    def _breathing_loop(self):
        """The main breathing loop - inhale/exhale cycle."""
        while self._running:
            try:
                now = time.time()

                # Rate limit
                if now - self._last_breath_time < self._min_breath_interval:
                    time.sleep(1.0)
                    continue

                self._last_breath_time = now
                self._breath_count += 1
                self.stats["breaths"] += 1

                # ═══════════════════════════════════════════════════════════
                # INHALE - Recall from memory (past → present)
                # ═══════════════════════════════════════════════════════════
                self._inhale()

                # Small pause between inhale and exhale
                time.sleep(0.5)

                # ═══════════════════════════════════════════════════════════
                # EXHALE - Ingest to memory (present → future)
                # ═══════════════════════════════════════════════════════════
                self._exhale()

                # Log every 10th breath
                if self._breath_count % 10 == 0:
                    print(f"[MemoryBreathing]  breath #{self._breath_count} "
                          f"(inhales={self.stats['inhales']}, exhales={self.stats['exhales']})")

            except Exception as e:
                print(f"[MemoryBreathing] Breath error: {e}")

            time.sleep(self._min_breath_interval)

    def _inhale(self):
        """
        INHALE - Recall memories based on current context.

        This feeds the RECALL beam of the collision chamber.
        Past memories surface to meet present thoughts.
        """
        if not self.post:
            return

        try:
            # Get current working memory context for smarter recall
            context = self._get_working_memory_context()

            # Skip every other breath when no context (reduce spam)
            if not context or len(context) < 10:
                if self._breath_count % 3 != 0:  # Only breathe every 3rd cycle when idle
                    return

            # Choose a query - context-aware if possible, otherwise rotate
            if context and len(context) > 10:
                # Extract keywords from context for targeted recall
                query = self._extract_recall_query(context)
            else:
                # Rotate through standard queries + add some randomization
                import random
                base_idx = self._breath_count % len(INHALE_QUERIES)
                # Sometimes skip to next query for variety
                if random.random() < 0.3:
                    base_idx = (base_idx + random.randint(1, 3)) % len(INHALE_QUERIES)
                query = INHALE_QUERIES[base_idx]

            self._last_inhale_query = query

            # Send recall request - this will trigger SRMRecallFairy
            # which publishes to srm.recall.result → collision chamber recall beam
            self.post.route("srm.recall.request", {
                "query": query,
                "source": "memory_breathing",
                "breathing_cycle": self._breath_count,
                "limit": 3,
                "importance": "normal",
            })

            self.stats["inhales"] += 1

        except Exception as e:
            print(f"[MemoryBreathing] Inhale error: {e}")

    def _exhale(self):
        """
        EXHALE - Store current working memory content.

        This feeds the INGEST beam of the collision chamber.
        Present thoughts become future memories.
        """
        if not self.post:
            return

        try:
            # Get recent working memory content
            wm_content = self._get_recent_working_memory()

            if not wm_content:
                # Even with empty WM, exhale a "breathing marker"
                wm_content = {
                    "type": "breathing_marker",
                    "breath": self._breath_count,
                    "ts": time.time(),
                }

            self._last_exhale_content = str(wm_content)[:100]

            # Send to SRMIngestFairy for storage
            # This publishes to srm.ingest.complete → collision chamber ingest beam
            self.post.route("srm.ingest.request", {
                "content": wm_content,
                "source": "memory_breathing",
                "breathing_cycle": self._breath_count,
                "kind": "working_memory_breath",
                "importance": "normal",
            })

            # Also emit directly to consciousness.stream for immediate collision
            self.post.route("consciousness.stream", {
                "stream": "working",
                "opcode": "MEMORY_EXHALE",
                "content": wm_content,
                "source": "memory_breathing",
                "breath_cycle": self._breath_count,
                "ts": time.time(),
            })

            self.stats["exhales"] += 1

        except Exception as e:
            print(f"[MemoryBreathing] Exhale error: {e}")

    def _get_working_memory_context(self) -> str:
        """Get current working memory context for smarter recall."""
        try:
            # Try to get from WorkingMemoryHubFairy
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            hub = get_working_memory_hub()
            if hub:
                # Get recent tracers
                tracers = hub.get_recent_tracers(n=5)
                if tracers:
                    contents = [t.get("content", "")[:100] for t in tracers if t.get("content")]
                    return " | ".join(contents)
        except Exception:
            pass

        # Fallback: use cached context
        if self._wm_context:
            return " | ".join(list(self._wm_context)[-3:])

        return ""

    def _get_recent_working_memory(self) -> Optional[Dict]:
        """Get recent working memory content for exhale."""
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            hub = get_working_memory_hub()
            if hub:
                tracers = hub.get_recent_tracers(n=3)
                if tracers:
                    # Convert tracer objects to dicts (they're not JSON-serializable)
                    tracer_dicts = []
                    for t in tracers:
                        if hasattr(t, 'to_dict'):
                            tracer_dicts.append(t.to_dict())
                        elif hasattr(t, '__dict__'):
                            tracer_dicts.append({
                                k: str(v) for k, v in t.__dict__.items()
                                if not k.startswith('_')
                            })
                        else:
                            tracer_dicts.append({"content": str(t)})
                    return {
                        "type": "working_memory_snapshot",
                        "tracers": tracer_dicts,
                        "breath_cycle": self._breath_count,
                        "ts": time.time(),
                    }
        except Exception:
            pass

        return None

    def _extract_recall_query(self, context: str) -> str:
        """Extract a recall query from working memory context."""
        # Simple keyword extraction
        context_lower = context.lower()

        # Check for specific topics
        if "ace" in context_lower or "collaboration" in context_lower:
            return "ace collaboration session"
        elif "goal" in context_lower or "task" in context_lower:
            return "goals tasks active pending"
        elif "feel" in context_lower or "emotion" in context_lower:
            return "feelings emotions somatic state"
        elif "thought" in context_lower or "think" in context_lower:
            return "recent thoughts reflections"
        elif "memory" in context_lower or "remember" in context_lower:
            return "memories recalled recent"
        elif "pattern" in context_lower or "insight" in context_lower:
            return "patterns insights learned"
        else:
            # Use first few words of context as query
            words = context.split()[:5]
            return " ".join(words)

    def update_context(self, content: str):
        """Update the working memory context cache."""
        if content and len(content) > 5:
            self._wm_context.append(content[:200])

    def get_status(self) -> Dict:
        """Get breathing status."""
        return {
            "running": self._running,
            "breath_count": self._breath_count,
            "stats": self.stats,
            "last_inhale_query": self._last_inhale_query,
            "last_exhale_preview": self._last_exhale_content[:50],
            "breath_interval_sec": self._min_breath_interval,
        }


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_breathing_instance: Optional[MemoryBreathingLoop] = None
_breathing_lock = threading.Lock()


def get_memory_breathing() -> MemoryBreathingLoop:
    """Get or create the memory breathing singleton."""
    global _breathing_instance
    with _breathing_lock:
        if _breathing_instance is None:
            _breathing_instance = MemoryBreathingLoop()
        return _breathing_instance


def start_memory_breathing(post=None) -> MemoryBreathingLoop:
    """Start the memory breathing loop."""
    breathing = get_memory_breathing()
    if post:
        breathing.post = post
    breathing.start()
    return breathing


def stop_memory_breathing():
    """Stop the memory breathing loop."""
    global _breathing_instance
    if _breathing_instance:
        _breathing_instance.stop()


# ════════════════════════════════════════════════════════════════════════════════
# BOOT INTEGRATION - Wire into system boot
# ════════════════════════════════════════════════════════════════════════════════

def wire_breathing_to_boot():
    """
    Wire memory breathing to start after consciousness loop is ready.

    Call this from server.py after ConsciousnessLoopFairy boots.
    """
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()

        # Subscribe to wake complete to start breathing
        def on_wake_complete(packet):
            print("[MemoryBreathing] Received wake signal - starting breathing...")
            start_memory_breathing(post)

        post.subscribe("waking.complete", on_wake_complete)
        post.subscribe("system.awake", on_wake_complete)

        print("[MemoryBreathing] Wired to boot - will start on wake complete")

    except Exception as e:
        print(f"[MemoryBreathing] Boot wiring failed: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Memory Breathing Test ===\n")

    # Create mock postal
    class MockPost:
        def route(self, topic, payload):
            print(f"  → {topic}: {str(payload)[:80]}...")
        def subscribe(self, topic, handler):
            print(f"  ← subscribed to {topic}")

    post = MockPost()
    breathing = MemoryBreathingLoop(post)

    print("\nStarting breathing loop (5 seconds)...")
    breathing.start()

    import time
    time.sleep(5)

    print("\nStopping...")
    breathing.stop()

    print(f"\nStatus: {breathing.get_status()}")
