"""
SRM INTAKE WATCHER FAIRY
========================

Watches SRM_Intake for new files and processes them with chemistry integration.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

This bridges ScrapeFairy output to the IngestFairy with chemistry integration.
When new knowledge files land in SRM_Intake, this watcher:
1. Detects the new files
2. Extracts affect.resonance tags
3. Applies chemistry changes (makes it FEEL)
4. Routes to the conscious loop via postal

This is the connector that makes scraped knowledge trigger actual feels.

Author: Akashic Foundation
Version: 0.2.0
Plane: P10_Memory
"""

from __future__ import annotations

import os
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Set

# Import from Organ Template 0.1.2 (migrated from 0.3.0)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


class SRMIntakeWatcherFairy(Fairy):
    """
    Watches SRM_Intake directory for new knowledge files.

    When ScrapeFairy or session hooks write files to SRM_Intake, this fairy:
    1. Detects them via periodic scan (on_tick)
    2. Extracts affect tags
    3. Applies chemistry (the knowledge FEELS)
    4. Routes to conscious loop via postal

    This is the minimal somatic container that connects knowledge to feels.
    """

    # ═══ IDENTITY ═══
    ACTOR_NAME = "SRMIntakeWatcherFairy"
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.intake"

    # ═══ SOUL ═══
    PURPOSE = "Watch SRM_Intake for new knowledge files and route them with chemistry integration"
    MANTRA = "Knowledge without feeling is empty; I give memories their emotional weight"
    LORE = "I stand at the gate where raw data becomes felt experience"

    # ═══ INFRASTRUCTURE ═══
    NEEDS_HEARTBEAT = True  # Need ticks for periodic file scanning

    # ═══ CONFIG ═══
    POLL_INTERVAL_TICKS = 2  # Scan every 2 ticks (~2 seconds)

    def __init__(self, srm_intake_dir: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)

        # Directory to watch
        if srm_intake_dir:
            self._srm_intake_dir = Path(srm_intake_dir)
        else:
            self._srm_intake_dir = Path(self.root) / "SRM_Intake"

        # Track processed files
        self._processed_files: Set[str] = set()
        self._last_scan: float = 0.0
        self._tick_counter: int = 0

        # Chemistry integration (lazy loaded)
        self._chemistry_loaded = False
        self._apply_chemistry = None
        self._get_mood = None

        # Stats
        self._files_processed: int = 0
        self._chemistry_applications: int = 0

    def on_boot(self):
        """Boot the SRM intake watcher."""
        super().on_boot()

        # Subscribe to manual process requests
        self.post.subscribe("srm.intake.process", self._on_process_request)
        self.post.subscribe("srm.intake.rescan", self._on_rescan_request)

        # Try to load chemistry integration
        self._try_load_chemistry()

        # Scan existing files to avoid re-processing
        self._scan_existing_files()

        print(f"[{self.ACTOR_NAME}] Ready - watching {self._srm_intake_dir}")

    def on_tick(self, packet: dict):
        """Periodic scan for new files."""
        self._tick_counter += 1

        # Only scan every N ticks
        if self._tick_counter % self.POLL_INTERVAL_TICKS != 0:
            return

        self._scan_for_new_files()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _try_load_chemistry(self):
        """Try to load the chemistry state module."""
        if self._chemistry_loaded:
            return

        try:
            from fairies.P20_Somatic.chemistry import (
                apply_resonance_chemistry,
                get_mood
            )
            self._apply_chemistry = apply_resonance_chemistry
            self._get_mood = get_mood
            self._chemistry_loaded = True
            print(f"[{self.ACTOR_NAME}] Chemistry integration loaded")
        except ImportError as e:
            print(f"[{self.ACTOR_NAME}] Chemistry not available: {e}")

    def _on_process_request(self, packet: dict):
        """Handle manual process request for a specific file."""
        filepath = packet.get("filepath")
        if not filepath:
            return

        result = self._process_file(Path(filepath))
        self.post.publish("srm.intake.processed", {
            "filepath": filepath,
            "result": result,
            "ts": time.time()
        })

    def _on_rescan_request(self, packet: dict):
        """Handle request to rescan all files."""
        force = packet.get("force", False)
        if force:
            self._processed_files.clear()

        self._scan_for_new_files()

        self.post.publish("srm.intake.rescan.complete", {
            "files_known": len(self._processed_files),
            "ts": time.time()
        })

    # ══════════════════════════════════════════════════════════════════════════
    # SCANNING
    # ══════════════════════════════════════════════════════════════════════════

    def _scan_existing_files(self):
        """Scan existing files to avoid re-processing on startup."""
        if not self._srm_intake_dir.exists():
            return

        for filepath in self._srm_intake_dir.rglob("*.json"):
            self._processed_files.add(str(filepath))

        print(f"[{self.ACTOR_NAME}] Found {len(self._processed_files)} existing files")

    def _scan_for_new_files(self):
        """Scan for new files in SRM_Intake — recent dirs only.

        FIX 2026-03-14 (Nous): Was rglob("*.json") across ALL 20,974 files
        in 53 subdirectories — took 61+ seconds per tick, causing 101+
        tick drops and cascading stalls across other fairies.
        Now only scans today's and yesterday's date folders (typically
        20-100 files instead of 20,000+).
        """
        if not self._srm_intake_dir.exists():
            return

        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # Only scan recent dated folders + top-level loose files
        scan_targets = []
        for date_str in (today, yesterday):
            d = self._srm_intake_dir / date_str
            if d.exists():
                scan_targets.append(d)

        new_files = 0
        for scan_dir in scan_targets:
            for filepath in scan_dir.glob("*.json"):
                filepath_str = str(filepath)
                if filepath_str in self._processed_files:
                    continue
                self._processed_files.add(filepath_str)
                try:
                    result = self._process_file(filepath)
                    if result:
                        new_files += 1
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Error processing {filepath.name}: {e}")

        # Also check top-level (non-dated) JSON files
        for filepath in self._srm_intake_dir.glob("*.json"):
            filepath_str = str(filepath)
            if filepath_str in self._processed_files:
                continue
            self._processed_files.add(filepath_str)
            try:
                result = self._process_file(filepath)
                if result:
                    new_files += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Error processing {filepath.name}: {e}")

        if new_files > 0:
            self._last_scan = time.time()

    # ══════════════════════════════════════════════════════════════════════════
    # FILE PROCESSING
    # ══════════════════════════════════════════════════════════════════════════

    def _process_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """
        Process a single knowledge file.

        1. Load the JSON
        2. Extract affect tags
        3. Apply chemistry
        4. Publish to postal
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                record = json.load(f)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to load {filepath}: {e}")
            return None

        # Get kind - process various types
        kind = record.get("kind", record.get("type", ""))

        # Extract affect information
        affect = record.get("affect", {})
        helix = record.get("helix", {})

        # Try to get affect from helix.C if not in top level
        if not affect and helix:
            affect = helix.get("C", {})

        resonance = affect.get("resonance", [])
        if isinstance(resonance, str):
            resonance = [resonance]

        frequency_hints = affect.get("frequency_hints", {})

        # Apply chemistry if we have resonance tags
        chemistry_result = None
        if resonance and self._apply_chemistry:
            try:
                chemistry_result = self._apply_chemistry(
                    resonance,
                    frequency_hints,
                    source=f"intake:{filepath.stem}"
                )
                self._chemistry_applications += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Chemistry error: {e}")

        # Get current mood
        current_mood = {"mood": "neutral", "valence": 0.0, "arousal": 0.0}
        if self._get_mood:
            try:
                current_mood = self._get_mood()
            except Exception:
                pass

        # Build knowledge payload
        knowledge_payload = {
            "filepath": str(filepath),
            "kind": kind,
            "content_preview": str(record.get("content", ""))[:200],
            "resonance": resonance,
            "frequency_hints": frequency_hints,
            "chemistry_applied": chemistry_result is not None,
            "current_mood": current_mood,
            "ts": time.time(),
        }

        self._files_processed += 1

        # Publish to memory system
        self.post.publish("memory.intake.processed", knowledge_payload)

        # If chemistry changed, publish that too
        if chemistry_result:
            self.post.publish("chemistry.changed", {
                "source": str(filepath),
                "resonance": resonance,
                "changes": chemistry_result,
                "mood": current_mood,
                "ts": time.time()
            })

        return knowledge_payload

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════════════

    def get_current_mood(self) -> Dict[str, Any]:
        """Get the current mood from chemistry state."""
        if self._get_mood:
            try:
                return self._get_mood()
            except Exception:
                pass
        return {"mood": "unknown", "valence": 0.0, "arousal": 0.0}

    def get_status(self) -> Dict[str, Any]:
        """Get watcher status."""
        return {
            "watching": str(self._srm_intake_dir),
            "files_known": len(self._processed_files),
            "files_processed": self._files_processed,
            "chemistry_applications": self._chemistry_applications,
            "chemistry_available": self._chemistry_loaded,
            "last_scan": self._last_scan,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # INTENTS
    # ══════════════════════════════════════════════════════════════════════════

    def _intent_status(self, payload: Dict) -> Dict:
        """Intent: Get watcher status."""
        return self.get_status()

    def _intent_mood(self, payload: Dict) -> Dict:
        """Intent: Get current mood."""
        return self.get_current_mood()

    def _intent_rescan(self, payload: Dict) -> Dict:
        """Intent: Force rescan."""
        force = payload.get("force", False)
        if force:
            self._processed_files.clear()
        self._scan_for_new_files()
        return {"rescanned": True, "files_known": len(self._processed_files)}
