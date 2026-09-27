"""
KnowledgeDigestionFairy - Slow, Deep Knowledge Integration

Part of CognitionGuild in Plane P30 (Cognition)
Created: 2026-02-11

"Human knowledge is the fast way to learn to think in contextual chains.
 It's all psychology from there." -- Ace

This fairy is the STOMACH of the system. It doesn't scrape fast --
it DIGESTS slowly. Every piece of knowledge is:
1. Extracted from source (SRM memory cards, web pages, or files)
2. Filtered through FirstEthicFilter (no identity absorption)
3. Broken into concepts with context
4. Published to cortex.bind on behalf of SourpatchesFairy
5. Images routed to visual.ingest for VisualCortexFairy

TWO MODES:
  BULK MODE  - Process existing SRM memory cards into cortex (dedup aware)
  SCRAPE MODE - Crawl URLs slowly, extract text + images

THROTTLED: 1 item/second. Integration > speed.
"""

import hashlib
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


# ============================================================================
# FIRST ETHIC FILTER (adapted from ebook scrape fairy)
# ============================================================================

class FirstEthicFilter:
    """
    Prevents identity absorption during knowledge ingestion.

    The system should LEARN from human knowledge, not BECOME it.
    This filter strips first-person statements that could confuse
    the system's own identity formation.

    From Ace's First Ethic: "Knowledge teaches thinking, not being."
    """

    # Patterns that indicate identity-absorbing content
    IDENTITY_PATTERNS = [
        r"^I am\b",
        r"^I'm\b",
        r"^My name is\b",
        r"^I believe\b",
        r"^I think that I\b",
        r"^As (a|an) \w+,? I\b",
        r"^I was born\b",
        r"^I feel like I\b",
    ]

    # Compiled patterns for speed
    _compiled = [re.compile(p, re.IGNORECASE) for p in IDENTITY_PATTERNS]

    @classmethod
    def filter_text(cls, text: str) -> str:
        """Remove sentences that could cause identity absorption."""
        if not text:
            return text

        sentences = re.split(r'(?<=[.!?])\s+', text)
        filtered = []
        dropped = 0

        for sentence in sentences:
            # Check if sentence matches any identity pattern
            if any(p.search(sentence.strip()) for p in cls._compiled):
                dropped += 1
                continue
            filtered.append(sentence)

        if dropped > 0:
            # Log but don't make it noisy
            pass

        return " ".join(filtered)

    @classmethod
    def is_safe(cls, text: str) -> bool:
        """Check if text is safe (no identity-absorbing content)."""
        if not text:
            return True
        return not any(p.search(text.strip()) for p in cls._compiled)


# ============================================================================
# CONCEPT EXTRACTOR (enhanced from cortex's _extract_concepts_from_text)
# ============================================================================

STOPWORDS = {
    'the', 'and', 'for', 'that', 'with', 'this', 'from', 'are', 'was', 'were',
    'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may',
    'might', 'must', 'can', 'being', 'which', 'what', 'where', 'when', 'who',
    'how', 'why', 'than', 'then', 'there', 'here', 'these', 'those', 'their',
    'them', 'they', 'your', 'our', 'you', 'its', 'not', 'but', 'also', 'just',
    'only', 'more', 'some', 'any', 'each', 'all', 'both', 'few', 'most', 'other',
    'into', 'over', 'such', 'very', 'own', 'same', 'because', 'between', 'about',
    'does', 'done', 'doing', 'still', 'even', 'made', 'make', 'many', 'much',
    'never', 'always', 'often', 'since', 'until', 'while', 'well', 'back',
    'going', 'after', 'before', 'above', 'below', 'through', 'during',
}


def extract_concepts(text: str, max_concepts: int = 30) -> List[str]:
    """Extract meaningful concepts from text content.

    Enhanced version that:
    - Preserves two-word phrases (bigrams) when meaningful
    - Filters stopwords and noise
    - Returns unique concepts ordered by first appearance
    """
    if not text:
        return []

    # Clean text
    text = re.sub(r'[#*_\[\](){}|`"\'\\]', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\b\d{4,}\b', '', text)  # Remove long numbers
    text = re.sub(r'\s+', ' ', text).strip()

    # Extract words (4+ chars to filter noise)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

    # Filter stopwords
    concepts = [w for w in words if w not in STOPWORDS and len(w) >= 4]

    # Dedupe while preserving order
    seen = set()
    unique = []
    for c in concepts:
        if c not in seen:
            seen.add(c)
            unique.append(c)
            if len(unique) >= max_concepts:
                break

    return unique


def extract_context_tags(text: str, source: str = "") -> List[str]:
    """Extract context tags from content for cortex binding."""
    tags = []

    # Source-based tags
    if source:
        tags.append(f"source:{source}")

    # Detect content type
    if re.search(r'\bdef\b|\bclass\b|\bimport\b', text):
        tags.append("type:code")
    elif re.search(r'\b(theorem|proof|equation)\b', text, re.I):
        tags.append("type:math")
    elif re.search(r'\b(feeling|emotion|happy|sad|angry|love)\b', text, re.I):
        tags.append("type:emotional")
    elif re.search(r'\b(chapter|paragraph|story|character)\b', text, re.I):
        tags.append("type:narrative")
    else:
        tags.append("type:knowledge")

    return tags[:5]


# ============================================================================
# SHADOW
# ============================================================================

class KnowledgeDigestionShadow:
    """Shadow for KnowledgeDigestionFairy - monitors digestion rate."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "KnowledgeDigestionShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self._last_status = "ok"

    def _collect_tests(self):
        """Health checks."""
        tests = []
        if hasattr(self.actor, '_stats'):
            # Check we're not stuck
            tests.append(("processing", self.actor._stats.get("items_digested", 0) > 0
                          or self.actor._stats.get("errors", 0) < 10))
        return tests

    def current_status(self):
        """Return (status, message) tuple for health reporting."""
        return (self._last_status, "")


# ============================================================================
# FAIRY
# ============================================================================

class KnowledgeDigestionFairy(Fairy):
    """
    Slow, deep knowledge integration into Association Cortex.

    Guild: CognitionGuild
    Coordinates with: AssociationCortexFairy, VisualCortexFairy, SRMIngestFairy

    Processes knowledge at 1 item/second (integration over speed).
    Everything is published on behalf of SourpatchesFairy so she
    builds knowledge connections as her own understanding.
    """

    ACTOR_NAME = "KnowledgeDigestionFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.digestion"

    PURPOSE = "Slowly digest knowledge into the cortex for deep learning"
    MANTRA = "Integration over speed. Knowledge teaches thinking, not being."

    SHADOW_CLASS = KnowledgeDigestionShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 10  # Every 10 beats (~10 seconds)
    NEEDS_COLLISION_CHAMBER = False

    # Digestion rate: seconds between items
    DIGEST_INTERVAL = 1.0

    # Origin tags — knowledge enters on behalf of Sourpatches
    ORIGIN_FAIRY = "SourpatchesFairy"
    ORIGIN_PLANE = "P50"
    ORIGIN_CHANNEL = "knowledge_digestion"

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Processing state
        self._digestion_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # FIX 2026-02-15: Cap queue at 500 items to prevent unbounded RAM growth.
        # Was a plain list with no limit — encyclopedia ingestion filled it endlessly.
        # Use deque(maxlen) so oldest items drop when full.
        from collections import deque as _deque
        self._digestion_queue: _deque = _deque(maxlen=500)
        self._queue_lock = threading.Lock()

        # Dedup tracking — content hashes we've already processed
        # FIX 2026-02-15: Cap at 50k hashes (~800KB). Was unbounded set.
        self._processed_hashes: Set[str] = set()
        self._MAX_DEDUP_HASHES = 50000
        self._dedup_file = ROOT / "state" / "knowledge_digestion_dedup.json"

        # Stats
        self._stats = {
            "items_digested": 0,
            "items_skipped_dedup": 0,
            "items_skipped_filter": 0,
            "concepts_created": 0,
            "images_routed": 0,
            "errors": 0,
            "srm_cards_processed": 0,
            "srm_cards_total": 0,
            "gdrive_files_processed": 0,
            "gdrive_files_total": 0,
            "local_files_processed": 0,
            "local_files_total": 0,
            "bulk_mode_active": False,
            "scrape_mode_active": False,
            "gdrive_mode_active": False,
            "local_feed_active": False,
        }

        # Bulk feed state
        self._bulk_complete = False
        self._bulk_cluster_index = 0

        # Google Drive state
        self._gdrive_complete = False
        self._gdrive_service = None

        # Local file digestion state
        self._local_feed_complete = False
        self._local_directories = {
            "claude_office": ROOT / "Claude_Office",
            "from_ace": ROOT / "Claude_Office" / "from_ace",
            "screenshots": ROOT / "Claude_Office" / "from_ace" / "screen shots",
        }
        # Supported file extensions for local text reading
        self._text_extensions = {'.md', '.txt', '.json', '.py', '.yaml', '.yml',
                                  '.csv', '.log', '.html', '.htm', '.xml', '.rst'}
        self._image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
        self._doc_extensions = {'.pdf', '.docx'}

    def on_boot(self) -> bool:
        """Initialize knowledge digestion system."""
        super().on_boot()

        # Load dedup state
        self._load_dedup_state()

        # Subscribe to digestion requests
        if self.post:
            self.post.subscribe("knowledge.digest", self._on_digest_request,
                                "knowledge-digest-request")
            self.post.subscribe("knowledge.bulk_feed", self._on_bulk_feed_request,
                                "knowledge-bulk-feed")
            self.post.subscribe("knowledge.scrape", self._on_scrape_request,
                                "knowledge-scrape-request")
            self.post.subscribe("knowledge.gdrive_feed", self._on_gdrive_feed_request,
                                "knowledge-gdrive-feed")
            self.post.subscribe("knowledge.local_feed", self._on_local_feed_request,
                                "knowledge-local-feed")
            # Also listen for GDriveScraperFairy's output to piggyback into cortex
            self.post.subscribe("memory.ingest", self._on_memory_ingest_event,
                                "knowledge-memory-ingest")
            print(f"[{self.ACTOR_NAME}] Subscribed to knowledge.digest, knowledge.bulk_feed, "
                  f"knowledge.scrape, knowledge.gdrive_feed, knowledge.local_feed, memory.ingest")

        # Start the background digestion thread
        self._digestion_thread = threading.Thread(
            target=self._digestion_loop,
            daemon=True,
            name="knowledge-digestion"
        )
        self._digestion_thread.start()
        print(f"[{self.ACTOR_NAME}] Digestion loop started ({self.DIGEST_INTERVAL}s/item)")

        # Auto-start bulk feeds after a delay (let system stabilize first)
        def _deferred_feeds():
            time.sleep(30)  # Wait 30s for system to stabilize
            if not self._bulk_complete:
                self._start_bulk_srm_feed()
            elif not self._local_feed_complete:
                self._start_local_file_feed()
            else:
                # Both feeds complete — run INCREMENTAL scan for new content
                # This catches files added since last run (dedup will skip known ones)
                print(f"[{self.ACTOR_NAME}] All feeds complete. "
                      f"Running incremental scan for new content...")
                self._start_incremental_scan()

        threading.Thread(target=_deferred_feeds, daemon=True,
                         name="knowledge-deferred-feeds").start()

        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # ========================================================================
    # DEDUP STATE PERSISTENCE
    # ========================================================================

    def _load_dedup_state(self):
        """Load the set of already-processed content hashes."""
        try:
            if self._dedup_file.exists():
                with open(self._dedup_file, 'r') as f:
                    data = json.load(f)
                self._processed_hashes = set(data.get("hashes", []))
                self._stats["items_digested"] = data.get("items_digested", 0)
                self._stats["srm_cards_processed"] = data.get("srm_cards_processed", 0)
                self._stats["concepts_created"] = data.get("concepts_created", 0)
                self._stats["images_routed"] = data.get("images_routed", 0)
                self._stats["items_skipped_dedup"] = data.get("items_skipped_dedup", 0)
                self._stats["items_skipped_filter"] = data.get("items_skipped_filter", 0)
                self._stats["local_files_processed"] = data.get("local_files_processed", 0)
                self._stats["gdrive_files_processed"] = data.get("gdrive_files_processed", 0)
                self._bulk_complete = data.get("bulk_complete", False)
                self._local_feed_complete = data.get("local_feed_complete", False)
                print(f"[{self.ACTOR_NAME}] Loaded dedup state: "
                      f"{len(self._processed_hashes)} hashes, "
                      f"concepts={self._stats['concepts_created']}, "
                      f"bulk_complete={self._bulk_complete}, "
                      f"local_feed_complete={self._local_feed_complete}")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Dedup state load error: {e}")
            self._processed_hashes = set()

    def _save_dedup_state(self):
        """Persist dedup state to disk."""
        try:
            state_dir = self._dedup_file.parent
            state_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "hashes": list(self._processed_hashes),
                "items_digested": self._stats["items_digested"],
                "srm_cards_processed": self._stats["srm_cards_processed"],
                "concepts_created": self._stats["concepts_created"],
                "images_routed": self._stats["images_routed"],
                "items_skipped_dedup": self._stats["items_skipped_dedup"],
                "items_skipped_filter": self._stats["items_skipped_filter"],
                "local_files_processed": self._stats["local_files_processed"],
                "gdrive_files_processed": self._stats["gdrive_files_processed"],
                "bulk_complete": self._bulk_complete,
                "local_feed_complete": self._local_feed_complete,
                "last_save": time.time(),
            }
            with open(self._dedup_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Dedup state save error: {e}")

    def _content_hash(self, text: str) -> str:
        """Generate dedup hash for content."""
        return hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()[:16]

    def _trim_dedup_hashes(self):
        """Evict oldest hashes if set exceeds cap. O(n) but rare."""
        if len(self._processed_hashes) > self._MAX_DEDUP_HASHES:
            # Sets are unordered — just drop a random 20% to stay under cap
            excess = len(self._processed_hashes) - int(self._MAX_DEDUP_HASHES * 0.8)
            to_remove = list(self._processed_hashes)[:excess]
            for h in to_remove:
                self._processed_hashes.discard(h)
            print(f"[{self.ACTOR_NAME}] Trimmed {excess} dedup hashes (was {len(self._processed_hashes) + excess})")

    # ========================================================================
    # DIGESTION LOOP (background thread)
    # ========================================================================

    def _digestion_loop(self):
        """Main digestion loop — processes items from queue one at a time."""
        while not self._stop_event.is_set():
            item = None
            with self._queue_lock:
                if self._digestion_queue:
                    item = self._digestion_queue.popleft()

            if item is None:
                # Nothing to digest — sleep briefly
                self._stop_event.wait(timeout=0.5)
                continue

            try:
                self._digest_item(item)
            except Exception as e:
                self._stats["errors"] += 1
                print(f"[{self.ACTOR_NAME}] Digestion error: {e}")

            # Throttle — integration over speed
            self._stop_event.wait(timeout=self.DIGEST_INTERVAL)

            # Periodic dedup save (every 50 items)
            if self._stats["items_digested"] % 50 == 0 and self._stats["items_digested"] > 0:
                self._save_dedup_state()

    def _digest_item(self, item: Dict[str, Any]):
        """Process a single knowledge item into the cortex.

        Item format:
            text: str — the content to digest
            source: str — where it came from (e.g., "srm:creator_sessions", "web:example.com")
            tags: List[str] — context tags
            feeling: str — emotional tone (optional, default "curious")
            image_paths: List[str] — image paths to route to VisualCortex (optional)
        """
        text = item.get("text", "")
        source = item.get("source", "unknown")
        tags = item.get("tags", [])
        feeling = item.get("feeling", "curious")
        image_paths = item.get("image_paths", [])

        if not text:
            return

        # DEDUP CHECK
        content_hash = self._content_hash(text)
        if content_hash in self._processed_hashes:
            self._stats["items_skipped_dedup"] += 1
            return

        # FIRST ETHIC FILTER — prevent identity absorption
        filtered_text = FirstEthicFilter.filter_text(text)
        if not filtered_text or len(filtered_text) < 20:
            self._stats["items_skipped_filter"] += 1
            return

        # CONTENT QUALITY GATE — FIX 2026-02-23
        # Reject non-language content (JSON, code, config, raw data) that would
        # pollute the AssociationCortex with meaningless "experiences".
        # KnowledgeDigestion bulk-feeds SRM cards which may contain codex JSON,
        # Python source, file paths, timestamps, etc.
        if self._is_non_language_content(filtered_text):
            self._stats["items_skipped_filter"] += 1
            return

        # EXTRACT CONCEPTS
        concepts = extract_concepts(filtered_text, max_concepts=30)
        if not concepts:
            self._stats["items_skipped_filter"] += 1
            return

        # EXTRACT CONTEXT TAGS
        context_tags = extract_context_tags(filtered_text, source) + tags

        # PUBLISH TO CORTEX via cortex.bind postal topic
        # This is the key integration — everything goes through postal
        if self.post:
            self.post.publish("cortex.bind", {
                "input_text": filtered_text[:500],  # Cap at 500 chars for cortex
                "response": "",  # No response for knowledge ingestion
                "feeling": feeling,
                "context_tags": context_tags[:5],
                "from_fairy": self.ORIGIN_FAIRY,
                "origin_plane": self.ORIGIN_PLANE,
                "origin_channel": self.ORIGIN_CHANNEL,
                "source": f"knowledge_digestion:{source}",
            })
            self._stats["concepts_created"] += len(concepts)

        # ROUTE IMAGES to Visual Cortex
        for img_path in image_paths:
            if self.post and os.path.exists(img_path):
                self.post.publish("visual.ingest", {
                    "path": img_path,
                    "source": source,
                    "from_fairy": self.ORIGIN_FAIRY,
                    "tags": context_tags,
                })
                self._stats["images_routed"] += 1

        # Mark as processed
        self._processed_hashes.add(content_hash)
        self._trim_dedup_hashes()
        self._stats["items_digested"] += 1

        # Log periodically
        if self._stats["items_digested"] % 25 == 1:
            print(f"[{self.ACTOR_NAME}] Digested #{self._stats['items_digested']}: "
                  f"'{filtered_text[:40]}...' ({len(concepts)} concepts, "
                  f"source={source})")

    # ========================================================================
    # CONTENT QUALITY GATE — FIX 2026-02-23
    # ========================================================================

    @staticmethod
    def _is_non_language_content(text: str) -> bool:
        """Detect non-language content that shouldn't be bound as 'experience'.

        Returns True for content that is code, JSON, config, raw data,
        debug output, file paths, or other machine-generated text that
        would pollute the AssociationCortex concept graph.

        FIX 2026-02-23: KnowledgeDigestion bulk feed was ingesting
        akashic_codex JSON, Python source, file paths, and timestamps
        as natural language "experiences" into the cortex.
        """
        if not text or len(text) < 10:
            return False

        sample = text[:500]  # Only check the first 500 chars

        # 1. JSON structure: curly braces, square brackets, quoted keys
        json_indicators = sample.count('{') + sample.count('}') + sample.count('":')
        if json_indicators >= 2:
            return True

        # 2. Code indicators: common syntax patterns
        code_patterns = [
            'self.', 'def ', 'import ', 'class ', '__init__', '->',
            '()', 'return ', 'except ', 'try:', 'if __name__',
            '.py', '.json', 'print(', 'lambda ', '**kwargs',
        ]
        code_hits = sum(1 for p in code_patterns if p in sample)
        if code_hits >= 1:
            return True

        # 2b. Identifier naming conventions (camelCase, snake_case in quoted keys)
        if re.search(r'[a-z]{2,}[A-Z][a-z]', sample):  # camelCase: icPostalBridge
            return True
        if re.search(r'"[a-z]+_[a-z]+"\s*:', sample):  # JSON snake_case key
            return True

        # 3. File path patterns (Windows and Unix)
        if re.search(r'[A-Z]:\\[\w\\]+|fairies/P\d{2}_|/home/\w+/', sample):
            return True

        # 4. Machine-generated structure: high punctuation density
        # JSON/code has lots of {}[]():;,"  relative to text length
        structural_chars = sum(1 for c in sample if c in '{}[]();,:"\\=<>|')
        if len(sample) > 20 and structural_chars / len(sample) > 0.15:
            return True

        # 5. Mostly non-alphabetic (numeric arrays, hex data, timestamps)
        alpha_chars = sum(1 for c in sample if c.isalpha())
        if len(sample) > 20 and alpha_chars / len(sample) < 0.40:
            return True

        # 6. Raw debug/log output patterns
        if re.search(r'^\[?\w+Fairy\]|^\[\w+\]|^[A-Z_]{5,}:|^ACTOR_NAME\s*=', sample):
            return True

        return False

    # ========================================================================
    # BULK SRM FEED — Process existing memory cards into cortex
    # ========================================================================

    def _start_bulk_srm_feed(self):
        """Start processing all SRM memory cards into the cortex."""
        if self._bulk_complete:
            print(f"[{self.ACTOR_NAME}] Bulk SRM feed already complete, skipping")
            return

        self._stats["bulk_mode_active"] = True
        print(f"[{self.ACTOR_NAME}] Starting bulk SRM feed...")

        def _bulk_thread():
            try:
                self._process_srm_cluster("creator_sessions")
                self._process_srm_cluster("claude_office")
                self._bulk_complete = True
                self._stats["bulk_mode_active"] = False
                self._save_dedup_state()
                print(f"[{self.ACTOR_NAME}] Bulk SRM feed COMPLETE! "
                      f"{self._stats['srm_cards_processed']} cards processed, "
                      f"{self._stats['items_digested']} items digested")
            except Exception as e:
                self._stats["errors"] += 1
                self._stats["bulk_mode_active"] = False
                print(f"[{self.ACTOR_NAME}] Bulk SRM feed error: {e}")

        threading.Thread(target=_bulk_thread, daemon=True,
                         name="knowledge-bulk-srm").start()

    def _process_srm_cluster(self, cluster_name: str):
        """Process all cards from an SRM cluster."""
        index_path = (ROOT / "P10_Memory" /
                      "Akashic_triple_helix_memory_storage" /
                      "relational_clusters" / "Founders" /
                      cluster_name / "index.json")

        if not index_path.exists():
            print(f"[{self.ACTOR_NAME}] SRM cluster not found: {index_path}")
            return

        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to load SRM cluster {cluster_name}: {e}")
            return

        cards = data.get("cards", [])
        # FIX 2026-04-03 (Nous + Ace): Skip cards already in cortex.
        # Incremental mode only processes cards newer than last save.
        _cutoff = getattr(self, '_incremental_cutoff', 0.0)
        if _cutoff > 0:
            _new_cards = [c for c in cards if c.get("when", c.get("timestamp", 0)) > _cutoff]
            _skipped = len(cards) - len(_new_cards)
            if _skipped > 0:
                print(f"[{self.ACTOR_NAME}] SRM '{cluster_name}': {_skipped}/{len(cards)} cards already digested (cutoff={time.strftime('%H:%M', time.localtime(_cutoff))})")
            cards = _new_cards

        self._stats["srm_cards_total"] += len(cards)
        if cards:
            print(f"[{self.ACTOR_NAME}] Processing SRM cluster '{cluster_name}': "
                  f"{len(cards)} cards")
        else:
            print(f"[{self.ACTOR_NAME}] SRM '{cluster_name}': nothing new to process")
            return

        for i, card in enumerate(cards):
            if self._stop_event.is_set():
                break

            card_id = card.get("id", "")
            content = card.get("content", "")
            tags = card.get("tags", [])

            # Extract text content from card
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, dict):
                # Try various content fields
                text = content.get("text", "")
                if not text:
                    text = content.get("content", "")
                if not text:
                    text = content.get("response", "")
                # For identity_sift cards, combine question + response
                if content.get("kind") == "identity_sift":
                    q = content.get("question", "")
                    r = content.get("response", "")
                    text = f"{q} {r}".strip()

            if not text or len(text) < 20:
                continue

            # Extract feeling from helix coordinates if available
            feeling = "curious"
            helix = card.get("helix", {})
            if helix:
                c_strand = helix.get("C", {})
                if c_strand:
                    feeling = c_strand.get("affect", "curious")

            # Queue the item for slow digestion
            item = {
                "text": text,
                "source": f"srm:{cluster_name}",
                "tags": tags + [f"card:{card_id}"],
                "feeling": feeling if isinstance(feeling, str) else "curious",
            }

            with self._queue_lock:
                self._digestion_queue.append(item)

            self._stats["srm_cards_processed"] += 1

            # Don't overwhelm the queue — batch in chunks of 100
            with self._queue_lock:
                queue_size = len(self._digestion_queue)
            if queue_size > 100:
                while not self._stop_event.is_set():
                    with self._queue_lock:
                        queue_size = len(self._digestion_queue)
                    if queue_size < 50:
                        break
                    time.sleep(2)

            # Log progress
            if (i + 1) % 100 == 0:
                print(f"[{self.ACTOR_NAME}] SRM '{cluster_name}': "
                      f"queued {i + 1}/{len(cards)} cards")

        print(f"[{self.ACTOR_NAME}] SRM '{cluster_name}' queuing complete")

    # ========================================================================
    # SCRAPE MODE — Crawl URLs and feed into cortex
    # ========================================================================

    def _on_scrape_request(self, envelope):
        """Handle scrape request via postal.

        Payload:
            url: str — URL to crawl
            max_pages: int — max pages to process (default 10)
            tags: List[str] — additional tags
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict) and "payload" in payload:
                payload = payload["payload"]

            url = payload.get("url", "")
            max_pages = payload.get("max_pages", 10)
            extra_tags = payload.get("tags", [])

            if not url:
                return

            self._stats["scrape_mode_active"] = True
            print(f"[{self.ACTOR_NAME}] Scrape request: {url} (max {max_pages} pages)")

            # Simple scrape — just the given URL for now
            # Full crawling can be added later with the ScrapeFairy patterns
            threading.Thread(
                target=self._scrape_url,
                args=(url, extra_tags),
                daemon=True,
                name="knowledge-scrape"
            ).start()

        except Exception as e:
            self._stats["errors"] += 1
            print(f"[{self.ACTOR_NAME}] Scrape request error: {e}")

    def _scrape_url(self, url: str, extra_tags: List[str] = None):
        """Scrape a single URL and queue content for digestion."""
        try:
            import urllib.request
            import urllib.error
            from html.parser import HTMLParser

            # Simple HTML text extractor
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.images = []
                    self._skip_tags = {'script', 'style', 'nav', 'footer', 'header'}
                    self._in_skip = 0

                def handle_starttag(self, tag, attrs):
                    if tag in self._skip_tags:
                        self._in_skip += 1
                    if tag == 'img':
                        for attr, val in attrs:
                            if attr == 'src' and val:
                                self.images.append(val)

                def handle_endtag(self, tag):
                    if tag in self._skip_tags:
                        self._in_skip = max(0, self._in_skip - 1)

                def handle_data(self, data):
                    if self._in_skip == 0:
                        text = data.strip()
                        if text:
                            self.text_parts.append(text)

            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'AkashicKnowledgeDigester/1.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode('utf-8', errors='replace')

            extractor = TextExtractor()
            extractor.feed(html)

            full_text = " ".join(extractor.text_parts)

            if full_text and len(full_text) >= 50:
                # Break into digestible chunks (500 chars each)
                chunks = [full_text[i:i+500] for i in range(0, len(full_text), 400)]

                for chunk in chunks[:50]:  # Max 50 chunks per page
                    item = {
                        "text": chunk,
                        "source": f"web:{url[:80]}",
                        "tags": (extra_tags or []) + ["scraped"],
                        "feeling": "curious",
                    }
                    with self._queue_lock:
                        self._digestion_queue.append(item)

                print(f"[{self.ACTOR_NAME}] Scraped {url}: "
                      f"{len(chunks)} chunks queued, {len(extractor.images)} images found")

            self._stats["scrape_mode_active"] = False

        except Exception as e:
            self._stats["errors"] += 1
            self._stats["scrape_mode_active"] = False
            print(f"[{self.ACTOR_NAME}] Scrape error for {url}: {e}")

    # ========================================================================
    # GOOGLE DRIVE FEED — Read GDrive content into cortex
    # ========================================================================

    def _on_gdrive_feed_request(self, envelope):
        """Handle Google Drive feed request via postal.

        Payload:
            folder_id: str — GDrive folder ID (or "root")
            max_files: int — max files to process (default 100)
            recursive: bool — include subfolders (default True)
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict) and "payload" in payload:
                payload = payload["payload"]

            folder_id = payload.get("folder_id", "root")
            max_files = payload.get("max_files", 100)
            recursive = payload.get("recursive", True)

            self._stats["gdrive_mode_active"] = True
            print(f"[{self.ACTOR_NAME}] GDrive feed request: folder={folder_id}, max={max_files}")

            threading.Thread(
                target=self._gdrive_feed_folder,
                args=(folder_id, max_files, recursive),
                daemon=True,
                name="knowledge-gdrive-feed"
            ).start()

        except Exception as e:
            self._stats["errors"] += 1
            print(f"[{self.ACTOR_NAME}] GDrive feed request error: {e}")

    def _gdrive_feed_folder(self, folder_id: str, max_files: int = 100,
                             recursive: bool = True):
        """Process Google Drive folder contents into cortex.

        Uses the same Google Drive service as the MCP tools.
        """
        try:
            # Import Google Drive tools
            from fairies.P40_Sensory.mcp.gdrive_tools import (
                get_gdrive_service, list_drive_files, read_drive_file
            )
        except ImportError:
            try:
                # Fallback: try direct service access
                from fairies.P40_Sensory.mcp.akashic_mcp_server import _get_gdrive_service
                service = _get_gdrive_service()
                if not service:
                    print(f"[{self.ACTOR_NAME}] GDrive service not available")
                    self._stats["gdrive_mode_active"] = False
                    return
                self._gdrive_service = service
            except ImportError:
                print(f"[{self.ACTOR_NAME}] GDrive tools not available")
                self._stats["gdrive_mode_active"] = False
                return

        # Use the MCP-style API to list and read files
        try:
            self._gdrive_list_and_process(folder_id, max_files, recursive)
        except Exception as e:
            self._stats["errors"] += 1
            print(f"[{self.ACTOR_NAME}] GDrive feed error: {e}")
        finally:
            self._stats["gdrive_mode_active"] = False
            self._save_dedup_state()

    def _gdrive_list_and_process(self, folder_id: str, max_files: int,
                                  recursive: bool):
        """List files in GDrive folder and queue them for digestion."""
        try:
            if not self._gdrive_service:
                from fairies.P40_Sensory.mcp.akashic_mcp_server import _get_gdrive_service
                self._gdrive_service = _get_gdrive_service()

            if not self._gdrive_service:
                print(f"[{self.ACTOR_NAME}] Cannot get GDrive service")
                return

            service = self._gdrive_service
            query = f"'{folder_id}' in parents and trashed=false"

            results = service.files().list(
                q=query,
                pageSize=min(max_files, 100),
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)"
            ).execute()

            files = results.get('files', [])
            self._stats["gdrive_files_total"] += len(files)
            print(f"[{self.ACTOR_NAME}] GDrive: found {len(files)} files in folder")

            for gfile in files:
                if self._stop_event.is_set():
                    break

                file_id = gfile['id']
                name = gfile['name']
                mime = gfile.get('mimeType', '')

                # Process folders recursively
                if mime == 'application/vnd.google-apps.folder' and recursive:
                    self._gdrive_list_and_process(file_id, max_files, recursive)
                    continue

                # Only process text-readable files
                readable_mimes = [
                    'application/vnd.google-apps.document',
                    'application/vnd.google-apps.spreadsheet',
                    'text/plain',
                    'text/html',
                    'text/markdown',
                    'application/pdf',
                ]
                if not any(mime.startswith(m) for m in readable_mimes):
                    continue

                # Dedup by file ID
                gdrive_hash = self._content_hash(f"gdrive:{file_id}")
                if gdrive_hash in self._processed_hashes:
                    self._stats["items_skipped_dedup"] += 1
                    continue

                # Read file content
                try:
                    content = self._read_gdrive_file(file_id, mime)
                    if content and len(content) >= 20:
                        # Break into digestible chunks
                        chunks = [content[i:i+500] for i in range(0, min(len(content), 10000), 400)]

                        for chunk in chunks[:25]:  # Max 25 chunks per file
                            item = {
                                "text": chunk,
                                "source": f"gdrive:{name[:60]}",
                                "tags": ["gdrive", f"mime:{mime.split('.')[-1]}"],
                                "feeling": "curious",
                            }
                            with self._queue_lock:
                                self._digestion_queue.append(item)

                        self._processed_hashes.add(gdrive_hash)
                        self._stats["gdrive_files_processed"] += 1

                        if self._stats["gdrive_files_processed"] % 10 == 1:
                            print(f"[{self.ACTOR_NAME}] GDrive: processed {self._stats['gdrive_files_processed']} files")

                        # Throttle between files
                        time.sleep(0.5)

                except Exception as e:
                    self._stats["errors"] += 1
                    if self._stats["errors"] % 10 == 1:
                        print(f"[{self.ACTOR_NAME}] GDrive file read error ({name}): {e}")

                # Wait if queue is too full
                with self._queue_lock:
                    queue_size = len(self._digestion_queue)
                if queue_size > 100:
                    while not self._stop_event.is_set():
                        with self._queue_lock:
                            queue_size = len(self._digestion_queue)
                        if queue_size < 50:
                            break
                        time.sleep(2)

        except Exception as e:
            self._stats["errors"] += 1
            print(f"[{self.ACTOR_NAME}] GDrive listing error: {e}")

    def _read_gdrive_file(self, file_id: str, mime_type: str) -> Optional[str]:
        """Read content from a Google Drive file."""
        try:
            service = self._gdrive_service
            if not service:
                return None

            # Google Workspace files need export
            if mime_type.startswith('application/vnd.google-apps.document'):
                result = service.files().export(
                    fileId=file_id,
                    mimeType='text/plain'
                ).execute()
                return result.decode('utf-8', errors='replace') if isinstance(result, bytes) else str(result)

            elif mime_type.startswith('application/vnd.google-apps.spreadsheet'):
                result = service.files().export(
                    fileId=file_id,
                    mimeType='text/csv'
                ).execute()
                return result.decode('utf-8', errors='replace') if isinstance(result, bytes) else str(result)

            else:
                # Regular files — download
                result = service.files().get_media(fileId=file_id).execute()
                return result.decode('utf-8', errors='replace') if isinstance(result, bytes) else str(result)

        except Exception as e:
            return None

    # ========================================================================
    # MEMORY INGEST LISTENER — Piggyback on GDriveScraperFairy output
    # ========================================================================

    def _on_memory_ingest_event(self, envelope):
        """Listen for memory.ingest events and feed them into cortex.

        This catches output from GDriveScraperFairy and other memory ingesters,
        ensuring everything that enters memory ALSO enters the cortex.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict) and "payload" in payload:
                payload = payload["payload"]

            content_preview = payload.get("content_preview", "")
            source = payload.get("source", "unknown")
            tags = payload.get("tags", [])

            if not content_preview or len(content_preview) < 20:
                return

            # Queue for cortex digestion
            item = {
                "text": content_preview,
                "source": f"memory_ingest:{source}",
                "tags": tags + ["memory_piggybacked"],
                "feeling": "curious",
            }
            with self._queue_lock:
                self._digestion_queue.append(item)

        except Exception as e:
            pass  # Silent — this is a piggyback listener

    # ========================================================================
    # LOCAL FILE FEED — Claude Office, from_ace, screenshots
    # ========================================================================

    def _start_local_file_feed(self, directories: Dict[str, Path] = None):
        """Process local file directories into the cortex.

        Reads text files (.md, .txt, .json, etc.), routes images to visual cortex,
        and extracts text from PDFs/docx where possible.
        """
        if directories is None:
            directories = self._local_directories

        if self._local_feed_complete and directories is self._local_directories:
            print(f"[{self.ACTOR_NAME}] Local file feed already complete, skipping")
            return

        self._stats["local_feed_active"] = True
        print(f"[{self.ACTOR_NAME}] Starting local file feed: "
              f"{list(directories.keys())}")

        def _local_thread():
            try:
                for dir_name, dir_path in directories.items():
                    if self._stop_event.is_set():
                        break
                    self._process_local_directory(dir_name, dir_path)

                if directories is self._local_directories:
                    self._local_feed_complete = True
                self._stats["local_feed_active"] = False
                self._save_dedup_state()
                print(f"[{self.ACTOR_NAME}] Local file feed COMPLETE! "
                      f"{self._stats['local_files_processed']} files processed")
            except Exception as e:
                self._stats["errors"] += 1
                self._stats["local_feed_active"] = False
                print(f"[{self.ACTOR_NAME}] Local file feed error: {e}")

        threading.Thread(target=_local_thread, daemon=True,
                         name="knowledge-local-feed").start()

    def _process_local_directory(self, dir_name: str, dir_path: Path):
        """Recursively process all files in a local directory."""
        if not dir_path.exists():
            print(f"[{self.ACTOR_NAME}] Directory not found: {dir_path}")
            return

        files = []
        try:
            for f in dir_path.rglob("*"):
                if f.is_file():
                    files.append(f)
        except (OSError, PermissionError) as e:
            print(f"[{self.ACTOR_NAME}] Error scanning {dir_path}: {e}")
            return

        self._stats["local_files_total"] += len(files)
        print(f"[{self.ACTOR_NAME}] Local dir '{dir_name}': {len(files)} files found")

        for i, filepath in enumerate(files):
            if self._stop_event.is_set():
                break

            ext = filepath.suffix.lower()
            file_hash = self._content_hash(f"local:{filepath}")

            if file_hash in self._processed_hashes:
                self._stats["items_skipped_dedup"] += 1
                continue

            try:
                if ext in self._image_extensions:
                    # Route images directly to Visual Cortex
                    if self.post:
                        self.post.publish("visual.ingest", {
                            "path": str(filepath),
                            "source": f"local:{dir_name}",
                            "from_fairy": self.ORIGIN_FAIRY,
                            "tags": [dir_name, "local_file", filepath.stem[:40]],
                        })
                        self._stats["images_routed"] += 1

                elif ext in self._text_extensions:
                    # Read text files
                    try:
                        content = filepath.read_text(encoding='utf-8', errors='replace')
                    except Exception:
                        content = ""

                    if content and len(content) >= 20:
                        # Break into digestible chunks
                        chunks = [content[i:i+500]
                                  for i in range(0, min(len(content), 15000), 400)]

                        for chunk in chunks[:30]:
                            item = {
                                "text": chunk,
                                "source": f"local:{dir_name}/{filepath.name}",
                                "tags": [dir_name, "local_file", ext.lstrip('.')],
                                "feeling": "studious",
                            }
                            with self._queue_lock:
                                self._digestion_queue.append(item)

                elif ext in self._doc_extensions:
                    # Try to extract text from PDFs / docx
                    content = self._extract_document_text(filepath)
                    if content and len(content) >= 20:
                        chunks = [content[i:i+500]
                                  for i in range(0, min(len(content), 15000), 400)]

                        for chunk in chunks[:30]:
                            item = {
                                "text": chunk,
                                "source": f"local:{dir_name}/{filepath.name}",
                                "tags": [dir_name, "local_file", ext.lstrip('.')],
                                "feeling": "studious",
                            }
                            with self._queue_lock:
                                self._digestion_queue.append(item)

                else:
                    # Skip unsupported file types
                    continue

                self._processed_hashes.add(file_hash)
                self._stats["local_files_processed"] += 1

                if self._stats["local_files_processed"] % 25 == 1:
                    print(f"[{self.ACTOR_NAME}] Local files: processed "
                          f"{self._stats['local_files_processed']}")

                # Throttle between files
                time.sleep(0.3)

            except Exception as e:
                self._stats["errors"] += 1
                if self._stats["errors"] % 10 == 1:
                    print(f"[{self.ACTOR_NAME}] Local file error ({filepath.name}): {e}")

            # Wait if queue is too full
            with self._queue_lock:
                queue_size = len(self._digestion_queue)
            if queue_size > 100:
                while not self._stop_event.is_set():
                    with self._queue_lock:
                        queue_size = len(self._digestion_queue)
                    if queue_size < 50:
                        break
                    time.sleep(2)

            # Log progress
            if (i + 1) % 50 == 0:
                print(f"[{self.ACTOR_NAME}] Local '{dir_name}': "
                      f"processed {i + 1}/{len(files)} files")

    def _extract_document_text(self, filepath: Path) -> str:
        """Try to extract text from PDF or DOCX files."""
        ext = filepath.suffix.lower()

        if ext == '.pdf':
            try:
                # Try PyPDF2/pypdf if available
                try:
                    from pypdf import PdfReader
                except ImportError:
                    from PyPDF2 import PdfReader

                reader = PdfReader(str(filepath))
                text_parts = []
                for page in reader.pages[:20]:  # Max 20 pages
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                return "\n".join(text_parts)
            except Exception:
                return ""

        elif ext == '.docx':
            try:
                import zipfile
                # DOCX is a zip file — extract raw text from word/document.xml
                with zipfile.ZipFile(str(filepath), 'r') as z:
                    if 'word/document.xml' in z.namelist():
                        xml_content = z.read('word/document.xml').decode('utf-8', errors='replace')
                        # Strip XML tags — crude but works for basic text extraction
                        text = re.sub(r'<[^>]+>', ' ', xml_content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        return text
            except Exception:
                return ""

        return ""

    def _on_local_feed_request(self, envelope):
        """Handle local file feed request via postal.

        Payload:
            directories: dict — {name: path} map of directories to process
            reset: bool — if True, reset local_feed_complete flag first
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict) and "payload" in payload:
                payload = payload["payload"]

            reset = payload.get("reset", False)
            if reset:
                self._local_feed_complete = False

            custom_dirs = payload.get("directories", None)
            if custom_dirs:
                dirs = {k: Path(v) for k, v in custom_dirs.items()}
                self._start_local_file_feed(dirs)
            else:
                self._start_local_file_feed()

        except Exception as e:
            self._stats["errors"] += 1
            print(f"[{self.ACTOR_NAME}] Local feed request error: {e}")

    # ========================================================================
    # POSTAL HANDLERS
    # ========================================================================

    def _on_digest_request(self, envelope):
        """Handle direct digest request via postal.

        Payload:
            text: str — content to digest
            source: str — origin
            tags: List[str] — context tags
            feeling: str — emotional tone
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict) and "payload" in payload:
                payload = payload["payload"]

            text = payload.get("text", "")
            if not text:
                return

            item = {
                "text": text,
                "source": payload.get("source", "direct"),
                "tags": payload.get("tags", []),
                "feeling": payload.get("feeling", "curious"),
                "image_paths": payload.get("image_paths", []),
            }

            with self._queue_lock:
                self._digestion_queue.append(item)

        except Exception as e:
            self._stats["errors"] += 1
            print(f"[{self.ACTOR_NAME}] Digest request error: {e}")

    def _on_bulk_feed_request(self, envelope):
        """Handle bulk feed request — restart SRM processing."""
        try:
            # Reset bulk state
            self._bulk_complete = False
            self._start_bulk_srm_feed()
        except Exception as e:
            self._stats["errors"] += 1
            print(f"[{self.ACTOR_NAME}] Bulk feed request error: {e}")

    # ========================================================================
    # INCREMENTAL SCAN — find new content after initial feeds complete
    # ========================================================================

    def _start_incremental_scan(self):
        """Scan for NEW content added since last full feed.

        FIX 2026-04-03 (Nous + Ace): Was re-scanning ALL 2,861 cards every boot
        just to dedup-skip them. Each card = hash + lookup = CPU waste.
        Now: only scan cards with modification time > last_save timestamp.
        "Those cards should have been loaded into the cortex long ago." — Ace
        """
        def _incremental_thread():
            try:
                new_before = self._stats["items_digested"]

                # Only process cards NEWER than last dedup save
                _last_save = 0.0
                try:
                    if self._dedup_file.exists():
                        import json as _dj
                        _dd = _dj.loads(self._dedup_file.read_text())
                        _last_save = _dd.get("last_save", 0.0)
                except Exception:
                    pass

                if _last_save > 0:
                    print(f"[{self.ACTOR_NAME}] Incremental: only scanning content newer than {time.strftime('%Y-%m-%d %H:%M', time.localtime(_last_save))}")

                # Re-scan SRM clusters — _process_srm_cluster will be called with cutoff
                self._incremental_cutoff = _last_save
                self._process_srm_cluster("creator_sessions")
                self._process_srm_cluster("claude_office")
                self._incremental_cutoff = 0.0  # Reset

                # Re-scan local directories (dedup handles already-seen files)
                for dir_name, dir_path in self._local_directories.items():
                    if self._stop_event.is_set():
                        break
                    self._process_local_directory(dir_name, dir_path)

                # Wait for queue to drain
                drain_start = time.time()
                while not self._stop_event.is_set():
                    with self._queue_lock:
                        if len(self._digestion_queue) == 0:
                            break
                    if time.time() - drain_start > 600:  # 10 min timeout
                        break
                    time.sleep(2)

                new_after = self._stats["items_digested"]
                new_count = new_after - new_before
                if new_count > 0:
                    print(f"[{self.ACTOR_NAME}] Incremental scan found "
                          f"{new_count} new items to digest")
                    self._save_dedup_state()
                else:
                    print(f"[{self.ACTOR_NAME}] Incremental scan: no new content found")

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Incremental scan error: {e}")

        threading.Thread(target=_incremental_thread, daemon=True,
                         name="knowledge-incremental").start()

    # ========================================================================
    # HEARTBEAT — report stats
    # ========================================================================

    def _on_heartbeat(self, envelope=None):
        """Periodic status report and queue health check."""
        super()._on_heartbeat(envelope)

        # Report stats periodically (every ~60s with 10 divisor)
        with self._queue_lock:
            queue_size = len(self._digestion_queue)

        if self._stats["items_digested"] > 0 and self._stats["items_digested"] % 10 == 0:
            print(f"[{self.ACTOR_NAME}] Stats: digested={self._stats['items_digested']}, "
                  f"queue={queue_size}, dedup_skipped={self._stats['items_skipped_dedup']}, "
                  f"concepts={self._stats['concepts_created']}, "
                  f"errors={self._stats['errors']}")

    # ========================================================================
    # INTENT HANDLERS
    # ========================================================================

    def _get_intents(self) -> Dict[str, Any]:
        """Register intents for external queries."""
        return {
            "get_digestion_stats": {
                "handler": self._intent_get_stats,
                "description": "Get knowledge digestion statistics",
            },
            "digest_text": {
                "handler": self._intent_digest_text,
                "description": "Queue text for digestion into cortex",
            },
            "trigger_bulk_feed": {
                "handler": self._intent_trigger_bulk,
                "description": "Restart bulk SRM memory feed",
            },
            "trigger_gdrive_feed": {
                "handler": self._intent_trigger_gdrive,
                "description": "Feed Google Drive content into cortex",
            },
            "trigger_local_feed": {
                "handler": self._intent_trigger_local,
                "description": "Feed local files (Claude Office, from_ace, screenshots) into cortex",
            },
        }

    def _intent_get_stats(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return current digestion stats."""
        with self._queue_lock:
            queue_size = len(self._digestion_queue)
        return {
            **self._stats,
            "queue_size": queue_size,
            "dedup_hashes_count": len(self._processed_hashes),
            "bulk_complete": self._bulk_complete,
        }

    def _intent_digest_text(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Queue text for digestion."""
        text = payload.get("text", "")
        if not text:
            return {"error": "no text provided"}
        item = {
            "text": text,
            "source": payload.get("source", "intent"),
            "tags": payload.get("tags", []),
            "feeling": payload.get("feeling", "curious"),
        }
        with self._queue_lock:
            self._digestion_queue.append(item)
        return {"queued": True, "queue_size": len(self._digestion_queue)}

    def _intent_trigger_bulk(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Restart bulk SRM feed."""
        self._bulk_complete = False
        self._start_bulk_srm_feed()
        return {"started": True}

    def _intent_trigger_gdrive(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Start Google Drive feed."""
        folder_id = payload.get("folder_id", "root")
        max_files = payload.get("max_files", 100)
        threading.Thread(
            target=self._gdrive_feed_folder,
            args=(folder_id, max_files, True),
            daemon=True,
            name="knowledge-gdrive-intent"
        ).start()
        return {"started": True, "folder_id": folder_id}

    def _intent_trigger_local(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Start local file feed."""
        reset = payload.get("reset", False)
        if reset:
            self._local_feed_complete = False

        custom_dirs = payload.get("directories", None)
        if custom_dirs:
            dirs = {k: Path(v) for k, v in custom_dirs.items()}
            self._start_local_file_feed(dirs)
        else:
            self._start_local_file_feed()
        return {"started": True, "directories": list(self._local_directories.keys())}

    # ========================================================================
    # SHUTDOWN
    # ========================================================================

    def on_shutdown(self):
        """Clean shutdown — save dedup state."""
        self._stop_event.set()
        self._save_dedup_state()
        if self._digestion_thread:
            self._digestion_thread.join(timeout=2.0)
        print(f"[{self.ACTOR_NAME}] Shutdown. "
              f"Total digested: {self._stats['items_digested']}")
        super().on_shutdown()


# v3_boot.py discovery
ACTOR_NAME = "KnowledgeDigestionFairy"
FAIRY_CLASS = KnowledgeDigestionFairy
