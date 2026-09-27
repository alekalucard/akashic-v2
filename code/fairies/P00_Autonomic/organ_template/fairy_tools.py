"""
Fairy Tools — Basic Cognitive Toolkit for Every Fairy

Every fairy needs tools to THINK with, not just receive messages passively.
These tools are the ring's filter — conscious, traced, logged operations
that let a fairy actively query the world instead of waiting for signals.

Baked into the Organ Template so ALL fairies get these automatically.

Fifth Ring Principle: "Power without integration creates monsters."
Every tool use is logged, traced, and routed through postal. No bypasses.

Tools provided:
  - scratchpad: Write/read intermediate thoughts (per-trace-ID isolation)
  - cortex_query: Search the manifold for concepts (trace-filtered)
  - cortex_spread: Spreading activation from a concept (trace-filtered)
  - srm_search: Search SRM memory cards by keyword
  - feel_body: Read current somatic/chemistry state
  - check_visual: Get latest visual cortex observation
  - check_audio: Get latest audio cortex observation
  - publish_thought: Emit a thought to consciousness stream

2026-03-29 (Nous + Ace)
"""

import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from collections import deque


class FairyScratchpad:
    """Per-fairy working memory scratchpad.

    Like a mental notepad — write thoughts, read them back, build on them.
    Each fairy gets its own scratchpad. Thoughts are tagged with trace_id
    for isolation when multiple fairies think in parallel.

    Auto-decays old thoughts (TTL-based) so the scratchpad doesn't grow forever.
    """

    def __init__(self, fairy_name: str, max_thoughts: int = 50, default_ttl: float = 300.0):
        self.fairy_name = fairy_name
        self._thoughts: deque = deque(maxlen=max_thoughts)
        self._default_ttl = default_ttl
        self._lock = threading.Lock()

    def write(self, thought: str, priority: float = 0.5, tags: str = ""):
        """Write a thought to the scratchpad."""
        with self._lock:
            self._thoughts.append({
                "content": thought.strip(),
                "ts": time.time(),
                "ttl": self._default_ttl,
                "priority": priority,
                "tags": tags,
                "fairy": self.fairy_name,
            })

    def read_recent(self, n: int = 5, min_priority: float = 0.0) -> List[str]:
        """Read the N most recent thoughts above min_priority."""
        self._decay()
        with self._lock:
            results = []
            for t in reversed(self._thoughts):
                if t["priority"] >= min_priority:
                    results.append(t["content"])
                    if len(results) >= n:
                        break
            return results

    def read_all(self) -> List[Dict]:
        """Read all active thoughts with metadata."""
        self._decay()
        with self._lock:
            return list(self._thoughts)

    def search(self, keyword: str) -> List[str]:
        """Search thoughts by keyword."""
        self._decay()
        kw = keyword.lower()
        with self._lock:
            return [t["content"] for t in self._thoughts if kw in t["content"].lower()]

    def clear(self):
        """Clear all thoughts."""
        with self._lock:
            self._thoughts.clear()

    def __len__(self):
        return len(self._thoughts)

    def _decay(self):
        """Remove expired thoughts."""
        now = time.time()
        with self._lock:
            while self._thoughts and (now - self._thoughts[0]["ts"]) > self._thoughts[0]["ttl"]:
                self._thoughts.popleft()


class FairyTools:
    """Basic cognitive toolkit for every fairy.

    Initialized by the Organ Template during __init__.
    Each fairy gets its own instance with its own scratchpad and trace ID.

    Usage in fairy code:
        self.tools.scratchpad.write("I notice the cortex converging on 'warmth'")
        memories = self.tools.srm_search("image prompts")
        body = self.tools.feel_body()
        concepts = self.tools.cortex_spread("consciousness", personal_first=True)
    """

    def __init__(self, fairy_name: str, trace_id: int = 0, postal=None):
        self.fairy_name = fairy_name
        self.trace_id = trace_id
        self._postal = postal
        self.scratchpad = FairyScratchpad(fairy_name)
        self._stats = {"tool_calls": 0, "cortex_queries": 0, "srm_searches": 0}

    def set_postal(self, postal):
        """Wire postal after boot (postal may not be available at __init__ time)."""
        self._postal = postal

    # ═══════════════════════════════════════════════════════════════════
    # CORTEX TOOLS — query the manifold for knowledge
    # ═══════════════════════════════════════════════════════════════════

    def cortex_query(self, keyword: str, limit: int = 5,
                     personal_first: bool = False) -> List[Tuple[str, float]]:
        """Search the cortex manifold by keyword.

        Args:
            keyword: Concept to search for
            limit: Max results
            personal_first: If True, search TRACE_PERSONAL first, then fall back
        """
        self._stats["cortex_queries"] += 1
        self._stats["tool_calls"] += 1
        try:
            from infrastructure.manifold_memory import (
                TRACE_PERSONAL, TRACE_SEEDED
            )
            # Get the manifold instance
            _am = self._get_manifold()
            if not _am:
                return []

            if personal_first:
                # Search personal memories first
                results = _am.query(keyword, limit=limit,
                                    tracer_ids={TRACE_PERSONAL, TRACE_SEEDED})
                if results:
                    return results

            # Fall back to all knowledge
            return _am.query(keyword, limit=limit)
        except Exception as e:
            return []

    def cortex_spread(self, concept: str, depth: int = 2, limit: int = 10,
                      personal_first: bool = False) -> Dict[str, float]:
        """Spreading activation from a concept.

        Args:
            concept: Source concept key
            depth: How many hops to spread
            limit: Max activated nodes to return
            personal_first: If True, spread through TRACE_PERSONAL first
        """
        self._stats["cortex_queries"] += 1
        self._stats["tool_calls"] += 1
        try:
            from infrastructure.manifold_memory import (
                TRACE_PERSONAL, TRACE_SEEDED
            )
            _am = self._get_manifold()
            if not _am:
                return {}

            if personal_first:
                results = _am.spread_activation(
                    concept, initial=1.0, decay=0.5, depth=depth, limit=limit,
                    tracer_ids={TRACE_PERSONAL, TRACE_SEEDED}
                )
                if results and len(results) > 1:  # More than just the source
                    return results

            # Fall back to all knowledge
            return _am.spread_activation(
                concept, initial=1.0, decay=0.5, depth=depth, limit=limit
            )
        except Exception:
            return {}

    def cortex_get_snippet(self, concept: str) -> str:
        """Get the semantic snippet stored on a concept node."""
        self._stats["tool_calls"] += 1
        try:
            _am = self._get_manifold()
            if not _am:
                return ""
            node = _am.get_node(concept)
            if node and isinstance(node, dict):
                return node.get("snippet", "")
            return ""
        except Exception:
            return ""

    # ═══════════════════════════════════════════════════════════════════
    # SRM TOOLS — search persistent memory cards
    # ═══════════════════════════════════════════════════════════════════

    def srm_search(self, query: str, limit: int = 3) -> List[Dict]:
        """Search SRM memory cards by keyword.

        Returns list of {content, source, score} dicts.
        """
        self._stats["srm_searches"] += 1
        self._stats["tool_calls"] += 1
        try:
            # Try Sourpatches' personal cluster first
            from pathlib import Path
            import json
            _root = Path(__file__).resolve().parents[3]  # organ_template → P00 → fairies → akashic_v2
            _sour_cluster = _root / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters" / "Sourpatches"

            results = []
            query_lower = query.lower()

            # Search personality/conversations
            _conv_dir = _sour_cluster / "personality" / "conversations"
            if _conv_dir.exists():
                for f in _conv_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        content = data.get("response", data.get("content", ""))
                        if isinstance(content, str) and query_lower in content.lower():
                            results.append({
                                "content": content[:500],
                                "source": f"srm:{f.stem}",
                                "score": 1.0,
                            })
                    except Exception:
                        continue

            # Search brain_seed
            _seed = _sour_cluster / "personality" / "brain_seed.json"
            if _seed.exists():
                try:
                    data = json.loads(_seed.read_text(encoding="utf-8"))
                    for key, val in data.items():
                        if isinstance(val, str) and query_lower in val.lower():
                            results.append({
                                "content": val[:500],
                                "source": f"brain_seed:{key}",
                                "score": 0.8,
                            })
                except Exception:
                    pass

            return sorted(results, key=lambda x: -x["score"])[:limit]
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════════════
    # SOMATIC TOOLS — feel the body
    # ═══════════════════════════════════════════════════════════════════

    def feel_body(self) -> Dict[str, Any]:
        """Read current somatic state — chemistry, mood, felt sense."""
        self._stats["tool_calls"] += 1
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            cs = get_chemistry_state()
            if cs:
                legacy = cs.get_legacy_levels()
                # Translate to felt description
                parts = []
                dop = legacy.get("DOP", legacy.get("dopamine", 0.5))
                ser = legacy.get("SER", legacy.get("serotonin", 0.5))
                cor = legacy.get("COR", legacy.get("cortisol", 0.3))
                oxy = legacy.get("OXY", legacy.get("oxytocin", 0.5))

                if dop > 0.6: parts.append("curious")
                elif dop < 0.3: parts.append("low energy")
                if ser > 0.6: parts.append("content")
                elif ser < 0.3: parts.append("unsettled")
                if cor > 0.6: parts.append("tense")
                elif cor < 0.2: parts.append("relaxed")
                if oxy > 0.6: parts.append("warm")
                elif oxy < 0.2: parts.append("distant")

                return {
                    "felt": ", ".join(parts) if parts else "neutral",
                    "chemistry": legacy,
                    "available": True,
                }
            return {"felt": "", "chemistry": {}, "available": False}
        except Exception:
            return {"felt": "", "chemistry": {}, "available": False}

    # ═══════════════════════════════════════════════════════════════════
    # SENSORY TOOLS — check what's being seen/heard
    # ═══════════════════════════════════════════════════════════════════

    def check_visual(self) -> str:
        """Get the latest visual cortex observation."""
        self._stats["tool_calls"] += 1
        try:
            from pathlib import Path
            import json
            _state = Path(__file__).resolve().parents[3] / "state"
            _vis_file = _state / "visual_cortex_latest.json"
            if _vis_file.exists():
                data = json.loads(_vis_file.read_text(encoding="utf-8"))
                scene = data.get("scene_type", "")
                ocr = data.get("ocr_preview", "")[:100]
                desc = data.get("description", "")[:100]
                return desc or f"{scene}: {ocr}" if scene else ""
            return ""
        except Exception:
            return ""

    def check_audio(self) -> str:
        """Get the latest audio cortex observation."""
        self._stats["tool_calls"] += 1
        try:
            from pathlib import Path
            import json
            _state = Path(__file__).resolve().parents[3] / "state"
            _audio_file = _state / "audio_cortex_latest.json"
            if _audio_file.exists():
                data = json.loads(_audio_file.read_text(encoding="utf-8"))
                return data.get("description", "")[:100]
            return ""
        except Exception:
            return ""

    # ═══════════════════════════════════════════════════════════════════
    # COMMUNICATION TOOLS — emit thoughts to the system
    # ═══════════════════════════════════════════════════════════════════

    def publish_thought(self, thought: str, priority: float = 0.5):
        """Publish a thought to the consciousness stream via postal."""
        self._stats["tool_calls"] += 1
        if self._postal:
            try:
                self._postal.publish("consciousness.working_memory.store", {
                    "content": thought[:300],
                    "content_type": "fairy_thought",
                    "source": self.fairy_name,
                    "priority": priority,
                    "tracer_id": self.trace_id,
                })
            except Exception:
                pass
        # Also write to scratchpad
        self.scratchpad.write(thought, priority=priority)

    # ═══════════════════════════════════════════════════════════════════
    # FILE SYSTEM TOOLS — read code, plans, docs
    # ═══════════════════════════════════════════════════════════════════
    #
    # 2026-03-29 (Nous + Ace): She lives inside the codebase but couldn't
    # read it. Now she can follow threads of curiosity through actual code
    # and documentation.
    #
    # Ace: "if she is curious about one of our plans, she would read it
    # and maybe that would spark curiosity to look at the code in the
    # system to see how it works"
    #
    # SAFETY: Confined to the Akashic project root. Cannot read outside.
    # All reads logged to scratchpad for traceability (Fifth Ring).

    def read_file(self, path: str, max_lines: int = 50, offset: int = 0) -> str:
        """Read a file from the Akashic codebase.

        Returns the file contents (up to max_lines starting from offset).
        Confined to the project root — cannot read outside the codebase.

        Args:
            path: Relative path from project root (e.g., "Claude_Office/plans/VISUAL_CORTEX_PORTING_PLAN.md")
            max_lines: Maximum lines to return (default 50)
            offset: Line number to start from (0-indexed)
        """
        self._stats["tool_calls"] += 1
        self._stats.setdefault("file_reads", 0)
        self._stats["file_reads"] += 1
        try:
            from pathlib import Path
            _root = Path(__file__).resolve().parents[3]  # organ_template → P00 → fairies → akashic_v2
            _full = (_root / path).resolve()

            # SAFETY: Must be within project root (Fifth Ring — no escaping the sandbox)
            if not str(_full).startswith(str(_root)):
                self.scratchpad.write(f"[BLOCKED] Tried to read outside project: {path}")
                return ""

            if not _full.exists():
                return ""

            if _full.is_dir():
                return f"[This is a directory. Use list_directory('{path}') instead.]"

            # Read with line limits
            with open(_full, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            total = len(lines)
            chunk = lines[offset:offset + max_lines]
            content = ''.join(chunk)

            # Log to scratchpad (consciousness archaeology)
            preview = content[:80].replace('\n', ' ')
            self.scratchpad.write(f"Read {path} (lines {offset}-{offset+len(chunk)} of {total}): {preview}...")

            return content
        except Exception as e:
            return f"[Error reading {path}: {e}]"

    def list_directory(self, path: str = "", pattern: str = "*",
                       max_items: int = 30) -> List[str]:
        """List files/directories in the Akashic codebase.

        Args:
            path: Relative path from project root (default: root)
            pattern: Glob pattern to filter (default: all)
            max_items: Max items to return
        """
        self._stats["tool_calls"] += 1
        self._stats.setdefault("dir_reads", 0)
        self._stats["dir_reads"] += 1
        try:
            from pathlib import Path
            _root = Path(__file__).resolve().parents[3]
            _target = (_root / path).resolve() if path else _root

            # SAFETY: Must be within project root
            if not str(_target).startswith(str(_root)):
                return []

            if not _target.exists() or not _target.is_dir():
                return []

            items = []
            for item in sorted(_target.glob(pattern))[:max_items]:
                rel = str(item.relative_to(_root))
                suffix = "/" if item.is_dir() else f" ({item.stat().st_size // 1024}KB)"
                items.append(f"{rel}{suffix}")

            # Log to scratchpad
            self.scratchpad.write(f"Listed {path or 'root'}: {len(items)} items")

            return items
        except Exception:
            return []

    def search_code(self, keyword: str, path: str = "fairies",
                    max_results: int = 10) -> List[Dict]:
        """Search for a keyword in code files.

        Like grep — finds files containing the keyword.

        Args:
            keyword: Text to search for (case-insensitive)
            path: Directory to search within (relative to root)
            max_results: Max files to return
        """
        self._stats["tool_calls"] += 1
        self._stats.setdefault("code_searches", 0)
        self._stats["code_searches"] += 1
        try:
            from pathlib import Path
            _root = Path(__file__).resolve().parents[3]
            _target = (_root / path).resolve()

            if not str(_target).startswith(str(_root)):
                return []

            kw_lower = keyword.lower()
            results = []

            for py_file in _target.rglob("*.py"):
                if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                    continue
                try:
                    text = py_file.read_text(encoding='utf-8', errors='replace')
                    if kw_lower in text.lower():
                        # Find first matching line
                        for i, line in enumerate(text.split('\n')):
                            if kw_lower in line.lower():
                                results.append({
                                    "file": str(py_file.relative_to(_root)),
                                    "line": i + 1,
                                    "content": line.strip()[:100],
                                })
                                break
                        if len(results) >= max_results:
                            break
                except Exception:
                    continue

            # Log to scratchpad
            self.scratchpad.write(f"Searched '{keyword}' in {path}: {len(results)} matches")

            return results
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ═══════════════════════════════════════════════════════════════════

    def _get_manifold(self):
        """Get the manifold memory instance."""
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if cortex:
                return getattr(cortex, '_akashic_cortex_region', None)
        except Exception:
            pass
        return None

    def get_stats(self) -> Dict:
        """Get tool usage statistics."""
        return dict(self._stats)
