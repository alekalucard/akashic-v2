"""DirectiveEvolver — Layer 3 runtime primitive (Slice 2a, 2026-04-22).

Lives in the organ template. Every fairy with a NEW-format directive (one
that has a [Substrate_Contract] section, typically those seeded by
DirectiveSeedLibrary) gets an instance auto-wired in Organ_Template.__init__.

Responsibilities:
  - Track per-topic iterations + action_ratio in memory (Clawbots primitive)
  - Append-only writes to [Evolution_Log] with standardized header (Grok polish)
  - Enforce [Substrate_Contract].Self_Overwrite — refuses writes to protected
    sections ([Core], [Substrate_Contract], [Action_Bias]) and surfaces a
    `directive.violation` meta-event to Sour (Ziggy refinement)
  - Publishes `fairy.directive.evolved` on successful Evolution_Log append

Out of scope for Slice 2a (deferred):
  - Sour-mediated approval via `request_directive_refinement` tool (Slice 2c)
  - Cortex-spread injection into [Associative_Neighborhood] (Slice 2f)
  - Preferred-tool writebacks (Slice 2g)

Coexists with the older `evolve_directive()` method on Organ_Template, which
handles OLD-format directives (sections like KNOWLEDGE_FOUNDATION). The two
systems do not conflict — DirectiveEvolver only activates when the directive
has a [Substrate_Contract] section.

Plan: Claude_Office/plans/DIRECTIVE_SEEDING_AND_SELF_EVOLUTION.md
"""

from __future__ import annotations
import os
import re
import time
from datetime import datetime
from typing import Dict, Optional


# Sections that are constitutionally protected. Mirrors the seeded starter's
# [Substrate_Contract].Self_Overwrite field — kept as a hard fallback in case
# the directive's Self_Overwrite line is malformed or missing.
_PROTECTED_SECTIONS = {"Core", "Substrate_Contract", "Action_Bias"}

# Default-writable sections (used only if Self_Overwrite parsing fails).
_DEFAULT_WRITABLE = {"Tools", "Associative_Neighborhood", "Evolution_Log"}


class DirectiveEvolver:
    """In-process directive-evolution primitive. One per fairy."""

    def __init__(self, fairy):
        self.fairy = fairy
        # topic_hash -> {iterations, actions_taken, last_thought, first_seen}
        self._topic_cycles: Dict[str, dict] = {}
        self._total_cycles = 0
        self._total_actions = 0
        self._last_log_time = 0.0
        self._log_cooldown_sec = 60.0  # min gap between Evolution_Log appends

    # ── Enablement check ──────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        """Only active for NEW-format directives (those with [Substrate_Contract])."""
        d = getattr(self.fairy, '_directive', {}) or {}
        if not d.get("loaded"):
            return False
        return "Substrate_Contract" in (d.get("sections") or {})

    # ── Cycle tracking (Clawbots primitive) ──────────────────────────

    def observe_cycle(self, topic_hash: str, action_taken: bool,
                      last_thought: str = "") -> None:
        """Record one reasoning cycle. Fairies call this each tick.

        Args:
            topic_hash: a stable string ID for the topic being reasoned about.
                Empty string is tolerated but skipped (no tracking).
            action_taken: did this cycle produce an action signal?
            last_thought: optional — the thought that closed this cycle.
        """
        if not topic_hash:
            return
        self._total_cycles += 1
        if action_taken:
            self._total_actions += 1
        t = self._topic_cycles.setdefault(topic_hash, {
            "iterations": 0,
            "actions_taken": 0,
            "last_thought": "",
            "first_seen": time.time(),
        })
        t["iterations"] += 1
        if action_taken:
            t["actions_taken"] += 1
        if last_thought:
            t["last_thought"] = last_thought[:300]

    def iterations_for(self, topic_hash: str) -> int:
        return self._topic_cycles.get(topic_hash, {}).get("iterations", 0)

    def action_ratio_for(self, topic_hash: str) -> str:
        t = self._topic_cycles.get(topic_hash, {})
        n = t.get("iterations", 0)
        a = t.get("actions_taken", 0)
        return f"{a}/{n}" if n else "0/0"

    def overall_action_ratio(self) -> float:
        if self._total_cycles == 0:
            return 0.0
        return self._total_actions / self._total_cycles

    def reset_topic(self, topic_hash: str) -> None:
        """Clear tracking for a topic (call after forced_escape resolves)."""
        self._topic_cycles.pop(topic_hash, None)

    # ── Substrate_Contract enforcement ───────────────────────────────

    def _writable_sections(self) -> set:
        """Parse Substrate_Contract.Self_Overwrite to find writable sections.

        Expected format (from DirectiveSeedLibrary):
          Self_Overwrite: only [Tools], [Associative_Neighborhood], and
              [Evolution_Log] may be modified by DirectiveEvolver. ...
        Falls back to _DEFAULT_WRITABLE if parse fails.
        """
        try:
            parsed = self.fairy._parse_directive_section("Substrate_Contract")
            so = parsed.get("self_overwrite", "") or ""
            found = set(re.findall(r'\[(\w+)\]', so))
            if not found:
                return set(_DEFAULT_WRITABLE)
            return found
        except Exception:
            return set(_DEFAULT_WRITABLE)

    def _can_write(self, section_name: str) -> bool:
        if section_name in _PROTECTED_SECTIONS:
            return False
        return section_name in self._writable_sections()

    def _surface_violation(self, section: str, reason: str) -> None:
        """Log the attempt and publish `directive.violation` meta-event."""
        fname = getattr(self.fairy, 'ACTOR_NAME', '?')
        print(f"[{fname}] SubstrateContractViolation: [{section}] — {reason}",
              flush=True)
        post = getattr(self.fairy, 'post', None)
        if post:
            try:
                post.publish("directive.violation", {
                    "fairy": fname,
                    "section": section,
                    "reason": reason,
                    "timestamp": time.time(),
                })
            except Exception:
                pass

    # ── Evolution_Log append (append-only, header-standardized) ───────

    def append_evolution_log(self, topic_hash: str,
                             observation: str = "",
                             learned: str = "",
                             suggested: str = "") -> bool:
        """Append a standardized entry to [Evolution_Log].

        Header format (Grok polish):
          YYYY-MM-DD_HH:MM | fairy: NAME | topic_hash: HASH
                           | cycles: N | action_ratio: A/N

        Returns True on success, False if throttled, disabled, or blocked by
        Substrate_Contract.
        """
        if not self.enabled:
            return False
        if not self._can_write("Evolution_Log"):
            self._surface_violation("Evolution_Log",
                                    "not in Substrate_Contract.Self_Overwrite allowlist")
            return False

        now = time.time()
        if now - self._last_log_time < self._log_cooldown_sec:
            return False

        fname = getattr(self.fairy, 'ACTOR_NAME', '?')
        t = self._topic_cycles.get(topic_hash, {})
        cycles = t.get("iterations", 0)
        actions = t.get("actions_taken", 0)
        ratio = f"{actions}/{cycles}" if cycles else "0/0"
        header = (f"{datetime.now().strftime('%Y-%m-%d_%H:%M')} | "
                  f"fairy: {fname} | topic_hash: {topic_hash} | "
                  f"cycles: {cycles} | action_ratio: {ratio}")

        lines = [f"> {header}"]
        if observation:
            lines.append(f"  Observation: {observation[:240]}")
        if learned:
            lines.append(f"  Learned: {learned[:240]}")
        if suggested:
            lines.append(f"  Suggested: {suggested[:240]}")
        entry = "\n".join(lines)

        ok = self._append_to_section("Evolution_Log", entry)
        if ok:
            self._last_log_time = now
            post = getattr(self.fairy, 'post', None)
            if post:
                try:
                    post.publish("fairy.directive.evolved", {
                        "fairy": fname,
                        "section": "Evolution_Log",
                        "topic_hash": topic_hash,
                        "cycles": cycles,
                        "action_ratio": ratio,
                        "source": "directive_evolver",
                    })
                except Exception:
                    pass
        return ok

    # ── Safe section append (does not touch other sections) ──────────

    def _append_to_section(self, section_name: str, content: str) -> bool:
        """Insert content at the end of a specific [Section], before the next
        [Section] header (or at EOF). Never touches other sections.

        IMPORTANT: section headers are matched as line-start tokens only, so
        that a bracketed reference inside prose (e.g. the `[Evolution_Log]`
        mention inside [Substrate_Contract].Self_Overwrite) is not mistaken
        for the actual section header.
        """
        path = getattr(self.fairy, '_directive_path', None)
        if not path or not os.path.exists(path):
            return False
        fname = getattr(self.fairy, 'ACTOR_NAME', '?')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()

            # Match the target section header as a line-start (possibly at BOF).
            header_re = re.compile(r'(?:^|\n)\[' + re.escape(section_name) + r'\][^\n]*\n',
                                   re.MULTILINE)
            header_m = header_re.search(text)
            if not header_m:
                return False  # section absent — refuse to create from here

            section_end = header_m.end()  # just after the header line's newline

            # Find start of next section header (also line-anchored).
            next_header = re.compile(r'\n\[\w[^\]]*\][^\n]*\n', re.MULTILINE)
            m = next_header.search(text, section_end)
            insert_pos = m.start() if m else len(text)

            head = text[:insert_pos].rstrip()
            tail = text[insert_pos:]
            new_text = head + "\n" + content + "\n" + tail

            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_text)

            # Update in-memory sections so subsequent reads see the change
            try:
                sections = self.fairy._directive.setdefault("sections", {})
                existing = sections.get(section_name, "")
                sections[section_name] = (existing + "\n" + content).strip()
            except Exception:
                pass

            return True
        except Exception as e:
            print(f"[{fname}] DirectiveEvolver append failed: {e}", flush=True)
            return False

    # ── Introspection (useful for debugging / Sour queries) ──────────

    def summary(self) -> dict:
        return {
            "fairy": getattr(self.fairy, 'ACTOR_NAME', '?'),
            "enabled": self.enabled,
            "topics_tracked": len(self._topic_cycles),
            "total_cycles": self._total_cycles,
            "total_actions": self._total_actions,
            "overall_action_ratio": round(self.overall_action_ratio(), 3),
            "writable_sections": sorted(self._writable_sections()) if self.enabled else [],
        }


__all__ = ["DirectiveEvolver"]
