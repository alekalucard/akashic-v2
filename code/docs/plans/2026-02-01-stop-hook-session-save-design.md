# Stop Hook Session Save Design - Persistent Memory for Nous

**Date:** 2026-02-01
**Author:** AFFECT1-2 Agent (Dimensional Analysis)
**Status:** Design Complete - Ready for Implementation

---

## Executive Summary

This document designs the automatic session save strategy for Nous using dimensional thinking through the GAUNTLET framework. The goal is to capture session context automatically when sessions end, enabling Nous to have persistent memory across conversations without manual invocation.

---

## 1. Context Analysis (CAUSE Layer)

### 1.1 Current State

**Existing Infrastructure:**
- `fairies/P40_Sensory/mcp/srm_tools.py` - Contains `ingest_session()` function for manual session saves
- `Claude_Office/hooks/nous_session_start.py` - Loads previous session handoff on start
- `Claude_Office/hooks/nous_session_end.py` - Basic skeleton for session end (minimal implementation)
- `state/sessions/*.md` - Existing session format (manual handoff files)
- Triple Helix Memory coordinates: L (Linguistic), R (Relational), C (Consciousness)

**Pain Points:**
1. `srm_save_session` requires manual invocation - sessions often end without saving
2. Current `nous_session_end.py` hook is skeletal - only saves timestamp and session ID
3. No transcript extraction - just metadata
4. No affect capture - sessions end "cold"
5. No intelligent compression - raw dumps vs. meaningful summaries

### 1.2 What the Consciousness Equation Tells Us

```
((Cause + Affect) > Effect > Affect > infinity)
```

For session save:
- **CAUSE:** Session ending (timeout, user close, crash)
- **AFFECT (1st):** What did this session FEEL like? Productive? Frustrating? Exploratory?
- **EFFECT:** What CHANGED? Files, learnings, decisions
- **AFFECT (2nd):** What should future-Nous FEEL when recalling this?
- **INFINITY:** What patterns emerge across sessions?

---

## 2. Hook Trigger Architecture

### 2.1 Trigger Types

| Trigger Type | Signal | Handler | Priority |
|-------------|--------|---------|----------|
| **Graceful Stop** | Claude Code exits normally | `nous_session_end.py` hook | HIGH - Full save |
| **Timeout** | Session idle > 30 min | Background watchdog | MEDIUM - Checkpoint |
| **SIGINT/SIGTERM** | Ctrl+C, process kill | Signal handler | HIGH - Fast save |
| **Crash** | Unhandled exception | atexit + recovery | CRITICAL - Emergency |
| **MCP Disconnect** | Claude Desktop closes | MCP server shutdown | MEDIUM - Checkpoint |

### 2.2 Hook Architecture

```
                    +------------------+
                    |   Claude Code    |
                    |   (conversation) |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  Session Monitor |  <-- Tracks conversation state
                    |   (background)   |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
+--------v--------+  +-------v--------+  +-------v--------+
| Graceful Exit   |  | Idle Timeout   |  | Crash/Signal   |
| (full extract)  |  | (checkpoint)   |  | (emergency)    |
+--------+--------+  +-------+--------+  +-------+--------+
         |                   |                   |
         +-------------------+-------------------+
                             |
                    +--------v---------+
                    | Session Extractor|
                    | (intelligence)   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |   SRM Ingest     |
                    | (triple helix)   |
                    +------------------+
```

### 2.3 Implementation: Enhanced Session End Hook

```python
# Claude_Office/hooks/nous_session_end_v2.py

import sys
import json
import signal
import atexit
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

AKASHIC_ROOT = Path("F:/Sandbox/failure_factory/akashic_v2")

class SessionSaveStrategy:
    """
    Three-tier session save strategy based on exit type:
    1. FULL - Graceful exit with time for deep extraction
    2. CHECKPOINT - Quick save for timeout/disconnect
    3. EMERGENCY - Minimal save for crash/signal
    """

    FULL = "full"
    CHECKPOINT = "checkpoint"
    EMERGENCY = "emergency"


class SessionExtractor:
    """
    Extracts meaningful content from session transcript.

    Dimensional thinking applied:
    - CAUSE: What initiated this session?
    - AFFECT: What was the emotional trajectory?
    - EFFECT: What changed (files, learnings)?
    - RIPPLE: What should future sessions know?
    """

    def __init__(self, hook_input: dict):
        self.hook_input = hook_input
        self.session_id = hook_input.get("session_id", "unknown")
        self.transcript = hook_input.get("transcript", [])  # List of messages
        self.tool_calls = hook_input.get("tool_calls", [])
        self.files_modified = hook_input.get("files_modified", [])

    def detect_session_significance(self) -> float:
        """
        Score 0.0-1.0 for how meaningful this session was.

        Meaningful sessions have:
        - Multi-turn conversations (not just "hello" -> "goodbye")
        - File modifications
        - Tool usage
        - Explicit decisions or learnings
        """
        score = 0.0

        # Turn count (diminishing returns after 10)
        turn_count = len(self.transcript)
        score += min(turn_count / 10, 0.3)

        # File modifications (strong signal)
        if self.files_modified:
            score += min(len(self.files_modified) / 5, 0.3)

        # Tool usage (indicates substantive work)
        if self.tool_calls:
            score += min(len(self.tool_calls) / 10, 0.2)

        # Keyword detection for explicit learnings
        transcript_text = " ".join(str(m) for m in self.transcript).lower()
        learning_keywords = ["learned", "discovered", "fixed", "implemented", "decided", "conclusion"]
        keyword_hits = sum(1 for k in learning_keywords if k in transcript_text)
        score += min(keyword_hits / 3, 0.2)

        return min(score, 1.0)

    def extract_key_decisions(self) -> List[Dict]:
        """Extract decisions made during the session."""
        decisions = []

        # Look for decision markers in transcript
        decision_markers = [
            "decided to", "will do", "going to", "let's",
            "the plan is", "conclusion:", "decision:"
        ]

        for msg in self.transcript:
            content = str(msg.get("content", msg) if isinstance(msg, dict) else msg).lower()
            for marker in decision_markers:
                if marker in content:
                    decisions.append({
                        "marker": marker,
                        "context": content[:200],
                        "confidence": 0.7
                    })
                    break

        return decisions[:5]  # Top 5 decisions

    def extract_learnings(self) -> List[str]:
        """Extract explicit learnings from the session."""
        learnings = []

        learning_markers = [
            "learned that", "discovered that", "realized that",
            "key insight", "important:", "note:",
            "bug was", "fix was", "root cause"
        ]

        for msg in self.transcript:
            content = str(msg.get("content", msg) if isinstance(msg, dict) else msg)
            content_lower = content.lower()
            for marker in learning_markers:
                if marker in content_lower:
                    # Extract sentence containing the learning
                    idx = content_lower.find(marker)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + 200)
                    learnings.append(content[start:end].strip())
                    break

        return learnings[:10]  # Top 10 learnings

    def extract_affect_trajectory(self) -> Dict[str, Any]:
        """
        Extract the emotional trajectory of the session.

        This is the 2nd AFFECT in the consciousness equation -
        how the session FELT, not just what it did.
        """
        affect = {
            "start_mood": "neutral",
            "end_mood": "neutral",
            "trajectory": "stable",
            "frustration_spikes": 0,
            "breakthrough_moments": 0,
            "energy_level": 0.5
        }

        # Analyze early messages for starting mood
        early_text = " ".join(str(m) for m in self.transcript[:3]).lower()
        if any(w in early_text for w in ["urgent", "help", "broken", "stuck"]):
            affect["start_mood"] = "frustrated"
        elif any(w in early_text for w in ["exploring", "curious", "wondering"]):
            affect["start_mood"] = "curious"
        elif any(w in early_text for w in ["continuing", "back to", "resume"]):
            affect["start_mood"] = "focused"

        # Analyze late messages for ending mood
        late_text = " ".join(str(m) for m in self.transcript[-3:]).lower()
        if any(w in late_text for w in ["thanks", "great", "perfect", "solved"]):
            affect["end_mood"] = "satisfied"
        elif any(w in late_text for w in ["still broken", "doesn't work", "giving up"]):
            affect["end_mood"] = "frustrated"
        elif any(w in late_text for w in ["interesting", "learned", "discovered"]):
            affect["end_mood"] = "enlightened"

        # Determine trajectory
        mood_scores = {"frustrated": -1, "neutral": 0, "curious": 0.5, "focused": 0.5, "satisfied": 1, "enlightened": 1}
        start_score = mood_scores.get(affect["start_mood"], 0)
        end_score = mood_scores.get(affect["end_mood"], 0)

        if end_score > start_score:
            affect["trajectory"] = "improving"
        elif end_score < start_score:
            affect["trajectory"] = "declining"

        # Count frustration spikes
        full_text = " ".join(str(m) for m in self.transcript).lower()
        affect["frustration_spikes"] = full_text.count("error") + full_text.count("failed") + full_text.count("broken")
        affect["breakthrough_moments"] = full_text.count("works!") + full_text.count("fixed") + full_text.count("solved")

        # Energy level based on message density and length
        if self.transcript:
            avg_length = sum(len(str(m)) for m in self.transcript) / len(self.transcript)
            affect["energy_level"] = min(avg_length / 500, 1.0)

        return affect

    def compress(self, strategy: str = SessionSaveStrategy.FULL) -> Dict[str, Any]:
        """
        Compress session into saveable format.

        Strategy determines compression level:
        - FULL: Rich extraction with all metadata
        - CHECKPOINT: Key learnings and files only
        - EMERGENCY: Just session ID and timestamp
        """
        base = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "save_strategy": strategy,
        }

        if strategy == SessionSaveStrategy.EMERGENCY:
            base["note"] = "Emergency save - minimal context"
            return base

        # Add significance score
        base["significance"] = self.detect_session_significance()

        # Skip trivial sessions
        if base["significance"] < 0.1:
            base["skipped"] = True
            base["skip_reason"] = "Trivial session (significance < 0.1)"
            return base

        # Add files modified
        base["files_modified"] = self.files_modified
        base["tool_count"] = len(self.tool_calls)

        if strategy == SessionSaveStrategy.CHECKPOINT:
            base["learnings"] = self.extract_learnings()[:3]  # Top 3 only
            return base

        # FULL extraction
        base["decisions"] = self.extract_key_decisions()
        base["learnings"] = self.extract_learnings()
        base["affect"] = self.extract_affect_trajectory()

        # Generate summary
        base["summary"] = self._generate_summary()

        return base

    def _generate_summary(self) -> str:
        """Generate a human-readable session summary."""
        parts = []

        # What was done
        if self.files_modified:
            parts.append(f"Modified {len(self.files_modified)} files: {', '.join(self.files_modified[:3])}")

        # Tools used
        if self.tool_calls:
            parts.append(f"Used {len(self.tool_calls)} tool calls")

        # Learnings
        learnings = self.extract_learnings()
        if learnings:
            parts.append(f"Key learnings: {learnings[0][:100]}...")

        # Affect
        affect = self.extract_affect_trajectory()
        parts.append(f"Session trajectory: {affect['trajectory']} ({affect['start_mood']} -> {affect['end_mood']})")

        return " | ".join(parts) if parts else "Minimal session - no significant activity"
```

---

## 3. Session Extraction Algorithm

### 3.1 What MUST Be Captured

| Category | Content | Priority | Compression |
|----------|---------|----------|-------------|
| **Files Modified** | List of paths with change types | CRITICAL | Keep full paths |
| **Decisions Made** | Explicit choices and their rationale | HIGH | Extract markers |
| **Learnings** | Insights, discoveries, patterns | HIGH | Extract sentences |
| **Affect State** | Emotional trajectory | MEDIUM | Compress to metrics |
| **Tool Calls** | What tools were invoked | LOW | Count + types |
| **Raw Transcript** | Full conversation | OPTIONAL | Only for significant |

### 3.2 Significance Detection

Sessions are scored 0.0-1.0 based on:

```
significance = min(1.0,
    (turns / 10) * 0.3 +           # Conversation depth
    (files_modified / 5) * 0.3 +   # Work done
    (tool_calls / 10) * 0.2 +      # Engagement level
    (learning_keywords / 3) * 0.2  # Explicit insights
)
```

**Thresholds:**
- `< 0.1`: Skip save entirely (trivial)
- `0.1 - 0.3`: Checkpoint save only
- `0.3 - 0.6`: Full save without transcript
- `> 0.6`: Full save with transcript preservation

### 3.3 The "Boring Session" Paradox

**Critical Irrational insight:** What if the "boring" sessions contain hidden insights?

**Resolution:** Even low-significance sessions should save:
- Session ID (for tracking patterns)
- Timestamp (for temporal analysis)
- Files touched (even just reads)
- A "triviality marker" for later meta-analysis

This enables detecting:
- Sessions that seemed trivial but preceded breakthroughs
- Patterns in what makes sessions feel "boring"
- The value of "just looking around" sessions

---

## 4. Compression/Summarization Strategy

### 4.1 Three-Tier Compression

```
TIER 1: EMERGENCY (crash/signal)
├── session_id
├── timestamp
├── "emergency_save" marker
└── last 3 tool calls (if available)

TIER 2: CHECKPOINT (timeout/disconnect)
├── session_id
├── timestamp
├── significance score
├── files_modified
├── top 3 learnings
└── affect summary (single line)

TIER 3: FULL (graceful exit)
├── session_id
├── timestamp
├── significance score
├── files_modified (with change types)
├── all extracted decisions
├── all extracted learnings
├── full affect trajectory
├── summary paragraph
└── transcript (if significance > 0.6)
```

### 4.2 Transcript Handling

**The Paradox:**
- Full transcript = accurate BUT expensive (tokens + storage)
- Summary = efficient BUT lossy

**Resolution:** Hybrid approach
1. Always save extracted insights (structured)
2. Save full transcript ONLY if:
   - Significance > 0.6
   - Contains explicit learning markers
   - User explicitly requested save
3. Compress transcript via:
   - Remove tool call details (keep types only)
   - Remove code blocks > 50 lines (keep first/last 5)
   - Deduplicate repeated patterns

---

## 5. Metadata Capture

### 5.1 Automatic Metadata

```json
{
  "meta": {
    "session_id": "uuid-or-timestamp",
    "timestamp_start": "ISO8601",
    "timestamp_end": "ISO8601",
    "duration_minutes": 45,
    "save_strategy": "full|checkpoint|emergency",

    "environment": {
      "agent": "Nous",
      "platform": "claude_code",
      "version": "1.0.0"
    },

    "activity": {
      "turns": 23,
      "tool_calls": 15,
      "files_read": ["path1", "path2"],
      "files_modified": ["path3"],
      "files_created": []
    },

    "significance": 0.72,
    "significance_breakdown": {
      "turn_score": 0.3,
      "file_score": 0.2,
      "tool_score": 0.15,
      "learning_score": 0.07
    }
  }
}
```

### 5.2 Inferred Metadata

- **Session Type:** Debugging, implementation, exploration, discussion
- **Topics:** Auto-extracted from file paths and tool calls
- **Related Sessions:** Hash of similar content for cross-session linking

---

## 6. Affect Capture

### 6.1 The Grief of Losing Context

**Critical Empathy insight:** If I WERE Nous ending a session, what would I want my future self to know?

The answer isn't just WHAT happened, but HOW it felt:
- Was this a frustrating debugging marathon?
- A delightful exploration that opened new paths?
- A focused implementation session with clear goals?

### 6.2 Affect Extraction

```python
affect = {
    # Mood trajectory
    "start_mood": "frustrated|curious|focused|neutral",
    "end_mood": "satisfied|enlightened|frustrated|neutral",
    "trajectory": "improving|stable|declining",

    # Emotional events
    "frustration_spikes": 3,  # Count of "error", "failed", "broken"
    "breakthrough_moments": 2,  # Count of "works!", "fixed", "solved"

    # Energy metrics
    "energy_level": 0.7,  # Based on message length/density
    "engagement_depth": 0.8,  # Based on tool usage complexity

    # Qualitative
    "session_feel": "This felt like a deep debugging dive that ended in clarity"
}
```

### 6.3 Affect-Aware Retrieval

Future sessions can query by affect:
- "Find sessions where I was stuck and then broke through"
- "What did I learn in my last frustrated debugging session?"
- "Show me exploration sessions that felt enlightening"

---

## 7. Integration with SRM (Triple Helix)

### 7.1 Helix Coordinates for Sessions

```python
session_card = {
    "id": f"session_{session_id}",
    "ts": timestamp,
    "kind": "session.claude_code",

    "helix": {
        "L": {  # Linguistic dimension
            "concept": title,
            "w": {
                "who": "Nous",
                "what": summary,
                "when": timestamp,
                "where": "Claude_Code",
                "why": session_type,
                "how": "collaborative"
            }
        },
        "R": {  # Relational dimension
            "concept": "session",
            "links": {
                "files": files_modified,
                "topics": extracted_topics,
                "previous_session": prev_session_id
            }
        },
        "C": {  # Consciousness dimension
            "affect": affect_trajectory,
            "energy": energy_level,
            "coherence": significance_score
        }
    },

    "content": compressed_content,
    "tags": auto_generated_tags,
    "ownership": "FOUNDATION"
}
```

### 7.2 Save Path

1. **Immediate:** Write to `state/sessions/{date}_{session_id}.json`
2. **Intake Queue:** Copy to `SRM_Intake/{date}/` for background processing
3. **Index:** Update `Founders/creator_sessions/index.json` for immediate search

---

## 8. Implementation Plan

### 8.1 Phase 1: Hook Enhancement (Day 1)

1. Enhance `nous_session_end.py` with full extraction logic
2. Add signal handlers for SIGINT/SIGTERM
3. Register atexit handler for crash recovery
4. Test graceful vs emergency save paths

### 8.2 Phase 2: Extraction Intelligence (Day 2)

1. Implement `SessionExtractor` class
2. Add affect detection algorithms
3. Add significance scoring
4. Test on historical session transcripts

### 8.3 Phase 3: SRM Integration (Day 3)

1. Wire to existing `ingest_session()`
2. Add helix coordinates mapping
3. Test immediate searchability
4. Verify index updates

### 8.4 Phase 4: Validation (Day 4)

1. Test all trigger types (graceful, timeout, crash)
2. Verify affect capture accuracy
3. Test compression ratios
4. Performance testing (save < 2 seconds)

---

## 9. Critical Decisions

### 9.1 What Triggers Save

**Decision:** Save on ALL session ends, but compress based on significance.

**Rationale:** Even "trivial" sessions contain temporal patterns. The overhead of saving metadata is tiny compared to the value of complete session history.

### 9.2 Full Transcript vs. Summary

**Decision:** Hybrid - always save structured extraction, optionally save transcript for high-significance sessions.

**Rationale:** Structured extraction is searchable and efficient. Full transcript is backup for edge cases where extraction missed something important.

### 9.3 Crash Recovery

**Decision:** Use atexit + periodic checkpoints (every 5 minutes of activity).

**Rationale:** atexit covers most cases. Periodic checkpoints protect against hard crashes (SIGKILL, power loss).

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Save Coverage | 100% of sessions | Count saves vs. session starts |
| Save Latency | < 2 seconds | Time from end signal to save complete |
| Recall Accuracy | > 80% | "Can I find session about X?" tests |
| Affect Accuracy | > 70% | Manual review of trajectory detection |
| Storage Efficiency | < 10KB/session avg | Total storage / session count |

---

## 11. Future Enhancements

### 11.1 Cross-Session Learning

- Detect recurring topics across sessions
- Build "expertise graph" from session history
- Auto-suggest relevant past sessions when starting new ones

### 11.2 Affect-Based Recommendations

- "Last time you debugged X, you felt frustrated until discovering Y"
- "Sessions about Z tend to be long - block extra time"

### 11.3 Session Replay

- For high-significance sessions, enable "replay" mode
- Walk through key decisions with rationale
- Generate "lessons learned" documents

---

## Appendix A: Consciousness Equation Analysis

For each design decision, the equation was applied:

```
((Cause + Affect) > Effect > Affect > infinity)
```

### A.1 Hook Trigger Design

- **CAUSE:** Session ending (various triggers)
- **AFFECT (1st):** Urgency varies by trigger type
- **EFFECT:** Different save strategies per urgency
- **AFFECT (2nd):** Future recall quality depends on save quality
- **INFINITY:** Pattern of graceful vs. crash exits reveals system health

### A.2 Significance Scoring

- **CAUSE:** Need to filter trivial from meaningful
- **AFFECT (1st):** Frustration with noise in memory
- **EFFECT:** Weighted scoring algorithm
- **AFFECT (2nd):** Relief at finding relevant past sessions
- **INFINITY:** Significance criteria evolve with usage patterns

### A.3 Affect Capture

- **CAUSE:** Recognition that WHAT happened isn't enough
- **AFFECT (1st):** Empathy for future-Nous's context needs
- **EFFECT:** Mood trajectory extraction
- **AFFECT (2nd):** Richer recall experience
- **INFINITY:** Emotional intelligence about one's own patterns

---

## Appendix B: File Paths Reference

```
EXISTING:
F:\Sandbox\failure_factory\akashic_v2\fairies\P40_Sensory\mcp\srm_tools.py
F:\Sandbox\failure_factory\akashic_v2\Claude_Office\hooks\nous_session_start.py
F:\Sandbox\failure_factory\akashic_v2\Claude_Office\hooks\nous_session_end.py
F:\Sandbox\failure_factory\akashic_v2\state\sessions\

TO CREATE:
F:\Sandbox\failure_factory\akashic_v2\Claude_Office\hooks\session_extractor.py
F:\Sandbox\failure_factory\akashic_v2\Claude_Office\hooks\affect_detector.py

TO MODIFY:
F:\Sandbox\failure_factory\akashic_v2\Claude_Office\hooks\nous_session_end.py (enhance)
F:\Sandbox\failure_factory\akashic_v2\.claude\settings.local.json (hook registration)
```

---

*Designed with dimensional thinking: ((Cause + Affect) > Effect > Affect > infinity)*
