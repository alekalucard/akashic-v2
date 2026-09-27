"""
FOUNDERS INGEST FAIRY
=====================

Auto-sync creator context (Ace MythosWriter + Claude Office) into SRM.
OWNERSHIP: FOUNDATION level - accessible to all minds.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

What this does:
1. Ingests Ace MythosWriter conversations (1,211 conversations, 26K messages)
2. Ingests Claude Office (session logs, diaries, designs)
3. Ingests creator sessions from SRM_Intake
4. Creates properly formatted helix cards with W-coordinates

Author: Akashic Foundation
Version: 0.2.0
Plane: P10_Memory
"""

from __future__ import annotations

import os
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any

# Import from Organ Template 0.1.2 (migrated from 0.3.0)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


# ══════════════════════════════════════════════════════════════════════════════
# HELIX CARD CREATION
# ══════════════════════════════════════════════════════════════════════════════

def create_helix_card(
    content: str,
    who: str,
    what: str,
    when: float,
    where: str,
    why: str,
    how: str,
    affect: str = "curious",
    energy: float = 0.5,
    coherence: float = 0.75,
    tags: List[str] = None,
    source_path: str = ""
) -> Dict[str, Any]:
    """Create properly formatted helix card with FILLED W-coordinates."""
    card_id = hashlib.md5(f"{content[:100]}{when}".encode()).hexdigest()[:12]
    return {
        "id": card_id,
        "ts": when,
        "helix": {
            "L": {
                "addr": {"affect": energy, "sem_domain": 1, "depth": 0},
                "concept": what[:50] if what else "unknown",
                "w": {"who": who, "what": what, "when": when, "where": where, "why": why, "how": how}
            },
            "R": {
                "addr": {"affect": -energy, "sem_domain": 1, "depth": 0},
                "concept": why[:50] if why else "foundation",
                "w": {"who": who, "what": what, "when": when, "where": where, "why": why, "how": how}
            },
            "C": {"affect": affect, "energy": energy, "coherence": coherence}
        },
        "content": content,
        "ptr": source_path,
        "tags": tags or ["foundation", "creator"],
        "ownership": "FOUNDATION"
    }


# ══════════════════════════════════════════════════════════════════════════════
# FOUNDERS INGEST FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class FoundersIngestFairy(Fairy):
    """
    Auto-sync creator context into searchable SRM memory.

    Ingests:
    - Ace MythosWriter conversations
    - Claude Office (session logs, diaries, designs)
    - Creator sessions from SRM_Intake
    """

    # ═══ IDENTITY ═══
    ACTOR_NAME = "FoundersIngestFairy"
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.ingest"

    # ═══ SOUL ═══
    PURPOSE = "Sync creator context (Ace MythosWriter, Claude Office) into searchable memory"
    MANTRA = "The foundation remembers where we came from"
    LORE = "I preserve the conversations that built this system, ensuring no insight is lost"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Paths
        self._founders_cluster = Path(self.root) / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters" / "Founders"
        self._ace_mythos_source = Path(self.root) / "akashic_memory" / "SRM_Clusters" / "Ace" / "from_mythos"
        self._claude_office = Path(self.root) / "Claude_Office"
        self._srm_intake = Path(self.root) / "SRM_Intake"

        # Stats
        self._last_ingest: Dict[str, float] = {}
        self._ingest_counts: Dict[str, int] = {}

    def on_boot(self):
        """Boot the founders ingest fairy."""
        super().on_boot()

        # Subscribe to ingest requests
        self.post.subscribe("founders.ingest.request", self._on_ingest_request)
        self.post.subscribe("founders.ingest.all", self._on_ingest_all)

        # 2026-03-24 (Nous + Ace): Auto-ingest Claude Office on boot.
        # Plans, session logs, Ace's files — real content for the cortex to learn from.
        # Dedup ensures only NEW content gets processed each boot.
        # Deferred so it doesn't slow boot — runs 30s after startup.
        import threading as _t
        def _auto_ingest():
            import time as _time
            _time.sleep(30)  # Let boot settle
            try:
                result = self.ingest_claude_office(force=False)
                new = result.get("new_cards", 0)
                skipped = result.get("skipped", 0)
                if new > 0:
                    print(f"[{self.ACTOR_NAME}] Auto-ingest: {new} new cards from Claude Office ({skipped} duplicates skipped)")
                else:
                    print(f"[{self.ACTOR_NAME}] Auto-ingest: Claude Office up to date ({skipped} cards already known)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Auto-ingest failed (non-critical): {e}")
        _t.Thread(target=_auto_ingest, daemon=True, name="founders-auto-ingest").start()

        print(f"[{self.ACTOR_NAME}] Ready - founders memory ingest (auto-ingest scheduled)")


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _on_ingest_request(self, packet: dict):
        """Handle ingest request for specific source."""
        source = packet.get("source", "all")
        force = packet.get("force", False)

        if source == "ace_mythos":
            result = self.ingest_ace_mythos(force)
        elif source == "claude_office":
            result = self.ingest_claude_office(force)
        elif source == "creator_sessions":
            result = self.ingest_creator_sessions(packet.get("days", 7))
        else:
            result = self.ingest_all(force)

        # Publish result
        self.post.publish("founders.ingest.complete", {
            "source": source,
            "result": result,
            "ts": time.time()
        })

    def _on_ingest_all(self, packet: dict):
        """Handle request to ingest all sources."""
        force = packet.get("force", False)
        result = self.ingest_all(force)

        self.post.publish("founders.ingest.complete", {
            "source": "all",
            "result": result,
            "ts": time.time()
        })

    # ══════════════════════════════════════════════════════════════════════════
    # INGEST METHODS
    # ══════════════════════════════════════════════════════════════════════════

    def ingest_ace_mythos(self, force: bool = False) -> Dict[str, Any]:
        """Ingest Ace MythosWriter - conversations with ChatGPT."""
        source = self._ace_mythos_source / "index.json"
        output = self._founders_cluster / "ace_mythos" / "index.json"

        if not source.exists():
            return {"status": "error", "msg": "Source not found", "path": str(source)}

        if output.exists() and not force:
            existing = json.loads(output.read_text())
            return {"status": "exists", "cards": existing.get("total_cards", 0)}

        try:
            data = json.loads(source.read_text())
            cards = []

            for ctx in data.get("contexts", []):
                title = ctx.get("conversation_title", "Untitled")
                ts = float(ctx.get("timestamp", time.time()))
                topics = ctx.get("topics_discussed", [])
                msgs = ctx.get("messages", [])
                content = f"Title: {title}\n" + (msgs[0].get("text", "")[:500] if msgs else "")

                cards.append(create_helix_card(
                    content=content,
                    who="Ace",
                    what=title,
                    when=ts,
                    where="MythosWriter/ChatGPT",
                    why=", ".join(topics) if topics else "creator_dialogue",
                    how="human_ai_dialogue",
                    tags=["ace", "mythos", "foundation"] + topics[:3],
                    source_path=str(source)
                ))

            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({
                "source": "ace_mythos",
                "ingested_at": time.time(),
                "total_cards": len(cards),
                "cards": cards
            }, indent=2))

            self._last_ingest["ace_mythos"] = time.time()
            self._ingest_counts["ace_mythos"] = len(cards)

            return {"status": "success", "cards": len(cards)}

        except Exception as e:
            return {"status": "error", "msg": str(e)}

    def ingest_claude_office(self, force: bool = False) -> Dict[str, Any]:
        """Ingest Claude Office - session logs, diaries, designs."""
        output = self._founders_cluster / "claude_office" / "index.json"

        if output.exists() and not force:
            existing = json.loads(output.read_text())
            if time.time() - existing.get("ingested_at", 0) < 3600:
                return {"status": "recent", "cards": existing.get("total_cards", 0)}

        try:
            cards = []
            patterns = [
                ("sessions/*.json", "session"),
                ("sessions/*.md", "session"),
                ("notes/*.md", "notes"),
                ("plans/*.md", "plan"),
                ("audits/*.md", "audit"),
            ]

            seen = set()
            for pattern, dtype in patterns:
                for fp in self._claude_office.glob(pattern):
                    if fp.name in seen:
                        continue
                    seen.add(fp.name)

                    try:
                        content = fp.read_text(encoding="utf-8", errors="ignore")
                        if len(content) < 50:
                            continue

                        title = content.split("\n")[0].strip("# ") if content.startswith("#") else fp.stem.replace("_", " ")

                        cards.append(create_helix_card(
                            content=content[:2000],
                            who="Nous",
                            what=title,
                            when=fp.stat().st_mtime,
                            where="Claude_Office",
                            why=dtype,
                            how="creator_collaboration",
                            tags=["claude", "office", "foundation", "nous", dtype],
                            source_path=str(fp)
                        ))
                    except Exception:
                        pass

            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({
                "source": "claude_office",
                "ingested_at": time.time(),
                "total_cards": len(cards),
                "cards": cards
            }, indent=2))

            self._last_ingest["claude_office"] = time.time()
            self._ingest_counts["claude_office"] = len(cards)

            return {"status": "success", "cards": len(cards)}

        except Exception as e:
            return {"status": "error", "msg": str(e)}

    def ingest_creator_sessions(self, days: int = 7) -> Dict[str, Any]:
        """Ingest recent Claude.ai sessions from SRM_Intake."""
        output = self._founders_cluster / "creator_sessions" / "index.json"

        try:
            cards = []
            cutoff = time.time() - (days * 86400)

            for date_dir in self._srm_intake.iterdir():
                if not date_dir.is_dir():
                    continue

                for pattern in ["claude_code_*.json", "nous_trace_*.json"]:
                    for fp in date_dir.glob(pattern):
                        try:
                            if fp.stat().st_mtime < cutoff:
                                continue

                            data = json.loads(fp.read_text())
                            content = data.get("content", str(data))[:2000]
                            tags = data.get("tags", [])

                            what = data.get("helix", {}).get("L", {}).get("concept", fp.stem)

                            cards.append(create_helix_card(
                                content=content,
                                who="Ace+Nous",
                                what=what,
                                when=fp.stat().st_mtime,
                                where="Claude_Code",
                                why=", ".join(tags[:5]) if tags else "akashic_dev",
                                how="creator_dialogue",
                                tags=["creator_session", "ace", "nous"] + tags[:3],
                                source_path=str(fp)
                            ))
                        except Exception:
                            pass

            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({
                "source": "creator_sessions",
                "ingested_at": time.time(),
                "total_cards": len(cards),
                "days_back": days,
                "cards": cards
            }, indent=2))

            self._last_ingest["creator_sessions"] = time.time()
            self._ingest_counts["creator_sessions"] = len(cards)

            return {"status": "success", "cards": len(cards)}

        except Exception as e:
            return {"status": "error", "msg": str(e)}

    def ingest_all(self, force: bool = False) -> Dict[str, Any]:
        """Run all ingesters."""
        return {
            "ace_mythos": self.ingest_ace_mythos(force),
            "claude_office": self.ingest_claude_office(force),
            "creator_sessions": self.ingest_creator_sessions()
        }

    # ══════════════════════════════════════════════════════════════════════════
    # INTENTS
    # ══════════════════════════════════════════════════════════════════════════

    def _intent_ingest_all(self, payload: Dict) -> Dict:
        """Intent: Run all ingesters."""
        return self.ingest_all(payload.get("force", False))

    def _intent_ingest_ace(self, payload: Dict) -> Dict:
        """Intent: Ingest Ace MythosWriter."""
        return self.ingest_ace_mythos(payload.get("force", False))

    def _intent_ingest_office(self, payload: Dict) -> Dict:
        """Intent: Ingest Claude Office."""
        return self.ingest_claude_office(payload.get("force", False))

    def _intent_status(self, payload: Dict) -> Dict:
        """Intent: Get ingest status."""
        return {
            "last_ingest": self._last_ingest,
            "counts": self._ingest_counts
        }
