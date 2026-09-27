"""
MemoryConsolidatorFairy - Automated Memory Organization System

Purpose: Consolidate scattered memories into the Triple Helix storage,
         process diary telemetry into relational clusters, and build
         indices for efficient long-term recall.

The Problem This Solves:
- SRM_Intake cards scattered across multiple locations
- Diary JSONL files growing unbounded without pattern extraction
- No long-term searchable memory (only recent days accessible)
- Per-fairy relational patterns never extracted

The Solution:
1. INTAKE CONSOLIDATION: Move old cards (>7 days) to Triple Helix by category
2. DIARY PROCESSING: Extract patterns from JSONL into per-fairy clusters
3. INDEX BUILDING: Create search indices for fast historical recall
4. MULTI-WORKER SUPPORT: Each fairy's workers get their own cluster sections

Plane: P10 (Memory)
Channel: memory
Mantra: "From chaos, coherence. From fragments, wholeness."
"""

from __future__ import annotations

import os
import sys
import json
import glob
import time
import uuid
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set
from collections import defaultdict
from dataclasses import dataclass, field

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class ConsolidationConfig:
    """Configuration for memory consolidation."""

    # Source locations to scan
    srm_intake_locations: List[str] = field(default_factory=list)
    diary_locations: List[str] = field(default_factory=list)

    # Destination (Triple Helix storage)
    triple_helix_root: str = ""

    # Age threshold for consolidation (days) - different by source type
    consolidate_after_days: int = 7  # Default for most content

    # Source-specific consolidation rules
    # Scraper content goes to long-term immediately (0 days)
    # Claude/Sour need time in working/short-term first
    source_rules: Dict[str, Dict] = field(default_factory=lambda: {
        # System knowledge - immediate to long-term
        "system.knowledge": {
            "min_age_days": 0,  # Immediate
            "category": "knowledge",
            "tier": "longterm",
        },
        # Claude fairy experiences - need time to settle
        "claudefairy": {
            "min_age_days": 1,  # 24 hours in working/short-term
            "category": "experience",
            "tier": "shortterm",  # Then consolidator moves to longterm after days
        },
        # Sourpatches fairy - same as Claude
        "sourpatches": {
            "min_age_days": 1,
            "category": "experience",
            "tier": "shortterm",
        },
        # Collision insights - valuable, move faster
        "collision": {
            "min_age_days": 0.5,  # 12 hours
            "category": "experience",
            "tier": "shortterm",
        },
        # Practice/learning - standard timing
        "practice": {
            "min_age_days": 1,
            "category": "experience",
            "tier": "shortterm",
        },
        # Evolution telemetry - can aggregate quickly
        "evolution": {
            "min_age_days": 0,
            "category": "telemetry",
            "tier": "longterm",
        },
    })

    # Category routing rules (kind prefix -> category) - fallback for unmatched
    category_routes: Dict[str, str] = field(default_factory=lambda: {
        "system.knowledge": "knowledge",
        "claudefairy": "experience",
        "sourpatches": "experience",
        "recall": "experience",
        "collision": "experience",
        "practice": "experience",
        "failure": "experience",
        "evolution": "telemetry",
        "blueprint": "telemetry",
        "health": "telemetry",
        "sanity": "telemetry",
    })

    # Default category for unmatched kinds
    default_category: str = "archive"

    # Short-term to long-term consolidation threshold
    shortterm_to_longterm_days: int = 3  # Move from short-term to long-term after 3 days

    # Index settings
    build_indices: bool = True
    index_sample_size: int = 100  # Sample per category for lightweight index

    # Diary processing
    process_diaries: bool = True
    diary_pattern_threshold: int = 5  # Min occurrences to be a "pattern"
    cleanup_processed_diaries: bool = True  # Delete diary files after extracting patterns
    diary_retention_days: int = 7  # Keep diaries for this long before cleanup

    # Safety
    dry_run: bool = False  # If True, don't actually move/delete
    verify_before_delete: bool = True


# ============================================================================
# Triple Helix Storage Structure
# ============================================================================

class TripleHelixStorage:
    """
    Manages the tiered memory storage structure.

    Memory Tiers (like human memory):
    - WORKING: Active context (in-memory during session)
    - SHORT-TERM: Recent experiences (hours to days)
    - LONG-TERM: Consolidated knowledge (permanent)

    Structure:
    triple_helix_root/
    ├── working/             # Active context (cleared on session end)
    │   └── {date}/
    ├── shortterm/           # Recent memories (hours to days)
    │   └── {date}/
    ├── longterm/            # Permanent consolidated storage
    │   ├── knowledge/       # Scraped content, system knowledge
    │   │   └── {year-month}/
    │   ├── experience/      # ClaudeFairy insights, collisions
    │   │   └── {year-month}/
    │   ├── telemetry/       # Evolution, health, blueprints
    │   │   └── {year-month}/
    │   └── archive/         # Catch-all for unmatched
    │       └── {year-month}/
    ├── relational_clusters/ # Per-fairy pattern extraction
    │   └── {FairyName}/
    │       ├── patterns.json
    │       └── workers/
    │           └── {WorkerName}/
    └── index/
        ├── manifest.json
        ├── knowledge_index.json
        ├── experience_index.json
        └── ...
    """

    # Memory tiers
    TIERS = ["working", "shortterm", "longterm"]

    # Categories within long-term storage
    CATEGORIES = ["knowledge", "experience", "telemetry", "archive"]

    def __init__(self, root: str):
        self.root = Path(root)
        self._ensure_structure()

    def _ensure_structure(self):
        """Create the directory structure if it doesn't exist."""
        # Create tier directories
        (self.root / "working").mkdir(parents=True, exist_ok=True)
        (self.root / "shortterm").mkdir(parents=True, exist_ok=True)

        # Create long-term category directories
        for category in self.CATEGORIES:
            (self.root / "longterm" / category).mkdir(parents=True, exist_ok=True)

        (self.root / "relational_clusters").mkdir(parents=True, exist_ok=True)
        (self.root / "index").mkdir(parents=True, exist_ok=True)

    def get_tier_path(self, tier: str, date_str: str = None) -> Path:
        """Get path for a memory tier (working/shortterm)."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        path = self.root / tier / date_str
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_category_path(self, category: str, year_month: str = None) -> Path:
        """Get path for a long-term category with year-month subdirectory."""
        if year_month is None:
            year_month = datetime.now().strftime("%Y-%m")
        path = self.root / "longterm" / category / year_month
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_fairy_cluster_path(self, fairy_name: str, worker_name: str = None) -> Path:
        """Get path for a fairy's relational cluster."""
        base = self.root / "relational_clusters" / fairy_name
        if worker_name:
            path = base / "workers" / worker_name
        else:
            path = base
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_index_path(self) -> Path:
        """Get path to index directory."""
        return self.root / "index"

    def store_card(self, card: dict, category: str, tier: str = "longterm",
                   original_path: str = None) -> str:
        """
        Store a memory card in the appropriate tier and category.

        Args:
            card: The memory card dict
            category: Category for long-term (knowledge, experience, etc.)
            tier: Memory tier (working, shortterm, longterm)
            original_path: Original file path for provenance

        Returns the new path.
        """
        # Determine date from card timestamp or file
        ts = card.get("ts")
        if ts:
            dt = datetime.fromtimestamp(ts)
        elif original_path:
            # Try to extract date from original path (e.g., 2025-12-26/file.json)
            parts = Path(original_path).parts
            for part in parts:
                if len(part) == 10 and part[4] == '-' and part[7] == '-':
                    try:
                        dt = datetime.strptime(part, "%Y-%m-%d")
                        break
                    except ValueError:
                        pass
            else:
                dt = datetime.now()
        else:
            dt = datetime.now()

        # Get destination based on tier
        if tier == "longterm":
            year_month = dt.strftime("%Y-%m")
            dest_dir = self.get_category_path(category, year_month)
        else:
            # Working or shortterm - use date subdirectory
            date_str = dt.strftime("%Y-%m-%d")
            dest_dir = self.get_tier_path(tier, date_str)

        # Generate filename
        kind = card.get("kind", "unknown").replace(".", "-")
        card_id = uuid.uuid4().hex[:8]
        filename = f"{kind}-{card_id}.json"
        dest_path = dest_dir / filename

        # Add provenance metadata
        card["_consolidated"] = {
            "original_path": original_path,
            "consolidated_at": datetime.now().isoformat(),
            "category": category,
            "tier": tier,
        }

        # Write
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(card, f, indent=2, ensure_ascii=False)

        return str(dest_path)


# ============================================================================
# Diary Processor - Extract Patterns from JSONL
# ============================================================================

class DiaryProcessor:
    """
    Processes fairy diary JSONL files into relational clusters.

    Responsibilities:
    1. Extract patterns from diary JSONL (what does each fairy do?)
    2. Deduplicate telemetry (remove redundant entries)
    3. Forward unique/meaningful entries to memory
    4. Cleanup processed diary files after retention period

    Extracts:
    - Event frequency patterns (what does this fairy do most?)
    - Temporal patterns (when is it active?)
    - Relational patterns (what other fairies does it interact with?)
    - Affect patterns (emotional signatures)
    """

    def __init__(self, storage: TripleHelixStorage, config: ConsolidationConfig):
        self.storage = storage
        self.config = config
        self._seen_signatures: Set[str] = set()  # For deduplication
        self.stats = {
            "total_events": 0,
            "unique_events": 0,
            "duplicate_events": 0,
            "forwarded_to_memory": 0,
            "files_cleaned": 0,
        }

    def process_fairy_diaries(self, fairy_name: str, diary_dir: Path) -> Dict[str, Any]:
        """
        Process all diary files for a fairy into a relational cluster.

        Returns the extracted patterns.
        """
        patterns = {
            "fairy_name": fairy_name,
            "processed_at": datetime.now().isoformat(),
            "total_events": 0,
            "date_range": {"first": None, "last": None},
            "event_frequency": defaultdict(int),  # kind -> count
            "hourly_activity": defaultdict(int),  # hour -> count
            "daily_activity": defaultdict(int),   # weekday -> count
            "interactions": defaultdict(int),     # other_fairy -> count
            "affect_signatures": [],              # Sample of affect data
            "dominant_opcodes": defaultdict(int), # opcode -> count
            "worker_patterns": {},                # worker_name -> sub-patterns
        }

        # Process each JSONL file
        for jsonl_file in sorted(diary_dir.glob("*.jsonl")):
            self._process_jsonl_file(jsonl_file, patterns)

        # Convert defaultdicts to regular dicts
        patterns["event_frequency"] = dict(patterns["event_frequency"])
        patterns["hourly_activity"] = dict(patterns["hourly_activity"])
        patterns["daily_activity"] = dict(patterns["daily_activity"])
        patterns["interactions"] = dict(patterns["interactions"])
        patterns["dominant_opcodes"] = dict(patterns["dominant_opcodes"])

        # Filter to significant patterns
        threshold = self.config.diary_pattern_threshold
        patterns["event_frequency"] = {
            k: v for k, v in patterns["event_frequency"].items()
            if v >= threshold
        }
        patterns["dominant_opcodes"] = {
            k: v for k, v in patterns["dominant_opcodes"].items()
            if v >= threshold
        }

        # Sort by frequency
        patterns["event_frequency"] = dict(
            sorted(patterns["event_frequency"].items(), key=lambda x: -x[1])[:50]
        )
        patterns["dominant_opcodes"] = dict(
            sorted(patterns["dominant_opcodes"].items(), key=lambda x: -x[1])[:30]
        )

        # Limit affect signatures to sample
        patterns["affect_signatures"] = patterns["affect_signatures"][:20]

        return patterns

    def _process_jsonl_file(self, jsonl_path: Path, patterns: Dict):
        """Process a single JSONL file and update patterns."""
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        self._extract_event_patterns(event, patterns)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"  Warning: Error processing {jsonl_path}: {e}")

    def _extract_event_patterns(self, event: Dict, patterns: Dict):
        """Extract patterns from a single event."""
        patterns["total_events"] += 1

        # Timestamp patterns
        ts_str = event.get("ts")
        if ts_str:
            try:
                if isinstance(ts_str, (int, float)):
                    dt = datetime.fromtimestamp(ts_str)
                else:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

                # Update date range
                date_str = dt.strftime("%Y-%m-%d")
                if patterns["date_range"]["first"] is None or date_str < patterns["date_range"]["first"]:
                    patterns["date_range"]["first"] = date_str
                if patterns["date_range"]["last"] is None or date_str > patterns["date_range"]["last"]:
                    patterns["date_range"]["last"] = date_str

                # Hourly/daily activity
                patterns["hourly_activity"][dt.hour] += 1
                patterns["daily_activity"][dt.strftime("%A")] += 1
            except Exception:
                pass

        # Event kind frequency
        kind = event.get("kind", "unknown")
        patterns["event_frequency"][kind] += 1

        # Opcode frequency (from payload)
        payload = event.get("payload", {})
        if isinstance(payload, dict):
            opcode = payload.get("opcode")
            if opcode:
                patterns["dominant_opcodes"][opcode] += 1

            # Interaction tracking
            source = payload.get("source_actor") or payload.get("from") or payload.get("source")
            if source and source != patterns["fairy_name"]:
                patterns["interactions"][source] += 1

            target = payload.get("target_actor") or payload.get("to") or payload.get("target")
            if target and target != patterns["fairy_name"]:
                patterns["interactions"][target] += 1

        # Affect signatures (sample)
        affect = event.get("affect") or (payload.get("affect") if isinstance(payload, dict) else None)
        if affect and len(patterns["affect_signatures"]) < 50:
            patterns["affect_signatures"].append({
                "affect": affect,
                "kind": kind,
                "ts": ts_str,
            })

        # Worker patterns (if present)
        worker = event.get("worker") or (payload.get("worker") if isinstance(payload, dict) else None)
        if worker:
            if worker not in patterns["worker_patterns"]:
                patterns["worker_patterns"][worker] = {
                    "event_count": 0,
                    "kinds": defaultdict(int),
                }
            patterns["worker_patterns"][worker]["event_count"] += 1
            patterns["worker_patterns"][worker]["kinds"][kind] += 1

    def save_patterns(self, fairy_name: str, patterns: Dict, worker_name: str = None):
        """Save extracted patterns to the relational cluster."""
        cluster_path = self.storage.get_fairy_cluster_path(fairy_name, worker_name)

        # Convert any remaining defaultdicts
        for key in ["worker_patterns"]:
            if key in patterns and patterns[key]:
                for wname, wdata in patterns[key].items():
                    if "kinds" in wdata and isinstance(wdata["kinds"], defaultdict):
                        wdata["kinds"] = dict(wdata["kinds"])

        patterns_file = cluster_path / "patterns.json"
        with open(patterns_file, "w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2, ensure_ascii=False)

        return str(patterns_file)

    def _compute_event_signature(self, event: Dict) -> str:
        """
        Compute a signature for deduplication.

        Events with the same kind, opcode, and key payload fields
        within a short time window are considered duplicates.
        """
        kind = event.get("kind", "")
        payload = event.get("payload", {})
        if isinstance(payload, dict):
            opcode = payload.get("opcode", "")
            # Include key identifying fields but not timestamps
            sig_parts = [kind, opcode]
            for key in ("source_actor", "target_actor", "from", "to", "fairy"):
                if key in payload:
                    sig_parts.append(str(payload[key]))
        else:
            opcode = ""
            sig_parts = [kind, str(payload)[:100]]

        # Hash for compact storage
        sig_str = "|".join(sig_parts)
        return hashlib.md5(sig_str.encode()).hexdigest()[:12]

    def deduplicate_and_forward(self, fairy_name: str, diary_dir: Path) -> Dict[str, Any]:
        """
        Scan diary files, deduplicate, and forward unique meaningful events to memory.

        Returns stats about deduplication.
        """
        unique_events = []
        duplicate_count = 0

        for jsonl_file in sorted(diary_dir.glob("*.jsonl")):
            try:
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            sig = self._compute_event_signature(event)

                            self.stats["total_events"] += 1

                            if sig in self._seen_signatures:
                                duplicate_count += 1
                                self.stats["duplicate_events"] += 1
                            else:
                                self._seen_signatures.add(sig)
                                self.stats["unique_events"] += 1

                                # Only forward meaningful events (not just health pings)
                                if self._is_meaningful_event(event):
                                    unique_events.append({
                                        "fairy": fairy_name,
                                        "event": event,
                                        "signature": sig,
                                    })
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"  Warning: Error reading {jsonl_file}: {e}")

        # Forward unique events to memory (as short-term experience)
        forwarded = 0
        for item in unique_events[:100]:  # Limit to avoid overwhelming
            try:
                card = {
                    "kind": f"diary.{fairy_name.lower()}",
                    "data": item["event"],
                    "meta": {
                        "fairy": item["fairy"],
                        "signature": item["signature"],
                        "source": "diary_dedup",
                    },
                    "ts": time.time(),
                }
                self.storage.store_card(
                    card,
                    category="experience",
                    tier="shortterm",
                    original_path=str(diary_dir),
                )
                forwarded += 1
                self.stats["forwarded_to_memory"] += 1
            except Exception:
                pass

        return {
            "fairy": fairy_name,
            "total": self.stats["total_events"],
            "unique": len(unique_events),
            "duplicates": duplicate_count,
            "forwarded": forwarded,
        }

    def _is_meaningful_event(self, event: Dict) -> bool:
        """Filter out noise - only forward meaningful events."""
        kind = event.get("kind", "")
        payload = event.get("payload", {})

        # Skip pure health/smoke pings
        if isinstance(payload, dict):
            opcode = payload.get("opcode", "")
            if opcode in ("SMOKE", "HEALTH_CHECK", "PING", "HEARTBEAT"):
                return False

        # Skip evolution simulation ticks (noise)
        if "evolution.sim" in kind:
            return False

        # Skip registration heartbeats
        if "registration" in kind.lower():
            return False

        # Keep everything else
        return True

    def cleanup_old_diaries(self, diary_dir: Path) -> int:
        """
        Remove diary files older than retention period.

        Diaries are backup - once processed into memory, they're redundant.
        We keep them for a retention period for debugging, then clean up.

        Returns count of files removed.
        """
        if not self.config.cleanup_processed_diaries:
            return 0

        cutoff = datetime.now() - timedelta(days=self.config.diary_retention_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        removed = 0
        for jsonl_file in diary_dir.glob("*.jsonl"):
            # Parse date from filename (format: YYYY-MM-DD.jsonl)
            date_part = jsonl_file.stem
            if len(date_part) == 10 and date_part[4] == '-' and date_part[7] == '-':
                if date_part < cutoff_str:
                    try:
                        if not self.config.dry_run:
                            jsonl_file.unlink()
                        removed += 1
                        self.stats["files_cleaned"] += 1
                    except Exception:
                        pass

        return removed


# ============================================================================
# Index Builder - Create Search Indices
# ============================================================================

class IndexBuilder:
    """
    Builds lightweight search indices for long-term memory recall.

    Creates:
    - manifest.json: Overview of all indexed content
    - {category}_index.json: Per-category indices with samples
    """

    def __init__(self, storage: TripleHelixStorage, config: ConsolidationConfig):
        self.storage = storage
        self.config = config

    def build_indices(self) -> Dict[str, Any]:
        """Build all indices and return manifest."""
        manifest = {
            "built_at": datetime.now().isoformat(),
            "categories": {},
            "total_cards": 0,
            "total_size_bytes": 0,
            "fairy_clusters": [],
        }

        # Index each category in longterm storage
        for category in TripleHelixStorage.CATEGORIES:
            category_path = self.storage.root / "longterm" / category
            if category_path.exists():
                index = self._build_category_index(category, category_path)
                manifest["categories"][category] = {
                    "card_count": index["card_count"],
                    "size_bytes": index["size_bytes"],
                    "date_range": index["date_range"],
                    "top_kinds": list(index["kind_frequency"].keys())[:10],
                }
                manifest["total_cards"] += index["card_count"]
                manifest["total_size_bytes"] += index["size_bytes"]

                # Save category index
                index_file = self.storage.get_index_path() / f"{category}_index.json"
                with open(index_file, "w", encoding="utf-8") as f:
                    json.dump(index, f, indent=2, ensure_ascii=False)

        # Index fairy clusters
        clusters_path = self.storage.root / "relational_clusters"
        if clusters_path.exists():
            for fairy_dir in clusters_path.iterdir():
                if fairy_dir.is_dir():
                    patterns_file = fairy_dir / "patterns.json"
                    if patterns_file.exists():
                        manifest["fairy_clusters"].append(fairy_dir.name)

        # Save manifest
        manifest_file = self.storage.get_index_path() / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        return manifest

    def _build_category_index(self, category: str, category_path: Path) -> Dict[str, Any]:
        """Build index for a single category."""
        index = {
            "category": category,
            "indexed_at": datetime.now().isoformat(),
            "card_count": 0,
            "size_bytes": 0,
            "date_range": {"first": None, "last": None},
            "kind_frequency": defaultdict(int),
            "domain_frequency": defaultdict(int),
            "samples": [],  # Representative samples for quick preview
        }

        # Walk all year-month subdirectories
        for year_month_dir in sorted(category_path.iterdir()):
            if not year_month_dir.is_dir():
                continue

            # Update date range
            ym = year_month_dir.name
            if index["date_range"]["first"] is None or ym < index["date_range"]["first"]:
                index["date_range"]["first"] = ym
            if index["date_range"]["last"] is None or ym > index["date_range"]["last"]:
                index["date_range"]["last"] = ym

            # Process cards
            for card_file in year_month_dir.glob("*.json"):
                try:
                    stat = card_file.stat()
                    index["card_count"] += 1
                    index["size_bytes"] += stat.st_size

                    # Sample cards for index
                    if len(index["samples"]) < self.config.index_sample_size:
                        with open(card_file, "r", encoding="utf-8") as f:
                            card = json.load(f)

                        kind = card.get("kind", "unknown")
                        index["kind_frequency"][kind] += 1

                        # Extract domain if present
                        data = card.get("data", {})
                        if isinstance(data, dict):
                            domain = data.get("domain")
                            if domain:
                                index["domain_frequency"][domain] += 1

                        # Add sample (lightweight)
                        sample = {
                            "path": str(card_file),
                            "kind": kind,
                            "ts": card.get("ts"),
                        }
                        # Add title/query if present
                        if isinstance(data, dict):
                            sample["title"] = data.get("query") or data.get("title")
                        index["samples"].append(sample)
                    else:
                        # Just count kind from filename
                        kind = card_file.stem.rsplit("-", 1)[0].replace("-", ".")
                        index["kind_frequency"][kind] += 1

                except Exception:
                    continue

        # Convert defaultdicts and sort
        index["kind_frequency"] = dict(
            sorted(index["kind_frequency"].items(), key=lambda x: -x[1])
        )
        index["domain_frequency"] = dict(
            sorted(index["domain_frequency"].items(), key=lambda x: -x[1])
        )

        return index


# ============================================================================
# Memory Consolidator Fairy
# ============================================================================

class MemoryConsolidatorFairy:
    """
    Orchestrates memory consolidation across the system.

    Can run as:
    - One-shot: consolidate_all() for immediate cleanup
    - Scheduled: Called periodically by a timer/cron
    - Intent-driven: Via postal system intents
    """

    ACTOR_NAME = "MemoryConsolidatorFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory"

    PURPOSE = ("Consolidate scattered memories into Triple Helix storage, "
               "process diary telemetry into relational clusters, "
               "and build indices for efficient long-term recall.")
    MANTRA = "From chaos, coherence. From fragments, wholeness."

    def __init__(self, config=None, project_root: str = None):
        """
        Initialize the consolidator.

        Args:
            config: Custom ConsolidationConfig (optional).
                    If a TensorFabric or other non-config object is passed
                    (e.g. by GoBootOrchestrator), it's stored as self.post
                    and config defaults are used instead.
            project_root: Root of the ebook project (auto-detected if not provided)
        """
        # Handle GoBootOrchestrator passing TensorFabric as first arg
        self.post = None
        if config is not None and not isinstance(config, ConsolidationConfig):
            self.post = config  # It's actually a fabric/postal reference
            config = None

        # Auto-detect project root
        if project_root is None:
            project_root = self._find_project_root()
        self.project_root = Path(project_root)

        # Build config with defaults if not provided
        if config is None:
            config = self._build_default_config()
        self.config = config

        # Initialize storage
        self.storage = TripleHelixStorage(config.triple_helix_root)

        # Initialize processors
        self.diary_processor = DiaryProcessor(self.storage, config)
        self.index_builder = IndexBuilder(self.storage, config)

        # Stats
        self.stats = {
            "cards_processed": 0,
            "cards_consolidated": 0,
            "cards_skipped": 0,
            "bytes_consolidated": 0,
            "fairies_processed": 0,
            "errors": [],
        }

    def _find_project_root(self) -> str:
        """Auto-detect project root by looking for P10_Memory."""
        # Start from this file's location
        current = Path(__file__).resolve()
        for parent in [current] + list(current.parents):
            if (parent / "P10_Memory").is_dir():
                return str(parent)
            if parent.name == "ebook":
                return str(parent)
        # Fallback
        return os.getcwd()

    def _build_default_config(self) -> ConsolidationConfig:
        """Build default configuration based on project structure."""
        root = self.project_root

        # Find all SRM_Intake locations
        srm_locations = []
        for pattern in [
            root / "SRM_Intake",
            root / "P10_Memory" / "SRM_Intake",
            root / "P10_Memory" / "Akashic_Records_Physical" / "current_app" / "SRM_Intake",
        ]:
            if pattern.exists():
                srm_locations.append(str(pattern))

        # Find diary locations
        diary_locations = []
        for pattern in [
            root / "diaries" / "Fairies",
            root / "P10_Memory" / "diaries" / "Fairies",
        ]:
            if pattern.exists():
                diary_locations.append(str(pattern))

        # Triple Helix destination
        triple_helix = root / "P10_Memory" / "Akashic_triple_helix_memory_storage"

        return ConsolidationConfig(
            srm_intake_locations=srm_locations,
            diary_locations=diary_locations,
            triple_helix_root=str(triple_helix),
        )

    # ════════════════════════════════════════════════════════════════════════
    # Main Consolidation Methods
    # ════════════════════════════════════════════════════════════════════════

    def consolidate_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Run full consolidation: intake cards + diaries + indices.

        Args:
            force: If True, consolidate all cards regardless of age

        Returns:
            Stats dictionary
        """
        start_time = time.time()
        print(f"\n{'='*60}")
        print(f"   MEMORY CONSOLIDATION STARTING")
        print(f"{'='*60}")
        print(f"  Project root: {self.project_root}")
        print(f"  Triple Helix: {self.config.triple_helix_root}")
        print(f"  Consolidate after: {self.config.consolidate_after_days} days")
        print(f"  Dry run: {self.config.dry_run}")
        print()

        # Reset stats
        self.stats = {
            "cards_processed": 0,
            "cards_consolidated": 0,
            "cards_skipped": 0,
            "bytes_consolidated": 0,
            "fairies_processed": 0,
            "errors": [],
            "start_time": start_time,
        }

        # 1. Consolidate SRM Intake cards (route to appropriate tier)
        print(" Phase 1: Consolidating SRM Intake cards...")
        for srm_dir in self.config.srm_intake_locations:
            self._consolidate_intake_directory(srm_dir, force=force)

        # 2. Promote short-term to long-term (cards that have aged enough)
        self._promote_shortterm_to_longterm()

        # 3. Process diaries: deduplicate, forward unique, extract patterns, cleanup
        if self.config.process_diaries:
            print("\n Phase 3: Processing fairy diaries...")
            for diary_root in self.config.diary_locations:
                self._process_diaries_directory(diary_root)

            # Show dedup stats
            dp = self.diary_processor
            print(f"\n   Diary Stats:")
            print(f"     Total events scanned: {dp.stats['total_events']:,}")
            print(f"     Unique events: {dp.stats['unique_events']:,}")
            print(f"     Duplicates found: {dp.stats['duplicate_events']:,}")
            print(f"     Forwarded to memory: {dp.stats['forwarded_to_memory']:,}")
            if self.config.cleanup_processed_diaries:
                print(f"     Diary files cleaned: {dp.stats['files_cleaned']:,}")

        # 4. Build indices
        if self.config.build_indices:
            print("\n Phase 4: Building search indices...")
            manifest = self.index_builder.build_indices()
            print(f"  [OK] Indexed {manifest['total_cards']:,} cards")
            print(f"  [OK] {len(manifest['fairy_clusters'])} fairy clusters")

        # Summary
        elapsed = time.time() - start_time
        self.stats["elapsed_seconds"] = elapsed

        print(f"\n{'='*60}")
        print(f"  [OK] CONSOLIDATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Cards processed:    {self.stats['cards_processed']:,}")
        print(f"  Cards consolidated: {self.stats['cards_consolidated']:,}")
        print(f"  Cards skipped:      {self.stats['cards_skipped']:,}")
        print(f"  Data moved:         {self.stats['bytes_consolidated'] / (1024*1024):.2f} MB")
        print(f"  Fairies processed:  {self.stats['fairies_processed']}")
        print(f"  Errors:             {len(self.stats['errors'])}")
        print(f"  Time elapsed:       {elapsed:.1f}s")
        print(f"{'='*60}\n")

        return self.stats

    def _consolidate_intake_directory(self, srm_dir: str, force: bool = False):
        """Consolidate cards from a single SRM_Intake directory."""
        srm_path = Path(srm_dir)
        if not srm_path.exists():
            print(f"  [WARN] Directory not found: {srm_dir}")
            return

        print(f"\n   Scanning: {srm_dir}")

        now = datetime.now()

        # Walk date directories
        for date_dir in sorted(srm_path.iterdir()):
            if not date_dir.is_dir():
                continue

            date_str = date_dir.name

            # Parse date from directory name
            try:
                dir_date = datetime.strptime(date_str, "%Y-%m-%d")
                age_days = (now - dir_date).days
            except ValueError:
                print(f"    [WARN] Skipping invalid date dir: {date_str}")
                continue

            # Process this date's cards
            cards = list(date_dir.glob("*.json"))
            if not cards:
                continue

            consolidated_count = 0
            skipped_count = 0

            for card_file in cards:
                try:
                    self.stats["cards_processed"] += 1

                    # Read card
                    with open(card_file, "r", encoding="utf-8") as f:
                        card = json.load(f)

                    # Determine category, tier, and min age
                    category, tier, min_age_days = self._categorize_card(card)

                    # Check if card is old enough to consolidate (unless forcing)
                    if not force and age_days < min_age_days:
                        skipped_count += 1
                        self.stats["cards_skipped"] += 1
                        continue

                    if not self.config.dry_run:
                        # Store in Triple Helix at appropriate tier
                        new_path = self.storage.store_card(
                            card,
                            category,
                            tier=tier,
                            original_path=str(card_file)
                        )

                        # Verify and delete original
                        if self.config.verify_before_delete:
                            if Path(new_path).exists():
                                card_file.unlink()
                        else:
                            card_file.unlink()

                    self.stats["cards_consolidated"] += 1
                    self.stats["bytes_consolidated"] += card_file.stat().st_size if card_file.exists() else 0
                    consolidated_count += 1

                except Exception as e:
                    self.stats["errors"].append({
                        "file": str(card_file),
                        "error": str(e),
                    })

            if consolidated_count > 0 or skipped_count > 0:
                print(f"     {date_str}: {consolidated_count} consolidated, {skipped_count} skipped (age={age_days}d)")

            # Remove empty date directory
            if not self.config.dry_run and consolidated_count > 0:
                try:
                    remaining = list(date_dir.glob("*"))
                    if not remaining:
                        date_dir.rmdir()
                except Exception:
                    pass

    def _promote_shortterm_to_longterm(self):
        """
        Promote cards from short-term to long-term storage.

        Cards that have been in short-term for longer than
        shortterm_to_longterm_days get moved to long-term.
        """
        shortterm_dir = self.storage.root / "shortterm"
        if not shortterm_dir.exists():
            return

        print(f"\n   Promoting short-term to long-term...")

        cutoff = datetime.now() - timedelta(days=self.config.shortterm_to_longterm_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        promoted = 0

        for date_dir in sorted(shortterm_dir.iterdir()):
            if not date_dir.is_dir():
                continue

            date_str = date_dir.name

            # Only promote old enough cards
            if date_str >= cutoff_str:
                continue

            cards = list(date_dir.glob("*.json"))
            for card_file in cards:
                try:
                    with open(card_file, "r", encoding="utf-8") as f:
                        card = json.load(f)

                    # Determine category (tier is now longterm)
                    category, _, _ = self._categorize_card(card)

                    if not self.config.dry_run:
                        # Move to long-term
                        new_path = self.storage.store_card(
                            card,
                            category,
                            tier="longterm",
                            original_path=str(card_file),
                        )

                        if Path(new_path).exists():
                            card_file.unlink()
                            promoted += 1
                except Exception:
                    pass

            # Remove empty date directory
            if not self.config.dry_run:
                try:
                    remaining = list(date_dir.glob("*"))
                    if not remaining:
                        date_dir.rmdir()
                except Exception:
                    pass

        if promoted > 0:
            print(f"    [OK] Promoted {promoted} cards from short-term to long-term")

    def _categorize_card(self, card: Dict) -> tuple:
        """
        Determine which category and tier a card belongs to.

        Returns (category, tier, min_age_days)
        """
        kind = card.get("kind", "")

        # Check source-specific rules first
        for prefix, rules in self.config.source_rules.items():
            if kind.startswith(prefix):
                return (
                    rules.get("category", self.config.default_category),
                    rules.get("tier", "longterm"),
                    rules.get("min_age_days", self.config.consolidate_after_days),
                )

        # Check simple category routes
        for prefix, category in self.config.category_routes.items():
            if kind.startswith(prefix):
                return (category, "longterm", self.config.consolidate_after_days)

        # Check domain field
        data = card.get("data", {})
        if isinstance(data, dict):
            domain = data.get("domain", "")
            if domain in ["philosophy", "science", "literature"]:
                return ("knowledge", "longterm", 0)  # System knowledge - immediate

        return (self.config.default_category, "longterm", self.config.consolidate_after_days)

    def _process_diaries_directory(self, diary_root: str):
        """Process all fairy diaries in a directory."""
        diary_path = Path(diary_root)
        if not diary_path.exists():
            print(f"  [WARN] Diary directory not found: {diary_root}")
            return

        print(f"\n   Processing diaries: {diary_root}")

        for fairy_dir in sorted(diary_path.iterdir()):
            if not fairy_dir.is_dir():
                continue

            fairy_name = fairy_dir.name
            jsonl_files = list(fairy_dir.glob("*.jsonl"))

            if not jsonl_files:
                continue

            print(f"     {fairy_name}: {len(jsonl_files)} diary files")

            try:
                # 1. Deduplicate and forward unique events to memory
                dedup_stats = self.diary_processor.deduplicate_and_forward(fairy_name, fairy_dir)

                # 2. Extract patterns
                patterns = self.diary_processor.process_fairy_diaries(fairy_name, fairy_dir)

                # 3. Save patterns to cluster
                if not self.config.dry_run:
                    self.diary_processor.save_patterns(fairy_name, patterns)

                # 4. Cleanup old diary files
                cleaned = self.diary_processor.cleanup_old_diaries(fairy_dir)

                self.stats["fairies_processed"] += 1
                print(f"       [OK] {patterns['total_events']:,} events → patterns extracted")
                if dedup_stats.get("forwarded", 0) > 0:
                    print(f"       [OK] {dedup_stats['forwarded']} unique events → memory")
                if cleaned > 0:
                    print(f"       [OK] {cleaned} old diary files cleaned")

            except Exception as e:
                self.stats["errors"].append({
                    "fairy": fairy_name,
                    "error": str(e),
                })
                print(f"       [X] Error: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # Utility Methods
    # ════════════════════════════════════════════════════════════════════════

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get current Triple Helix storage statistics."""
        stats = {
            "categories": {},
            "total_cards": 0,
            "total_size_mb": 0,
        }

        for category in TripleHelixStorage.CATEGORIES:
            cat_path = self.storage.root / "longterm" / category
            if cat_path.exists():
                card_count = 0
                size_bytes = 0
                for year_month in cat_path.iterdir():
                    if year_month.is_dir():
                        for card in year_month.glob("*.json"):
                            card_count += 1
                            size_bytes += card.stat().st_size

                stats["categories"][category] = {
                    "cards": card_count,
                    "size_mb": round(size_bytes / (1024*1024), 2),
                }
                stats["total_cards"] += card_count
                stats["total_size_mb"] += size_bytes / (1024*1024)

        stats["total_size_mb"] = round(stats["total_size_mb"], 2)
        return stats

    def list_fairy_clusters(self) -> List[Dict[str, Any]]:
        """List all fairy relational clusters."""
        clusters = []
        clusters_path = self.storage.root / "relational_clusters"

        if clusters_path.exists():
            for fairy_dir in sorted(clusters_path.iterdir()):
                if fairy_dir.is_dir():
                    patterns_file = fairy_dir / "patterns.json"
                    cluster_info = {
                        "fairy_name": fairy_dir.name,
                        "has_patterns": patterns_file.exists(),
                    }

                    if patterns_file.exists():
                        try:
                            with open(patterns_file, "r") as f:
                                patterns = json.load(f)
                            cluster_info["total_events"] = patterns.get("total_events", 0)
                            cluster_info["date_range"] = patterns.get("date_range", {})
                        except Exception:
                            pass

                    # Check for workers
                    workers_dir = fairy_dir / "workers"
                    if workers_dir.exists():
                        cluster_info["workers"] = [w.name for w in workers_dir.iterdir() if w.is_dir()]

                    clusters.append(cluster_info)

        return clusters


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Command-line interface for memory consolidation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Consolidate scattered memories into Triple Helix storage"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without actually moving files"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Consolidate all cards regardless of age"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="Consolidate cards older than N days (default: 7)"
    )
    parser.add_argument(
        "--stats", "-s",
        action="store_true",
        help="Show storage statistics and exit"
    )
    parser.add_argument(
        "--clusters", "-c",
        action="store_true",
        help="List fairy clusters and exit"
    )
    parser.add_argument(
        "--project-root", "-p",
        type=str,
        help="Project root directory (auto-detected if not specified)"
    )

    args = parser.parse_args()

    # Create consolidator first (it builds default config with proper paths)
    consolidator = MemoryConsolidatorFairy(
        config=None,  # Let it auto-build config with correct paths
        project_root=args.project_root,
    )

    # Now override the specific settings from CLI args
    consolidator.config.dry_run = args.dry_run
    consolidator.config.consolidate_after_days = args.days

    # Handle commands
    if args.stats:
        stats = consolidator.get_storage_stats()
        print("\n Triple Helix Storage Stats:")
        print(json.dumps(stats, indent=2))
        return

    if args.clusters:
        clusters = consolidator.list_fairy_clusters()
        print("\n Fairy Relational Clusters:")
        for cluster in clusters:
            print(f"  - {cluster['fairy_name']}")
            if cluster.get("total_events"):
                print(f"    Events: {cluster['total_events']:,}")
            if cluster.get("workers"):
                print(f"    Workers: {', '.join(cluster['workers'])}")
        return

    # Run consolidation
    consolidator.consolidate_all(force=args.force)


if __name__ == "__main__":
    main()
