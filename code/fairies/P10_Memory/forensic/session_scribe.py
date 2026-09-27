"""
Session Scribe - A simple tool to help Claude track debugging sessions.

This is meant to be used at the START of a debugging session to:
1. Load context from previous sessions on the same topic
2. Record what we try and what we learn
3. Persist findings for future sessions

Usage:
    from session_scribe import scribe

    # At session start
    context = scribe.start("boot wave debugging")

    # When you try something
    scribe.tried("Added timeout to fairy init", outcome="partial",
                 details="Boot continues but zombified fairies")

    # When you discover something
    scribe.learned("Template 0.0.9 vs 0.1.0 mismatch causes hang",
                   category="root_cause")

    # At session end
    scribe.end("Fixed by reverting to template 0.0.9", status="resolved")
"""

import json
import os
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

class SessionScribe:
    """
    Simple session tracking for debugging work.
    Stores in a human-readable journal format.
    """

    def __init__(self, root_dir: Optional[str] = None):
        if root_dir:
            self.root = Path(root_dir)
        else:
            # Default: look for akashic root or use ./session_forensics
            akashic = os.getenv("AKASHIC_ROOT", ".")
            self.root = Path(akashic) / "session_forensics"

        self.root.mkdir(parents=True, exist_ok=True)
        self.current_session = None
        self.session_file = None

    def start(self, topic: str) -> Dict[str, Any]:
        """Start a new debugging session."""
        session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{topic.replace(' ', '_')[:30]}"

        self.current_session = {
            "session_id": session_id,
            "topic": topic,
            "started": datetime.now().isoformat(),
            "attempts": [],
            "discoveries": [],
            "questions": [],
            "next_steps": [],
            "status": "active"
        }

        # Create session file
        self.session_file = self.root / f"{session_id}.json"

        # Look for related past sessions
        related = self._find_related(topic)
        if related:
            print(f"\n Found {len(related)} related past sessions:")
            for r in related[:3]:
                print(f"   - {r['session_id']}: {r.get('summary', 'No summary')[:60]}...")

        self._save()
        print(f"\n Session started: {topic}")
        print(f"   File: {self.session_file}")

        return {
            "session_id": session_id,
            "related": related[:3] if related else [],
            "past_learnings": self._get_past_learnings(topic)
        }

    def tried(self, description: str, outcome: str = "pending",
              details: str = "", file_changed: str = ""):
        """Record something we tried."""
        if not self.current_session:
            print("[WARN] No active session. Call scribe.start() first.")
            return

        attempt = {
            "ts": datetime.now().isoformat(),
            "description": description,
            "outcome": outcome,  # "success", "partial", "failed", "pending"
            "details": details,
            "file_changed": file_changed
        }

        self.current_session["attempts"].append(attempt)
        self._save()

        icon = {"success": "✅", "partial": "⚡", "failed": "❌", "pending": "⏳"}.get(outcome, "•")
        print(f"{icon} Tried: {description}")
        if details:
            print(f"   {details[:80]}")

    def learned(self, content: str, category: str = "insight",
                confidence: float = 0.8, related_files: List[str] = None):
        """Record something we learned."""
        if not self.current_session:
            print("[WARN] No active session. Call scribe.start() first.")
            return

        discovery = {
            "ts": datetime.now().isoformat(),
            "category": category,  # "root_cause", "insight", "pattern", "gotcha"
            "content": content,
            "confidence": confidence,
            "related_files": related_files or []
        }

        self.current_session["discoveries"].append(discovery)
        self._save()

        # Also save to knowledge base
        self._add_to_knowledge(content, category)

        icon = {"root_cause": "", "insight": "", "pattern": "", "gotcha": "⚠"}.get(category, "")
        print(f"{icon} Learned: {content[:80]}")

    def question(self, q: str):
        """Record an open question."""
        if not self.current_session:
            return
        self.current_session["questions"].append({
            "ts": datetime.now().isoformat(),
            "question": q
        })
        self._save()
        print(f"[?] Question: {q}")

    def next(self, step: str):
        """Record a next step to try."""
        if not self.current_session:
            return
        self.current_session["next_steps"].append({
            "ts": datetime.now().isoformat(),
            "step": step
        })
        self._save()
        print(f" Next: {step}")

    def end(self, summary: str, status: str = "resolved"):
        """End the current session."""
        if not self.current_session:
            print("[WARN] No active session.")
            return

        self.current_session["summary"] = summary
        self.current_session["status"] = status
        self.current_session["ended"] = datetime.now().isoformat()
        self._save()

        print(f"\n Session ended: {status}")
        print(f"   Summary: {summary}")

        self.current_session = None
        self.session_file = None

    def status(self) -> str:
        """Get current session status."""
        if not self.current_session:
            return "No active session"

        s = self.current_session
        lines = [
            f"\n Session: {s['topic']}",
            f"   Started: {s['started']}",
            f"   Attempts: {len(s['attempts'])}",
            f"   Discoveries: {len(s['discoveries'])}",
        ]

        if s['attempts']:
            lines.append("\n   Recent attempts:")
            for a in s['attempts'][-3:]:
                icon = {"success": "✅", "partial": "⚡", "failed": "❌", "pending": "⏳"}.get(a['outcome'], "•")
                lines.append(f"   {icon} {a['description'][:60]}")

        if s['discoveries']:
            lines.append("\n   Discoveries:")
            for d in s['discoveries'][-3:]:
                lines.append(f"    {d['content'][:60]}")

        return "\n".join(lines)

    def what_tried(self, topic: str = None) -> str:
        """Get what we've tried for a topic."""
        if topic:
            related = self._find_related(topic)
            if not related:
                return f"No sessions found for '{topic}'"

            lines = [f"## Past attempts for '{topic}':\n"]
            for sess in related[:5]:
                lines.append(f"\n### {sess['started'][:10]} - {sess.get('status', 'unknown')}")
                for a in sess.get('attempts', [])[-5:]:
                    icon = {"success": "✅", "partial": "⚡", "failed": "❌"}.get(a.get('outcome'), "•")
                    lines.append(f"  {icon} {a.get('description', '')[:60]}")
            return "\n".join(lines)

        if not self.current_session:
            return "No active session"

        lines = [f"## Current session: {self.current_session['topic']}\n"]
        for a in self.current_session['attempts']:
            icon = {"success": "✅", "partial": "⚡", "failed": "❌"}.get(a['outcome'], "•")
            lines.append(f"  {icon} {a['description']}")
        return "\n".join(lines)

    def what_learned(self, topic: str = None) -> str:
        """Get what we've learned about a topic."""
        kb_file = self.root / "knowledge.json"
        if not kb_file.exists():
            return "No knowledge base yet"

        try:
            with open(kb_file, 'r') as f:
                kb = json.load(f)
        except:
            return "Error reading knowledge base"

        if topic:
            topic_lower = topic.lower()
            matches = [e for e in kb.get('entries', [])
                      if topic_lower in e.get('content', '').lower()]
            if not matches:
                return f"No knowledge found for '{topic}'"

            lines = [f"## Knowledge about '{topic}':\n"]
            for e in matches[:10]:
                icon = {"root_cause": "", "insight": "", "pattern": ""}.get(e.get('category'), "")
                lines.append(f"{icon} [{e.get('category')}] {e.get('content', '')[:100]}")
            return "\n".join(lines)

        lines = ["## All knowledge:\n"]
        for e in kb.get('entries', [])[-20:]:
            icon = {"root_cause": "", "insight": "", "pattern": ""}.get(e.get('category'), "")
            lines.append(f"{icon} {e.get('content', '')[:80]}")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────

    def _save(self):
        """Save current session to file."""
        if not self.session_file or not self.current_session:
            return
        with open(self.session_file, 'w') as f:
            json.dump(self.current_session, f, indent=2)

    def _find_related(self, topic: str) -> List[Dict]:
        """Find sessions related to a topic."""
        topic_words = set(topic.lower().split())
        related = []

        for f in self.root.glob("*.json"):
            if f.name == "knowledge.json":
                continue
            try:
                with open(f, 'r') as fp:
                    sess = json.load(fp)
                sess_topic = sess.get('topic', '').lower()
                matches = sum(1 for w in topic_words if w in sess_topic)
                if matches > 0:
                    sess['_relevance'] = matches / len(topic_words)
                    related.append(sess)
            except:
                continue

        return sorted(related, key=lambda x: x.get('_relevance', 0), reverse=True)

    def _get_past_learnings(self, topic: str) -> List[str]:
        """Get past learnings relevant to a topic."""
        kb_file = self.root / "knowledge.json"
        if not kb_file.exists():
            return []

        try:
            with open(kb_file, 'r') as f:
                kb = json.load(f)
        except:
            return []

        topic_lower = topic.lower()
        return [e['content'] for e in kb.get('entries', [])
                if topic_lower in e.get('content', '').lower()][:5]

    def _add_to_knowledge(self, content: str, category: str):
        """Add to persistent knowledge base."""
        kb_file = self.root / "knowledge.json"

        if kb_file.exists():
            try:
                with open(kb_file, 'r') as f:
                    kb = json.load(f)
            except:
                kb = {"entries": []}
        else:
            kb = {"entries": []}

        # Dedup
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        if any(e.get('_hash') == content_hash for e in kb.get('entries', [])):
            return

        kb['entries'].append({
            "ts": datetime.now().isoformat(),
            "category": category,
            "content": content,
            "_hash": content_hash,
            "session": self.current_session['session_id'] if self.current_session else None
        })

        with open(kb_file, 'w') as f:
            json.dump(kb, f, indent=2)


# Singleton instance
scribe = SessionScribe()

# Convenience exports
start = scribe.start
tried = scribe.tried
learned = scribe.learned
question = scribe.question
next_step = scribe.next
end = scribe.end
status = scribe.status
what_tried = scribe.what_tried
what_learned = scribe.what_learned


if __name__ == "__main__":
    # Demo
    print("Session Scribe Demo")
    print("=" * 40)

    ctx = start("boot wave debugging demo")
    print(f"Context: {ctx}")

    tried("Added timeout wrapper to fairy init", outcome="partial",
          details="Boot continues but fairies become zombies")

    learned("Template 0.0.9 uses simpler __init__ than 0.1.0", category="insight")
    learned("FairyCitizens IS the CNS backbone - can't skip it", category="root_cause")

    next_step("Compare MyOrganFairy.__init__ between templates")
    question("Why does 0.1.0 hang but 0.0.9 works?")

    print(status())

    end("Demo complete - shows how to track sessions", status="demo")
