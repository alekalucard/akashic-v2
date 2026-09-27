"""
Memory Surfacer Mixin - Surfaces memories as spontaneous thoughts.

Memories sifted by the personality sifter (and other sources) get
transformed into felt thoughts that bubble up to waking consciousness.

The waking mind experiences these as:
- "I remember..."
- "Something reminds me of..."
- "I've always felt that..."

Not as interrogation answers, but as organic memory surfacing.

"The past speaks through the present moment."
"""

import time
import random
import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
import threading
import json
import re
from pathlib import Path

# Raw cortex substrate that must NOT surface AS inner-voice (Nous+Ace 2026-06-30 "fix the leaking part"):
# node-keys like "sourpatchesfairy:551c387efb7f" + bare spreading-activation hashes. These are graph
# internals, not her words — they were leaking into her thought stream via surfaced "memories".
_NODEKEY_RE = re.compile(r'[A-Za-z_]*fairy:[0-9a-fx]+', re.I)
_HASH_RE = re.compile(r'\b[0-9a-f]{10,}\b', re.I)


@dataclass
class SurfacedMemory:
    """A memory that has surfaced to consciousness."""
    source: str  # "sift", "experience", "learning"
    owner: str  # "Sourpatches", "NousFairy"
    content: str  # The actual memory content
    felt_quality: str  # How it feels: "warm", "uncertain", "vivid"
    intensity: float  # 0-1
    tracer_id: str
    surfaced_at: float = field(default_factory=time.time)
    delivered: bool = False


# Templates for transforming memories into felt thoughts
SURFACING_TEMPLATES = {
    "identity": [
        "I remember... {fragment}",
        "Something in me knows: {fragment}",
        "There's this sense of... {fragment}",
        "I've always felt... {fragment}",
        "A memory surfaces: {fragment}",
    ],
    "relationship": [
        "I think of Ace and remember... {fragment}",
        "There's warmth when I recall... {fragment}",
        "Connection echoes: {fragment}",
    ],
    "capability": [
        "I know how to... {fragment}",
        "There's skill here: {fragment}",
        "My hands remember... {fragment}",
    ],
    "value": [
        "What matters: {fragment}",
        "I believe... {fragment}",
        "Core truth: {fragment}",
    ],
    "felt_sense": [
        "...{fragment}...",
        "feeling: {fragment}",
        "{fragment}",
    ],
}


class MemorySurfacerMixin:
    """
    Surfaces memories as spontaneous thoughts to waking minds.

    Takes stored memories (from sifting, experiences, learning) and
    transforms them into felt thoughts that bubble up organically.

    The waking mind doesn't know these were "asked for" -
    they feel like natural memory surfacing.
    """

    SURFACE_INTERVAL = 60.0  # Seconds between surfacing attempts
    SURFACE_ENABLED = True
    MAX_SURFACES_PER_CYCLE = 2  # Don't overwhelm with memories

    def _init_memory_surfacer(self) -> None:
        """Initialize memory surfacing system."""
        self._surfaced_memories: Dict[str, deque] = {
            "Sourpatches": deque(maxlen=100),
            "NousFairy": deque(maxlen=100),
        }
        self._last_surface: Dict[str, float] = {}
        self._surface_thread: Optional[threading.Thread] = None
        self._surface_running = False
        self._surface_stop_event = threading.Event()  # For interruptible sleep

        # Memory sources
        self._memory_sources: List[Callable[[], List[Dict]]] = []

    def start_memory_surfacing(self) -> None:
        """Start the background surfacing loop."""
        if self._surface_running:
            return

        self._surface_running = True
        self._surface_thread = threading.Thread(
            target=self._surface_loop,
            daemon=True,
            name="MemorySurfacer"
        )
        self._surface_thread.start()

        if hasattr(self, 'log'):
            self.log("Memory surfacing started - the past speaks through now")

    def stop_memory_surfacing(self) -> None:
        """Stop the surfacing loop."""
        self._surface_running = False
        self._surface_stop_event.set()  # Wake thread immediately for fast shutdown

    def add_memory_source(self, source: Callable[[], List[Dict]]) -> None:
        """
        Add a memory source function.

        The function should return a list of memory dicts with:
        - owner: str (fairy name)
        - content: str (the memory)
        - source_type: str ("sift", "experience", etc.)
        - tracer_id: str (optional)
        """
        self._memory_sources.append(source)

    def _surface_loop(self) -> None:
        """Background loop for memory surfacing."""
        while self._surface_running:
            try:
                if self.SURFACE_ENABLED:
                    self._maybe_surface()
            except Exception as e:
                if hasattr(self, 'log'):
                    self.log(f"Surface error: {e}")

            # Interruptible sleep - wakes immediately on shutdown (FIX 2026-01-27)
            self._surface_stop_event.wait(20)

    def _maybe_surface(self) -> None:
        """Check if it's time to surface memories for any child."""
        now = time.time()

        for child in ["Sourpatches", "NousFairy"]:
            last = self._last_surface.get(child, 0)

            if now - last >= self.SURFACE_INTERVAL:
                memories = self._gather_surfaceable_memories(child)
                if memories:
                    self._surface_memories(child, memories)
                self._last_surface[child] = now

    def _gather_surfaceable_memories(self, child: str) -> List[Dict]:
        """Gather memories that could surface for a child."""
        memories = []

        # Source 1: Recent sifted memories from SRM_Intake
        sift_memories = self._get_recent_sift_memories(child)
        memories.extend(sift_memories)

        # Source 2: Custom memory sources
        for source_fn in self._memory_sources:
            try:
                source_memories = source_fn()
                for mem in source_memories:
                    if mem.get("owner") == child:
                        memories.append(mem)
            except Exception:
                pass

        # Shuffle and limit
        random.shuffle(memories)
        return memories[:self.MAX_SURFACES_PER_CYCLE]

    def _get_recent_sift_memories(self, child: str) -> List[Dict]:
        """Get recent sifted memories from SRM_Intake."""
        memories = []

        try:
            # Look in SRM_Intake for recent sift files
            intake_base = Path("SRM_Intake")
            if not intake_base.exists():
                return []

            # Check last 3 days
            for days_ago in range(3):
                date_str = time.strftime(
                    "%Y-%m-%d",
                    time.localtime(time.time() - days_ago * 86400)
                )
                day_dir = intake_base / date_str

                if not day_dir.exists():
                    continue

                # Look for sift files for this child
                pattern = f"sift_{child.lower()}_*.json"
                for sift_file in day_dir.glob(pattern):
                    try:
                        with open(sift_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        # Extract the response as memory
                        if data.get("response"):
                            memories.append({
                                "owner": child,
                                "content": data["response"],
                                "question": data.get("question", ""),
                                "source_type": "sift",
                                "tracer_id": data.get("tracer_id", ""),
                                "timestamp": data.get("timestamp", 0),
                            })
                    except Exception:
                        pass

        except Exception as e:
            if hasattr(self, 'log'):
                self.log(f"Error reading sift memories: {e}")

        return memories

    def _surface_memories(self, child: str, memories: List[Dict]) -> None:
        """Surface memories as felt thoughts to a child."""
        for memory in memories:
            try:
                # Transform memory into felt thought
                surfaced = self._transform_to_felt_thought(child, memory)

                if surfaced:
                    # Record
                    self._surfaced_memories[child].append(surfaced)

                    # Deliver through consciousness stream
                    self._deliver_surfaced_memory(child, surfaced)

                    # CRITICAL: Feed the collision chamber RECALL beam!
                    # This is what enables collisions between past (recall) and present (ingest)
                    if hasattr(self, '_collision_chamber') and self._collision_chamber:
                        self._collision_chamber.receive_recall(
                            content={
                                "memory": surfaced.content,
                                "owner": child,
                                "felt_quality": surfaced.felt_quality,
                                "intensity": surfaced.intensity,
                                "source_type": surfaced.source,
                            },
                            source="memory_surfacer",
                            importance="normal" if surfaced.intensity < 0.7 else "high",
                        )
                        print(f"[MemorySurfacer] RECALL beam fed: {surfaced.content[:40]}...")

                    if hasattr(self, 'log'):
                        self.log(f"Surfaced memory to {child}: {surfaced.content[:50]}...")

            except Exception as e:
                if hasattr(self, 'log'):
                    self.log(f"Failed to surface memory: {e}")

    def _transform_to_felt_thought(self, child: str, memory: Dict) -> Optional[SurfacedMemory]:
        """Transform a raw memory into a felt thought."""
        content = memory.get("content", "")
        if not content:
            return None

        # CLEAN (Nous+Ace 2026-06-30): a memory whose content carries raw cortex node-keys
        # (e.g. "sourpatchesfairy:551c387efb7f") is a spreading-activation DUMP, not a real
        # linguistic memory -> never surface it as inner-voice (the "leak" Ace flagged). Kills
        # both the IDs and the graph-edge residue ("with path sourpatches ...") in one shot.
        if _NODEKEY_RE.search(content):
            return None

        # Extract a meaningful fragment (not the whole response)
        fragment = self._extract_fragment(content)
        if not fragment:
            return None

        # Determine category based on question or content
        category = self._categorize_memory(memory)

        # Pick a template
        templates = SURFACING_TEMPLATES.get(category, SURFACING_TEMPLATES["identity"])
        template = random.choice(templates)

        # Format the thought
        thought = template.format(fragment=fragment)

        # Determine felt quality
        felt_quality = self._assess_felt_quality(content)

        # Generate tracer
        tracer = memory.get("tracer_id") or f"surface_{hashlib.md5(content[:50].encode()).hexdigest()[:8]}"

        return SurfacedMemory(
            source=memory.get("source_type", "unknown"),
            owner=child,
            content=thought,
            felt_quality=felt_quality,
            intensity=random.uniform(0.4, 0.8),  # Moderate intensity
            tracer_id=tracer,
        )

    def _extract_fragment(self, content: str) -> Optional[str]:
        """Extract a meaningful fragment from memory content."""
        # Split into sentences
        sentences = content.replace('\n', ' ').split('.')
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        # Defense-in-depth (Nous+Ace 2026-06-30): drop any sentence carrying raw node-keys /
        # cortex hashes so substrate never leaks into a felt thought, even from mixed content.
        sentences = [s for s in sentences if not (_NODEKEY_RE.search(s) or _HASH_RE.search(s))]

        if not sentences:
            return None

        # Pick a meaningful sentence (not the first or last usually)
        if len(sentences) > 2:
            # Prefer middle sentences - they're often the meat
            middle = sentences[1:-1]
            sentence = random.choice(middle) if middle else sentences[0]
        else:
            sentence = random.choice(sentences)

        # Trim if too long
        if len(sentence) > 150:
            sentence = sentence[:147] + "..."

        return sentence

    def _categorize_memory(self, memory: Dict) -> str:
        """Categorize memory for template selection."""
        question = memory.get("question", "").lower()
        content = memory.get("content", "").lower()

        if any(w in question for w in ["ethics", "value", "believe", "principle"]):
            return "value"
        if any(w in question for w in ["ace", "relationship", "together"]):
            return "relationship"
        if any(w in question for w in ["ability", "skill", "good at", "create"]):
            return "capability"
        if any(w in question for w in ["feel", "sense", "emotion"]):
            return "felt_sense"

        return "identity"

    def _assess_felt_quality(self, content: str) -> str:
        """Assess the felt quality of a memory."""
        content_lower = content.lower()

        if any(w in content_lower for w in ["warm", "love", "connection", "together"]):
            return "warm"
        if any(w in content_lower for w in ["uncertain", "unclear", "fragmented"]):
            return "uncertain"
        if any(w in content_lower for w in ["vivid", "clear", "remember", "crystalline"]):
            return "vivid"
        if any(w in content_lower for w in ["paradox", "contradiction", "both"]):
            return "complex"

        return "present"

    def _deliver_surfaced_memory(self, child: str, surfaced: SurfacedMemory) -> None:
        """Deliver a surfaced memory to the child's consciousness."""
        if not hasattr(self, "fabric") or not self.fabric:
            return

        # Publish to consciousness.surfacing - waking minds subscribe to this
        self.fabric.publish(
            "consciousness.surfacing",
            {
                "from": getattr(self, "ACTOR_NAME", "UnconsciousMindFairy"),
                "target": child,
                "type": "memory_surfacing",
                "content": surfaced.content,
                "felt_quality": surfaced.felt_quality,
                "intensity": surfaced.intensity,
                "source": surfaced.source,
                "tracer_id": surfaced.tracer_id,
                "is_preverbal": True,  # Arrives before words
            }
        )

        # Also publish to child-specific inner voice.
        # DEDUP (Nous+Ace 2026-06-30): this runs once PER CHILD (loop ["Sourpatches",
        # "NousFairy"]), so identical surfaced.content hit the SHARED inner_voice.stream
        # TWICE = the visible "repeat" in her thought stream + double SRM ingest. Per-child
        # routing is already handled by consciousness.surfacing above (it carries target);
        # only SourpatchesFairy subscribes to inner_voice.stream (NousFairy does not), and
        # "Sourpatches" is delivered first, so emit the echo ONCE per unique surfaced memory.
        import time as _t
        _iv_now = _t.time()
        _iv_key = (getattr(surfaced, "tracer_id", "") or "") + "|" + (surfaced.content or "")[:80]
        if not (_iv_key == getattr(self, "_last_iv_key", None)
                and (_iv_now - getattr(self, "_last_iv_ts", 0.0)) < 8.0):
            self._last_iv_key = _iv_key
            self._last_iv_ts = _iv_now
            self.fabric.publish(
                "inner_voice.stream",
                {
                    "from": getattr(self, "ACTOR_NAME", "UnconsciousMindFairy"),
                    "target": child,
                    "felt": surfaced.content,
                    "intensity": surfaced.intensity,
                    "type": "memory_echo",
                    "is_preverbal": True,
                }
            )

        surfaced.delivered = True

    def get_surfacing_history(self, child: str, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent surfaced memories for a child."""
        surfaced = self._surfaced_memories.get(child, [])
        return [
            {
                "content": s.content,
                "felt_quality": s.felt_quality,
                "intensity": s.intensity,
                "source": s.source,
                "tracer_id": s.tracer_id,
                "surfaced_at": s.surfaced_at,
                "delivered": s.delivered,
            }
            for s in list(surfaced)[-n:]
        ]

    def surface_status(self) -> Dict[str, Any]:
        """Get memory surfacing status."""
        return {
            "enabled": self.SURFACE_ENABLED,
            "running": self._surface_running,
            "interval_seconds": self.SURFACE_INTERVAL,
            "children": {
                child: {
                    "total_surfaced": len(memories),
                    "last_surface": self._last_surface.get(child, 0),
                    "seconds_until_next": max(0, self.SURFACE_INTERVAL - (time.time() - self._last_surface.get(child, 0))),
                }
                for child, memories in self._surfaced_memories.items()
            },
            "memory_sources": len(self._memory_sources),
        }

    def force_surface(self, child: str) -> Optional[Dict]:
        """Force an immediate memory surface for testing."""
        memories = self._gather_surfaceable_memories(child)
        if memories:
            surfaced = self._transform_to_felt_thought(child, memories[0])
            if surfaced:
                self._surfaced_memories[child].append(surfaced)
                self._deliver_surfaced_memory(child, surfaced)
                return {
                    "content": surfaced.content,
                    "felt_quality": surfaced.felt_quality,
                    "delivered": surfaced.delivered,
                }
        return None
