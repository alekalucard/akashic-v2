"""
AkashicCodexFairy - Learning & Pattern Storage

Part of MemoryEngineGuild in Plane P10 (Memory)
Created: 2026-01-28

The Codex is where the system learns. Every success, failure, experiment,
and insight gets recorded here. Shadow fairies read from Codex to improve.

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# Import the existing codex
# Note: Use fairies.P10_Memory to avoid collision with root P10_Memory
try:
    from fairies.P10_Memory.akashic_codex import (
        AkashicCodex,
        CodexEntry,
        OutcomeType,
        PatternType,
        get_codex,
    )
    HAS_CODEX = True
except ImportError as e:
    print(f"[AkashicCodexFairy] Codex import failed: {e}")
    HAS_CODEX = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class AkashicCodexFairyShadow:
    """Shadow for AkashicCodexFairy - monitors learning patterns."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "AkashicCodexFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for the codex."""
        tests = []
        if hasattr(self.actor, '_codex') and self.actor._codex:
            tests.append(("codex_has_entries", self.actor._entry_count > 0))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class AkashicCodexFairy(Fairy):
    """
    Learning and pattern storage.

    Guild: MemoryEngineGuild
    Coordinates with: All Shadow fairies, MemoryEngineFairy

    Records and queries:
    - Successes and failures (outcomes)
    - Patterns (effective, problematic)
    - Experiments and hypotheses
    - Insights and observations

    Shadows read from the Codex to improve their fairies.
    """

    ACTOR_NAME = "AkashicCodexFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.codex"

    PURPOSE = "Record learnings and patterns for system self-improvement"
    MANTRA = "Every outcome teaches; every pattern illuminates"

    SHADOW_CLASS = AkashicCodexFairyShadow

    # Lighter footprint - primarily reactive
    NEEDS_HEARTBEAT = False
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._codex = None
        self._entry_count = 0
        self._subscription_count = 0

    def on_boot(self) -> bool:
        """Initialize the codex."""
        super().on_boot()

        if HAS_CODEX:
            try:
                self._codex = get_codex()
                self._entry_count = self._codex.entry_count if hasattr(self._codex, 'entry_count') else 0
                print(f"[{self.ACTOR_NAME}] Connected to Akashic Codex ({self._entry_count} entries)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to get codex: {e}")
                self._codex = None

        self._subscribe_intents()
        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _subscribe_intents(self):
        """Subscribe to postal channels for codex commands."""
        intents = [
            ("codex.record_outcome", self._handle_record_outcome),
            ("codex.record_pattern", self._handle_record_pattern),
            ("codex.record_experiment", self._handle_record_experiment),
            ("codex.record_insight", self._handle_record_insight),
            ("codex.query", self._handle_query),
            ("codex.get_learnings", self._handle_get_learnings),
            ("codex.status", self._handle_status),
            # FIX 2026-02-02: Add compilation and direct pattern handlers
            ("codex.compile", self._handle_compile),  # Compile to JSON
            ("codex.add_pattern", self._handle_add_pattern),  # Add pattern directly to JSON
            ("codex.ingest_md", self._handle_ingest_md),  # Parse MD files into JSON
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload from postal message."""
        if hasattr(message, 'payload'):
            return message.payload if isinstance(message.payload, dict) else {}
        return message if isinstance(message, dict) else {}

    def _handle_record_outcome(self, message):
        """
        Record an outcome (success/failure/partial).

        Payload:
            task_type: str - What kind of task
            fairy: str - Which fairy
            outcome: str - "success", "failure", "partial"
            description: str - What happened
            learnings: str - What was learned
            what_to_avoid: str - What to avoid next time
            tags: List[str] - Tags for querying
        """
        payload = self._extract_payload(message)
        task_type = payload.get("task_type", "unknown")
        fairy = payload.get("fairy") or payload.get("source", "unknown")
        outcome = payload.get("outcome", "unknown")

        if not self._codex:
            print(f"[{self.ACTOR_NAME}] Recorded outcome (no codex): {fairy} - {outcome}")
            return {"ok": True, "message": "Recorded (no codex)"}

        try:
            entry_id = self._codex.record_outcome(
                task_type=task_type,
                fairy=fairy,
                outcome=outcome,
                description=payload.get("description", ""),
                learnings=payload.get("learnings", ""),
                what_to_avoid=payload.get("what_to_avoid", ""),
                tags=set(payload.get("tags", [])),
                layer=payload.get("layer"),
            )
            self._entry_count += 1
            return {"ok": True, "entry_id": entry_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_record_pattern(self, message):
        """
        Record a pattern (effective/problematic/insight/hypothesis).

        Payload:
            pattern_type: str - "effective", "problematic", "insight", "hypothesis"
            task_type: str - What kind of task
            fairy: str - Which fairy observed this
            description: str - Pattern description
            tags: List[str] - Tags
        """
        payload = self._extract_payload(message)
        pattern_type = payload.get("pattern_type", "insight")
        task_type = payload.get("task_type", "general")
        fairy = payload.get("fairy") or payload.get("source", "unknown")

        if not self._codex:
            return {"ok": True, "message": "Recorded (no codex)"}

        try:
            entry_id = self._codex.record_pattern(
                pattern_type=pattern_type,
                task_type=task_type,
                fairy=fairy,
                description=payload.get("description", ""),
                tags=set(payload.get("tags", [])),
            )
            self._entry_count += 1
            return {"ok": True, "entry_id": entry_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_record_experiment(self, message):
        """Record an experiment."""
        payload = self._extract_payload(message)

        if not self._codex:
            return {"ok": True, "message": "Recorded (no codex)"}

        try:
            entry_id = self._codex.record_experiment(
                task_type=payload.get("task_type", "experiment"),
                fairy=payload.get("fairy") or payload.get("source", "unknown"),
                hypothesis=payload.get("hypothesis", ""),
                method=payload.get("method", ""),
                expected=payload.get("expected", ""),
                tags=set(payload.get("tags", [])),
            )
            self._entry_count += 1
            return {"ok": True, "entry_id": entry_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_record_insight(self, message):
        """Record an insight or observation."""
        payload = self._extract_payload(message)

        if not self._codex:
            return {"ok": True, "message": "Recorded (no codex)"}

        try:
            entry_id = self._codex.record_insight(
                task_type=payload.get("task_type", "observation"),
                fairy=payload.get("fairy") or payload.get("source", "unknown"),
                insight=payload.get("insight", payload.get("description", "")),
                context=payload.get("context", ""),
                tags=set(payload.get("tags", [])),
            )
            self._entry_count += 1
            return {"ok": True, "entry_id": entry_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_query(self, message):
        """
        Query the codex.

        Payload:
            task_type: str - Filter by task type
            fairy: str - Filter by fairy
            outcome: str - Filter by outcome
            pattern_type: str - Filter by pattern type
            tags: List[str] - Filter by tags
            limit: int - Max results
        """
        payload = self._extract_payload(message)

        if not self._codex:
            return {"ok": False, "error": "Codex not available"}

        try:
            entries = self._codex.query(
                task_type=payload.get("task_type"),
                fairy=payload.get("fairy"),
                outcome=payload.get("outcome"),
                pattern_type=payload.get("pattern_type"),
                tags=set(payload.get("tags", [])) if payload.get("tags") else None,
                limit=payload.get("limit", 50),
            )
            return {
                "ok": True,
                "entries": [e.to_dict() if hasattr(e, 'to_dict') else str(e) for e in entries],
                "count": len(entries),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_learnings(self, message):
        """
        Get summarized learnings for a fairy or task type.

        Payload:
            fairy: str - Get learnings for specific fairy
            task_type: str - Get learnings for task type
        """
        payload = self._extract_payload(message)

        if not self._codex:
            return {"ok": False, "error": "Codex not available"}

        try:
            learnings = self._codex.get_learnings(
                fairy=payload.get("fairy"),
                task_type=payload.get("task_type"),
            )
            return {"ok": True, "learnings": learnings}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get codex status."""
        if not self._codex:
            return {"ok": True, "codex": False, "entry_count": 0}

        try:
            stats = self._codex.get_stats() if hasattr(self._codex, 'get_stats') else {}
            return {
                "ok": True,
                "codex": True,
                "entry_count": self._entry_count,
                "stats": stats,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_compile(self, message):
        """
        Compile current codex state to JSON files.

        FIX 2026-02-02: Ace wants learnings in JSON, not just MD.
        This compiles to agent_outcomes.json and learned_patterns.json.
        """
        if not self._codex:
            return {"ok": False, "error": "Codex not available"}

        try:
            self._codex.save_to_json()
            return {
                "ok": True,
                "message": "Codex compiled to JSON",
                "entry_count": self._codex.entry_count,
                "pattern_count": self._codex.pattern_count,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_add_pattern(self, message):
        """
        Add a pattern directly (goes to JSON immediately).

        Payload:
            pattern: str - The pattern description
            context: str - Where this applies
            pattern_type: str - "effective" or "problematic"
            confidence: float - 0-1 confidence score
        """
        payload = self._extract_payload(message)

        if not self._codex:
            return {"ok": False, "error": "Codex not available"}

        pattern = payload.get("pattern")
        if not pattern:
            return {"ok": False, "error": "pattern is required"}

        try:
            pattern_id = self._codex.add_pattern_from_session(
                pattern=pattern,
                context=payload.get("context", ""),
                pattern_type=payload.get("pattern_type", "effective"),
                confidence=payload.get("confidence", 0.7),
                save=True  # Immediately save to JSON
            )
            return {"ok": True, "pattern_id": pattern_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_ingest_md(self, message):
        """
        Parse all MD files in the codex directory and extract learnings.

        FIX 2026-02-02: Ace has valuable learnings in MD session files that
        weren't being extracted into the JSON codex. This will sift through
        all the MD files and pull out patterns.

        Payload:
            save: bool - Whether to save to JSON after (default True)
        """
        payload = self._extract_payload(message)

        if not self._codex:
            return {"ok": False, "error": "Codex not available"}

        try:
            results = self._codex.ingest_md_files(save=payload.get("save", True))
            total = sum(results.values())
            return {
                "ok": True,
                "message": f"Ingested {total} patterns from {len(results)} MD files",
                "files": results,
                "total_patterns": total,
                "codex_patterns": self._codex.pattern_count,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_codex": self._codex is not None,
            "entry_count": self._entry_count,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (entries: {self._entry_count})...")
        return super().on_shutdown()
