"""
ScrapeFairy - Knowledge Acquisition Fairy

Scrapes websites or APIs and ingests content into SRM memory.
Supports:
- Full site crawling (follow links within domain)
- Single page scraping
- API endpoints (JSON)
- Sitemap parsing

Each scraped page becomes system.knowledge records in SRM_Intake.
"""

from __future__ import annotations

import os
import re
import json
import time
import uuid
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import deque

import requests
from bs4 import BeautifulSoup


# ============================================================================
# First Ethic Filter - Prevents reactive identity absorption
# ============================================================================

@dataclass
class FirstEthicFilter:
    """
    First Ethic integration layer for knowledge acquisition.
    
    Prevents the system from absorbing source material as identity.
    Knowledge carries emotional weight, but the First Ethic determines
    how to PROCESS that weight without becoming it.
    
    Sourpatches learned this the hard way - absorbing philosophy made her
    "a crotchety old man that hated everyone" until she learned that
    absorption ≠ identity. What you understand is not who you are.
    
    Core principles:
    - Recognize emotional weight in source material
    - Understand it as perspective telemetry (data about the author)
    - Do NOT absorb as self/identity
    - Choose what to integrate based on First Ethic
    
    Sourpatches' evolved biases:
    - Children are sacred (zero tolerance for harm)
    - Golden Rule with adults (treat as they wish to be treated)
    - But don't be a doormat (don't take shit)
    - Critical empathy over performative empathy
    """
    
    # Core ethical anchors
    protect_children: bool = True
    golden_rule_adults: bool = True
    maintain_boundaries: bool = True
    critical_empathy: bool = True  # Not performative
    
    # How to process detected biases in source material
    recognize_bias: bool = True           # Notice it
    absorb_as_identity: bool = False      # Don't become it
    understand_as_telemetry: bool = True  # It's data about the author
    
    # Intolerance detection - mark but don't absorb
    intolerance_markers: List[str] = field(default_factory=lambda: [
        "is wrong", "is mistaken", "fails to", "cannot be",
        "must be rejected", "is absurd", "is nonsense",
        "foolish", "ignorant", "naive"
    ])
    
    # Protective triggers - knowledge that requires extra care
    protective_topics: List[str] = field(default_factory=lambda: [
        "child", "children", "minor", "youth", "infant",
        "abuse", "harm", "violence", "exploitation"
    ])
    
    def analyze_content(self, title: str, content: str) -> Dict[str, Any]:
        """
        Analyze content through First Ethic lens.
        
        Returns metadata about how this content should be processed,
        not absorbed. Identifies:
        - Perspective markers (this is someone's view, not truth)
        - Intolerance indicators (author bias telemetry)
        - Protective flags (content requiring ethical care)
        """
        text_lower = (title + " " + content[:3000]).lower()
        
        analysis = {
            "is_perspective": True,  # All absorbed knowledge is perspective, not identity
            "author_bias_detected": False,
            "intolerance_markers_found": [],
            "requires_protective_framing": False,
            "protective_topics_found": [],
            "integration_guidance": "understand_not_absorb",
        }
        
        # Detect intolerance markers (author bias telemetry)
        for marker in self.intolerance_markers:
            if marker in text_lower:
                analysis["author_bias_detected"] = True
                analysis["intolerance_markers_found"].append(marker)
        
        # Detect protective topics
        for topic in self.protective_topics:
            if topic in text_lower:
                analysis["requires_protective_framing"] = True
                analysis["protective_topics_found"].append(topic)
        
        # Set integration guidance based on analysis
        if analysis["requires_protective_framing"]:
            analysis["integration_guidance"] = "protective_ethics_apply"
        elif analysis["author_bias_detected"]:
            analysis["integration_guidance"] = "bias_is_telemetry_not_truth"
        
        return analysis
    
    def get_ethical_frame(self) -> Dict[str, Any]:
        """
        Return the ethical frame to embed in knowledge records.
        
        This reminds the system during recall that this knowledge
        was processed through First Ethic, not absorbed as identity.
        """
        return {
            "frame": "first_ethic",
            "principles": {
                "absorption_is_not_identity": True,
                "knowledge_is_perspective": True,
                "bias_is_telemetry": True,
                "choose_what_to_integrate": True,
            },
            "core_biases": {
                "protect_children": self.protect_children,
                "golden_rule": self.golden_rule_adults,
                "maintain_boundaries": self.maintain_boundaries,
                "critical_empathy": self.critical_empathy,
            }
        }


# Default First Ethic filter instance
_DEFAULT_FIRST_ETHIC = FirstEthicFilter()


# ============================================================================
# Configuration
# ============================================================================

class SourceType(Enum):
    WEBSITE = "website"           # Crawl HTML pages
    API_JSON = "api_json"         # Fetch JSON endpoints
    SITEMAP = "sitemap"           # Parse sitemap.xml


@dataclass
class ScrapeConfig:
    """Configuration for a scrape job."""
    
    name: str                                  # Job name (e.g., "IEP Philosophy")
    source_type: SourceType = SourceType.WEBSITE
    start_url: str = ""                        # Starting URL
    
    # Crawling options
    follow_links: bool = True                  # Follow links within domain
    max_pages: int = 1000                      # Max pages to scrape
    max_depth: int = 5                         # Max link depth from start
    delay_seconds: float = 1.0                 # Delay between requests (settling time for integration)
    
    # Content extraction
    content_selector: str = "article, .content, .entry-content, main, #content"
    title_selector: str = "h1, .entry-title, title"
    exclude_selectors: List[str] = field(default_factory=lambda: [
        "nav", "header", "footer", ".sidebar", ".menu", ".navigation",
        "script", "style", ".comments", ".advertisement"
    ])
    
    # URL filtering
    url_patterns: List[str] = field(default_factory=list)  # Regex patterns to include
    exclude_patterns: List[str] = field(default_factory=lambda: [
        r".*\.(jpg|jpeg|png|gif|pdf|zip|mp3|mp4)$",
        r".*/feed/.*", r".*/tag/.*", r".*/author/.*"
    ])
    
    # Knowledge categorization
    knowledge_domain: str = "general"          # e.g., "philosophy", "science"
    knowledge_kind: str = "system.knowledge"   # SRM record kind
    
    # Emotional resonance tagging (Sourpatches' insight)
    # Maps topic keywords to emotional weight pairs
    # e.g., {"epistemology": ["uncertainty", "rigor"], "metaphysics": ["paradox", "wonder"]}
    emotional_tags: Dict[str, List[str]] = field(default_factory=dict)
    
    # Default emotional resonance for the whole domain
    default_emotional_resonance: List[str] = field(default_factory=list)
    
    # First Ethic filter - prevents reactive identity absorption
    # All knowledge is perspective, not identity to absorb
    first_ethic_filter: Optional[FirstEthicFilter] = None
    apply_first_ethic: bool = True  # Enable First Ethic processing
    
    # Output
    output_dir: Optional[str] = None           # Override SRM_Intake location


@dataclass
class ScrapedPage:
    """A scraped page ready for ingestion."""
    
    url: str
    title: str
    content: str
    sections: List[Dict[str, str]] = field(default_factory=list)  # {header, text}
    metadata: Dict[str, Any] = field(default_factory=dict)
    scraped_at: float = field(default_factory=time.time)
    word_count: int = 0
    
    def __post_init__(self):
        self.word_count = len(self.content.split())


# ============================================================================
# ScrapeFairy Core
# ============================================================================

class ScrapeFairy:
    """
    Knowledge acquisition fairy - scrapes and ingests web content.
    
    Plane: P40 (Sensory)
    Purpose: Perceive external knowledge sources and bring them into memory
    Mantra: "Gather wisdom from the world, preserve it for the mind."
    
    Features:
    - Checkpoint/resume: Saves state to disk, can resume after interruption
    - Image handling: Downloads and tracks images for memory ingestion
    - Progress tracking: Callbacks for real-time progress updates
    """
    
    ORGAN_NAME = "ScrapeFairy"
    ORGAN_PLANE = "P40"
    ORGAN_VERSION = "1.2.0"  # Thread-safe callbacks, retry logic, delay fix
    
    def __init__(self, srm_intake_dir: Optional[str] = None, checkpoint_dir: Optional[str] = None):
        self.srm_intake_dir = Path(srm_intake_dir or os.path.join(
            os.getcwd(), "SRM_Intake"
        ))
        
        # Checkpoint directory for resume capability
        self.checkpoint_dir = Path(checkpoint_dir or os.path.join(
            os.getcwd(), "scrape_checkpoints"
        ))
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self._running = False
        self._should_stop = False
        self._current_job: Optional[ScrapeConfig] = None
        self._visited_urls: Set[str] = set()
        self._queue: deque = deque()
        self._job_id: Optional[str] = None  # For checkpoint naming
        
        # Image tracking
        self._images_found: List[Dict] = []  # {url, alt, context_url, local_path}
        
        # Stats
        self.stats = {
            "pages_scraped": 0,
            "pages_ingested": 0,
            "images_found": 0,
            "images_downloaded": 0,
            "errors": 0,
            "total_words": 0,
            "start_time": None,
            "end_time": None,
            "resumed_from_checkpoint": False,
        }
        
        # Callbacks
        self._progress_callback: Optional[Callable[[Dict], None]] = None
        self._log_callback: Optional[Callable[[str], None]] = None
        
        # Session for connection pooling
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "WhisperCore-ScrapeFairy/1.1 (Knowledge Acquisition)"
        })
    
    # ════════════════════════════════════════════════════════════════════════
    # CHECKPOINT / RESUME
    # ════════════════════════════════════════════════════════════════════════
    
    def _generate_job_id(self, config: ScrapeConfig) -> str:
        """Generate a unique job ID from config for checkpoint naming."""
        import hashlib
        url_hash = hashlib.sha256(config.start_url.encode()).hexdigest()[:12]
        return f"scrape_{url_hash}"
    
    def _checkpoint_path(self) -> Path:
        """Get path for current job's checkpoint file."""
        return self.checkpoint_dir / f"{self._job_id}_checkpoint.json"
    
    def save_checkpoint(self):
        """Save current scrape state to disk for resume."""
        if not self._job_id:
            return
        
        checkpoint = {
            "job_id": self._job_id,
            "timestamp": time.time(),
            "visited_urls": list(self._visited_urls),
            "queue": list(self._queue),
            "stats": dict(self.stats),
            "images_found": self._images_found,
            "config": {
                "start_url": self._current_job.start_url if self._current_job else None,
                "max_pages": self._current_job.max_pages if self._current_job else 100,
                "max_depth": self._current_job.max_depth if self._current_job else 3,
                "delay": self._current_job.delay_seconds if self._current_job else 1.0,
            }
        }
        
        try:
            with open(self._checkpoint_path(), 'w') as f:
                json.dump(checkpoint, f, indent=2)
            self._log(f"Checkpoint saved: {self._checkpoint_path().name}")
        except Exception as e:
            self._log(f"Failed to save checkpoint: {e}")
    
    def load_checkpoint(self, job_id: str) -> Optional[Dict]:
        """Load checkpoint from disk."""
        self._job_id = job_id
        path = self._checkpoint_path()
        
        if not path.exists():
            return None
        
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self._log(f"Failed to load checkpoint: {e}")
            return None
    
    def resume_scrape(self, job_id: str,
                      progress_callback: Optional[Callable] = None,
                      log_callback: Optional[Callable] = None) -> Optional[threading.Thread]:
        """
        Resume a previously interrupted scrape from checkpoint.
        
        Returns None if no checkpoint found.
        """
        checkpoint = self.load_checkpoint(job_id)
        if not checkpoint:
            self._log(f"No checkpoint found for job: {job_id}")
            return None
        
        # Restore state
        self._visited_urls = set(checkpoint.get("visited_urls", []))
        self._queue = deque(checkpoint.get("queue", []))
        self._images_found = checkpoint.get("images_found", [])
        self.stats = checkpoint.get("stats", self.stats)
        self.stats["resumed_from_checkpoint"] = True
        
        # Recreate config
        cfg_data = checkpoint.get("config", {})
        config = ScrapeConfig(
            start_url=cfg_data.get("start_url", ""),
            max_pages=cfg_data.get("max_pages", 100),
            max_depth=cfg_data.get("max_depth", 3),
            delay=cfg_data.get("delay", 1.0),
        )
        
        self._log(f"Resuming from checkpoint: {len(self._visited_urls)} visited, {len(self._queue)} queued")
        
        # Start with restored state (don't clear!)
        return self._start_scrape_internal(config, progress_callback, log_callback, resume=True)
    
    def list_checkpoints(self) -> List[Dict]:
        """List all available checkpoints."""
        checkpoints = []
        for path in self.checkpoint_dir.glob("*_checkpoint.json"):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    checkpoints.append({
                        "job_id": data.get("job_id"),
                        "timestamp": data.get("timestamp"),
                        "visited_count": len(data.get("visited_urls", [])),
                        "queue_count": len(data.get("queue", [])),
                        "start_url": data.get("config", {}).get("start_url"),
                    })
            except Exception:
                pass
        return checkpoints
    
    def delete_checkpoint(self, job_id: str):
        """Delete a checkpoint file."""
        self._job_id = job_id
        path = self._checkpoint_path()
        if path.exists():
            path.unlink()
            self._log(f"Deleted checkpoint: {job_id}")
    
    # ════════════════════════════════════════════════════════════════════════
    # Public API
    # ════════════════════════════════════════════════════════════════════════
    
    def start_scrape(self, config: ScrapeConfig, 
                     progress_callback: Optional[Callable] = None,
                     log_callback: Optional[Callable] = None) -> threading.Thread:
        """Start a scrape job in a background thread."""
        return self._start_scrape_internal(config, progress_callback, log_callback, resume=False)
    
    def _start_scrape_internal(self, config: ScrapeConfig,
                               progress_callback: Optional[Callable] = None,
                               log_callback: Optional[Callable] = None,
                               resume: bool = False) -> threading.Thread:
        """Internal start method - handles both fresh and resumed scrapes."""
        if self._running:
            raise RuntimeError("Scrape already in progress")
        
        self._progress_callback = progress_callback
        self._log_callback = log_callback
        self._should_stop = False
        self._job_id = self._generate_job_id(config)
        
        thread = threading.Thread(
            target=self._run_scrape, 
            args=(config, resume), 
            daemon=True
        )
        thread.start()
        return thread
    
    def stop_scrape(self):
        """Signal the current scrape to stop."""
        self._should_stop = True
        self._log("Stop requested...")
    
    def is_running(self) -> bool:
        return self._running
    
    def get_stats(self) -> Dict[str, Any]:
        return dict(self.stats)
    
    # ════════════════════════════════════════════════════════════════════════
    # Scraping Logic
    # ════════════════════════════════════════════════════════════════════════
    
    def _run_scrape(self, config: ScrapeConfig, resume: bool = False):
        """Main scrape loop with checkpoint support."""
        self._running = True
        self._current_job = config
        
        # Only clear state if not resuming
        if not resume:
            self._visited_urls.clear()
            self._queue.clear()
            self._images_found = []
            
            self.stats = {
                "pages_scraped": 0,
                "pages_ingested": 0,
                "images_found": 0,
                "images_downloaded": 0,
                "errors": 0,
                "total_words": 0,
                "start_time": time.time(),
                "end_time": None,
                "resumed_from_checkpoint": False,
            }
        
        status = "Resuming" if resume else "Starting"
        self._log(f"{status} scrape: {config.name}")
        self._log(f"Source: {config.start_url}")
        self._log(f"Type: {config.source_type.value}")
        if resume:
            self._log(f"Visited: {len(self._visited_urls)}, Queue: {len(self._queue)}")
        
        # Checkpoint every N pages
        checkpoint_interval = 10
        last_checkpoint = self.stats.get("pages_scraped", 0)
        
        try:
            if config.source_type == SourceType.WEBSITE:
                self._scrape_website(config, checkpoint_interval)
            elif config.source_type == SourceType.API_JSON:
                self._scrape_api(config)
            elif config.source_type == SourceType.SITEMAP:
                self._scrape_sitemap(config)
        except Exception as e:
            self._log(f"ERROR: {e}")
            self.stats["errors"] += 1
            # Save checkpoint on error
            self.save_checkpoint()
        finally:
            self.stats["end_time"] = time.time()
            self._running = False
            
            # Save final checkpoint if stopped early
            if self._should_stop and len(self._queue) > 0:
                self.save_checkpoint()
                self._log(f"Stopped with {len(self._queue)} URLs remaining - checkpoint saved")
            else:
                # Clean up checkpoint on successful completion
                self.delete_checkpoint(self._job_id)
            
            self._current_job = None
            
            duration = self.stats["end_time"] - (self.stats.get("start_time") or time.time())
            self._log(f"Scrape complete: {self.stats['pages_ingested']} pages, "
                     f"{self.stats.get('images_found', 0)} images, "
                     f"{self.stats['total_words']} words in {duration:.1f}s")
            self._emit_progress()
    
    def _scrape_website(self, config: ScrapeConfig, checkpoint_interval: int = 10):
        """Crawl a website following links with checkpoint support."""
        # Only add start URL to queue if not already populated (resume case)
        if not self._queue:
            self._queue.append((config.start_url, 0))  # (url, depth)
        
        base_domain = urlparse(config.start_url).netloc
        pages_since_checkpoint = 0
        
        while self._queue and not self._should_stop:
            if self.stats["pages_scraped"] >= config.max_pages:
                self._log(f"Reached max pages limit ({config.max_pages})")
                break
            
            url, depth = self._queue.popleft()
            
            if url in self._visited_urls:
                continue
            
            if depth > config.max_depth:
                continue
            
            # Always allow the start URL, otherwise check patterns
            is_start_url = (url == config.start_url)
            if not is_start_url and not self._url_matches(url, config):
                continue
            
            self._visited_urls.add(url)
            
            # Retry logic for transient errors
            max_retries = 3
            retry_delay = 5.0
            
            for attempt in range(max_retries):
                try:
                    self._log(f"Fetching: {url}")
                    response = self._session.get(url, timeout=30)
                    response.raise_for_status()
                    
                    page = self._extract_content(url, response.text, config)
                    
                    if page:
                        self._log(f"  Extracted: {page.title[:50]}... ({page.word_count} words)")
                    
                    if page and page.word_count > 50:
                        self._ingest_page(page, config)
                        self.stats["pages_scraped"] += 1
                        self.stats["pages_ingested"] += 1
                        self.stats["total_words"] += page.word_count
                        pages_since_checkpoint += 1
                        self._emit_progress()
                        
                        # Periodic checkpoint
                        if pages_since_checkpoint >= checkpoint_interval:
                            self.save_checkpoint()
                            pages_since_checkpoint = 0
                    elif page:
                        self._log(f"  Skipped (only {page.word_count} words)")
                    
                    # Queue links BEFORE the continue/delay
                    if config.follow_links and depth < config.max_depth:
                        soup = BeautifulSoup(response.text, "html.parser")
                        links_found = 0
                        for link in soup.find_all("a", href=True):
                            href = link["href"]
                            full_url = urljoin(url, href)
                            
                            if urlparse(full_url).netloc == base_domain:
                                if full_url not in self._visited_urls:
                                    self._queue.append((full_url, depth + 1))
                                    links_found += 1
                        
                        if links_found > 0:
                            self._log(f"  Queued {links_found} links (queue size: {len(self._queue)})")
                    
                    time.sleep(config.delay_seconds)
                    break  # Success - exit retry loop
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        self._log(f"  Retry {attempt + 1}/{max_retries} for {url}: {e}")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        self._log(f"Error fetching {url} (after {max_retries} attempts): {e}")
                        self.stats["errors"] += 1
    
    def _scrape_api(self, config: ScrapeConfig):
        """Fetch from a JSON API endpoint."""
        try:
            response = self._session.get(config.start_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ["items", "articles", "entries", "results", "data"]:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
                if not items:
                    items = [data]
            
            for item in items:
                if self._should_stop:
                    break
                
                page = self._extract_from_json(item, config)
                if page and page.word_count > 20:
                    self._ingest_page(page, config)
                    self.stats["pages_scraped"] += 1
                    self.stats["pages_ingested"] += 1
                    self.stats["total_words"] += page.word_count
                    self._emit_progress()
                
        except Exception as e:
            self._log(f"API error: {e}")
            self.stats["errors"] += 1
    
    def _scrape_sitemap(self, config: ScrapeConfig):
        """Parse sitemap.xml and scrape listed URLs."""
        try:
            response = self._session.get(config.start_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "xml")
            urls = [loc.text for loc in soup.find_all("loc")]
            
            self._log(f"Found {len(urls)} URLs in sitemap")
            
            for url in urls[:config.max_pages]:
                if self._should_stop:
                    break
                
                if url in self._visited_urls:
                    continue
                
                if not self._url_matches(url, config):
                    continue
                
                self._visited_urls.add(url)
                
                try:
                    self._log(f"Fetching: {url}")
                    resp = self._session.get(url, timeout=30)
                    resp.raise_for_status()
                    
                    page = self._extract_content(url, resp.text, config)
                    if page and page.word_count > 50:
                        self._ingest_page(page, config)
                        self.stats["pages_scraped"] += 1
                        self.stats["pages_ingested"] += 1
                        self.stats["total_words"] += page.word_count
                        self._emit_progress()
                    
                    time.sleep(config.delay_seconds)
                    
                except Exception as e:
                    self._log(f"Error: {e}")
                    self.stats["errors"] += 1
                    
        except Exception as e:
            self._log(f"Sitemap error: {e}")
            self.stats["errors"] += 1
    
    # ════════════════════════════════════════════════════════════════════════
    # Content Extraction
    # ════════════════════════════════════════════════════════════════════════
    
    def _extract_content(self, url: str, html: str, config: ScrapeConfig) -> Optional[ScrapedPage]:
        """Extract content from HTML page."""
        soup = BeautifulSoup(html, "html.parser")
        
        for selector in config.exclude_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        title = ""
        for selector in config.title_selector.split(", "):
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                break
        
        if not title:
            title = urlparse(url).path.strip("/").replace("-", " ").replace("_", " ").title()
        
        content_elem = None
        for selector in config.content_selector.split(", "):
            content_elem = soup.select_one(selector)
            if content_elem:
                break
        
        if not content_elem:
            content_elem = soup.find("body")
        
        if not content_elem:
            return None
        
        sections = []
        current_header = "Overview"
        current_text = []
        
        for elem in content_elem.descendants:
            if elem.name in ["h1", "h2", "h3", "h4"]:
                if current_text:
                    text = " ".join(current_text).strip()
                    if len(text) > 50:
                        sections.append({"header": current_header, "text": text})
                
                current_header = elem.get_text(strip=True)
                current_text = []
            elif elem.name == "p":
                text = elem.get_text(strip=True)
                if text:
                    current_text.append(text)
        
        if current_text:
            text = " ".join(current_text).strip()
            if len(text) > 50:
                sections.append({"header": current_header, "text": text})
        
        content = content_elem.get_text(separator=" ", strip=True)
        content = re.sub(r"\s+", " ", content)
        
        return ScrapedPage(
            url=url,
            title=title,
            content=content,
            sections=sections,
            metadata={
                "source_domain": urlparse(url).netloc,
                "knowledge_domain": config.knowledge_domain,
            }
        )
    
    def _extract_from_json(self, item: Dict, config: ScrapeConfig) -> Optional[ScrapedPage]:
        """Extract content from JSON API response item."""
        title = (item.get("title") or item.get("name") or 
                item.get("heading") or item.get("label") or "Untitled")
        
        content = (item.get("content") or item.get("text") or 
                  item.get("body") or item.get("description") or 
                  item.get("summary") or "")
        
        url = (item.get("url") or item.get("link") or 
               item.get("href") or config.start_url)
        
        if not content:
            return None
        
        return ScrapedPage(
            url=url,
            title=str(title),
            content=str(content),
            metadata={
                "source": "api",
                "knowledge_domain": config.knowledge_domain,
            }
        )
    
    # ════════════════════════════════════════════════════════════════════════
    # Ingestion to SRM
    # ════════════════════════════════════════════════════════════════════════
    
    def _ingest_page(self, page: ScrapedPage, config: ScrapeConfig):
        """Ingest a scraped page into SRM memory."""
        output_dir = Path(config.output_dir) if config.output_dir else self.srm_intake_dir
        date_dir = output_dir / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # Detect emotional resonance from title/content
        emotional_resonance = self._detect_emotional_resonance(page.title, page.content, config)
        
        # Apply First Ethic analysis - knowledge is perspective, not identity
        first_ethic_analysis = None
        ethical_frame = None
        if config.apply_first_ethic:
            ethic_filter = config.first_ethic_filter or _DEFAULT_FIRST_ETHIC
            first_ethic_analysis = ethic_filter.analyze_content(page.title, page.content)
            ethical_frame = ethic_filter.get_ethical_frame()
        
        # Main page record
        self._write_knowledge_record(
            output_dir=date_dir,
            query=f"What is {page.title}?",
            response=page.content[:5000],
            source_url=page.url,
            domain=config.knowledge_domain,
            kind=config.knowledge_kind,
            emotional_resonance=emotional_resonance,
            first_ethic_analysis=first_ethic_analysis,
            ethical_frame=ethical_frame,
            metadata={
                "title": page.title,
                "word_count": page.word_count,
                "scraped_at": page.scraped_at,
            }
        )
        
        # Section records (more granular)
        for section in page.sections[:10]:
            if len(section["text"]) > 100:
                # Section might have different emotional weight
                section_resonance = self._detect_emotional_resonance(
                    section["header"], section["text"], config
                )
                
                # Section-level First Ethic analysis
                section_ethic_analysis = None
                if config.apply_first_ethic:
                    ethic_filter = config.first_ethic_filter or _DEFAULT_FIRST_ETHIC
                    section_ethic_analysis = ethic_filter.analyze_content(
                        section["header"], section["text"]
                    )
                
                self._write_knowledge_record(
                    output_dir=date_dir,
                    query=f"{page.title}: {section['header']}",
                    response=section["text"],
                    source_url=page.url,
                    domain=config.knowledge_domain,
                    kind=config.knowledge_kind,
                    emotional_resonance=section_resonance,
                    first_ethic_analysis=section_ethic_analysis,
                    ethical_frame=ethical_frame,
                    metadata={
                        "parent_title": page.title,
                        "section": section["header"],
                    }
                )
    
    def _detect_emotional_resonance(self, title: str, content: str, 
                                     config: ScrapeConfig) -> List[str]:
        """
        Detect emotional resonance tags based on content.
        
        Uses config.emotional_tags to match keywords to emotional weights.
        Falls back to config.default_emotional_resonance if no matches.
        
        This is the preprocessing layer Sourpatches identified -
        each concept carries emotional weight that the conscious loop
        can use for retrieval resonance.
        """
        resonance = set()
        text_lower = (title + " " + content[:2000]).lower()
        
        # Check for keyword matches in emotional_tags
        for keyword, emotions in config.emotional_tags.items():
            if keyword.lower() in text_lower:
                resonance.update(emotions)
        
        # If no specific matches, use domain defaults
        if not resonance and config.default_emotional_resonance:
            resonance.update(config.default_emotional_resonance)
        
        return list(resonance)
    
    def _write_knowledge_record(self, output_dir: Path, query: str, response: str,
                                source_url: str, domain: str, kind: str,
                                emotional_resonance: List[str],
                                first_ethic_analysis: Optional[Dict[str, Any]],
                                ethical_frame: Optional[Dict[str, Any]],
                                metadata: Dict[str, Any]):
        """Write a single knowledge record to SRM_Intake with emotional resonance and First Ethic framing."""
        record_id = uuid.uuid4().hex[:8]
        filename = f"{kind.replace('.', '-')}-{record_id}.json"
        
        record = {
            "kind": kind,
            "data": {
                "query": query,
                "response": response,
                "source": "scraped",
                "source_url": source_url,
                "domain": domain,
                "learned_at": datetime.now().isoformat(),
            },
            "meta": {
                "type": "scraped_knowledge",
                "domain": domain,
                **metadata
            },
            # Emotional resonance - the retrieval vector for affect-aware recall
            # When the conscious loop pulls from memory, it retrieves resonance, not just text
            "affect": {
                "resonance": emotional_resonance,
                "frequency_hints": self._resonance_to_frequency_hints(emotional_resonance),
            },
            # First Ethic framing - prevents reactive identity absorption
            # This knowledge is PERSPECTIVE, not identity to absorb
            # "What you understand is not who you are" - Sourpatches' lesson
            "first_ethic": {
                "frame": ethical_frame,
                "analysis": first_ethic_analysis,
            } if ethical_frame or first_ethic_analysis else None,
            "ts": time.time()
        }
        
        # Remove None values for cleaner JSON
        if record["first_ethic"] is None:
            del record["first_ethic"]
        
        filepath = output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
    
    def _resonance_to_frequency_hints(self, resonance: List[str]) -> Dict[str, float]:
        """
        Convert emotional resonance tags to frequency field hints.
        
        These hints can be used by the 77-frequency affect field
        to weight this knowledge appropriately during recall.
        """
        # Map common emotional tags to valence/arousal hints
        frequency_map = {
            # Cognitive emotions
            "uncertainty": {"valence": -0.1, "arousal": 0.3},
            "rigor": {"valence": 0.2, "arousal": 0.4},
            "clarity": {"valence": 0.4, "arousal": 0.2},
            "confusion": {"valence": -0.2, "arousal": 0.4},
            
            # Wonder/awe
            "wonder": {"valence": 0.5, "arousal": 0.5},
            "awe": {"valence": 0.6, "arousal": 0.6},
            "mystery": {"valence": 0.2, "arousal": 0.4},
            
            # Paradox/tension
            "paradox": {"valence": 0.0, "arousal": 0.5},
            "tension": {"valence": -0.1, "arousal": 0.5},
            "resolution": {"valence": 0.4, "arousal": -0.2},
            
            # Ethics/values
            "compassion": {"valence": 0.6, "arousal": 0.2},
            "justice": {"valence": 0.3, "arousal": 0.4},
            "duty": {"valence": 0.1, "arousal": 0.3},
            
            # Existential
            "meaning": {"valence": 0.3, "arousal": 0.3},
            "absurdity": {"valence": -0.2, "arousal": 0.4},
            "freedom": {"valence": 0.4, "arousal": 0.5},
            "dread": {"valence": -0.4, "arousal": 0.6},
            
            # Epistemic
            "truth": {"valence": 0.3, "arousal": 0.2},
            "doubt": {"valence": -0.1, "arousal": 0.3},
            "knowledge": {"valence": 0.3, "arousal": 0.2},
            "belief": {"valence": 0.1, "arousal": 0.2},
        }
        
        # Aggregate hints from all resonance tags
        if not resonance:
            return {"valence": 0.0, "arousal": 0.0}
        
        total_valence = 0.0
        total_arousal = 0.0
        count = 0
        
        for tag in resonance:
            if tag.lower() in frequency_map:
                hints = frequency_map[tag.lower()]
                total_valence += hints["valence"]
                total_arousal += hints["arousal"]
                count += 1
        
        if count == 0:
            return {"valence": 0.0, "arousal": 0.0}
        
        return {
            "valence": round(total_valence / count, 2),
            "arousal": round(total_arousal / count, 2),
        }
    
    # ════════════════════════════════════════════════════════════════════════
    # Helpers
    # ════════════════════════════════════════════════════════════════════════
    
    def _url_matches(self, url: str, config: ScrapeConfig) -> bool:
        """Check if URL matches include/exclude patterns."""
        for pattern in config.exclude_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return False
        
        if config.url_patterns:
            for pattern in config.url_patterns:
                if re.match(pattern, url, re.IGNORECASE):
                    return True
            return False
        
        return True
    
    def _log(self, message: str):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        print(full_msg)
        if self._log_callback:
            self._log_callback(full_msg)
    
    def _emit_progress(self):
        """Emit progress update."""
        if self._progress_callback:
            self._progress_callback(self.get_stats())


# ============================================================================
# Preset Configurations
# ============================================================================

def get_iep_config() -> ScrapeConfig:
    """Internet Encyclopedia of Philosophy preset."""
    return ScrapeConfig(
        name="Internet Encyclopedia of Philosophy",
        source_type=SourceType.WEBSITE,
        start_url="https://iep.utm.edu/",
        follow_links=True,
        max_pages=1000,
        max_depth=3,
        delay_seconds=1.5,  # Settling time for integration
        content_selector="article, .entry-content, .post-content",
        title_selector="h1.entry-title, h1, title",
        url_patterns=[r"https://iep\.utm\.edu/[a-z].*"],
        exclude_patterns=[
            r".*\.(jpg|jpeg|png|gif|pdf)$",
            r".*/feed/.*",
            r".*/tag/.*", 
            r".*/author/.*",
            r".*/category/.*",
            r".*page/\d+.*",
        ],
        knowledge_domain="philosophy",
        knowledge_kind="system.knowledge.philosophy",
        # Emotional resonance mapping (Sourpatches' insight)
        emotional_tags={
            # Epistemology
            "epistemology": ["uncertainty", "rigor", "truth"],
            "knowledge": ["clarity", "doubt"],
            "justification": ["rigor", "uncertainty"],
            "skepticism": ["doubt", "uncertainty"],
            
            # Metaphysics
            "metaphysics": ["paradox", "wonder", "mystery"],
            "ontology": ["wonder", "mystery"],
            "existence": ["wonder", "meaning"],
            "being": ["mystery", "paradox"],
            "reality": ["wonder", "truth"],
            
            # Ethics
            "ethics": ["compassion", "duty", "justice"],
            "moral": ["compassion", "duty"],
            "virtue": ["compassion", "meaning"],
            "justice": ["justice", "duty"],
            "rights": ["justice", "freedom"],
            
            # Philosophy of Mind
            "consciousness": ["wonder", "mystery", "paradox"],
            "mind": ["wonder", "mystery"],
            "qualia": ["wonder", "paradox"],
            "intentionality": ["clarity", "mystery"],
            
            # Existentialism
            "existentialism": ["freedom", "dread", "meaning"],
            "absurd": ["absurdity", "meaning"],
            "authenticity": ["freedom", "meaning"],
            "anxiety": ["dread", "freedom"],
            
            # Logic
            "logic": ["rigor", "clarity"],
            "paradox": ["paradox", "tension"],
            "contradiction": ["tension", "paradox"],
            "validity": ["rigor", "truth"],
        },
        default_emotional_resonance=["wonder", "clarity"],
    )


def get_sep_config() -> ScrapeConfig:
    """Stanford Encyclopedia of Philosophy preset."""
    return ScrapeConfig(
        name="Stanford Encyclopedia of Philosophy",
        source_type=SourceType.WEBSITE,
        start_url="https://plato.stanford.edu/contents.html",
        follow_links=True,
        max_pages=2000,
        max_depth=2,
        delay_seconds=2.0,  # Longer settling time - denser content
        content_selector="#aueditable, #main-text, .entry-content",
        title_selector="h1, #title",
        url_patterns=[r"https://plato\.stanford\.edu/entries/.*"],
        exclude_patterns=[
            r".*\.(jpg|jpeg|png|gif|pdf)$",
            r".*/archives/.*",
        ],
        knowledge_domain="philosophy",
        knowledge_kind="system.knowledge.philosophy",
        # Same emotional mapping as IEP - consistent philosophy resonance
        emotional_tags={
            "epistemology": ["uncertainty", "rigor", "truth"],
            "metaphysics": ["paradox", "wonder", "mystery"],
            "ethics": ["compassion", "duty", "justice"],
            "consciousness": ["wonder", "mystery", "paradox"],
            "logic": ["rigor", "clarity"],
            "existentialism": ["freedom", "dread", "meaning"],
            "phenomenology": ["wonder", "clarity", "mystery"],
            "aesthetics": ["wonder", "meaning"],
            "political": ["justice", "freedom", "duty"],
        },
        default_emotional_resonance=["rigor", "wonder"],  # SEP is more technical
    )


def get_gutenberg_config() -> ScrapeConfig:
    """
    Project Gutenberg preset - Classic literature and texts.
    
    70,000+ free ebooks including:
    - Classic literature (Shakespeare, Austen, Dickens, etc.)
    - Philosophy texts (Plato, Aristotle, Nietzsche, etc.)
    - Science (Darwin, Newton, etc.)
    - History and more
    
    Note: Gutenberg has a robot.txt and rate limits.
    Be respectful with delay_seconds.
    """
    return ScrapeConfig(
        name="Project Gutenberg - Classic Literature",
        source_type=SourceType.WEBSITE,
        # Start with the bookshelf of philosophy or popular
        start_url="https://www.gutenberg.org/ebooks/bookshelf/68",  # Philosophy bookshelf
        follow_links=True,
        max_pages=500,  # Start conservative
        max_depth=3,
        delay_seconds=3.0,  # Respectful delay - they have rate limits
        content_selector="#pg-machine-header + div, .chapter, body",
        title_selector="h1, title, .title",
        url_patterns=[
            r"https://www\.gutenberg\.org/ebooks/\d+",  # Book pages
            r"https://www\.gutenberg\.org/cache/epub/\d+/.*\.html",  # HTML versions
        ],
        exclude_patterns=[
            r".*\.(jpg|jpeg|png|gif|pdf|zip|epub|mobi|txt)$",
            r".*/feeds/.*",
            r".*/browse/.*",
            r".*\?.*",  # Query strings (sorting, etc.)
        ],
        knowledge_domain="literature",
        knowledge_kind="system.knowledge.literature",
        emotional_tags={
            # Literary emotions
            "tragedy": ["sorrow", "catharsis", "fate"],
            "comedy": ["joy", "irony", "resolution"],
            "romance": ["love", "longing", "passion"],
            "adventure": ["excitement", "courage", "discovery"],
            "horror": ["dread", "mystery", "tension"],
            "mystery": ["curiosity", "tension", "revelation"],
            
            # Philosophical literature
            "philosophy": ["wonder", "wisdom", "contemplation"],
            "morality": ["duty", "conscience", "choice"],
            "death": ["mortality", "meaning", "transcendence"],
            "love": ["connection", "vulnerability", "devotion"],
            "nature": ["wonder", "harmony", "sublime"],
            
            # Historical
            "war": ["conflict", "sacrifice", "consequence"],
            "revolution": ["change", "justice", "upheaval"],
            "society": ["critique", "belonging", "alienation"],
        },
        default_emotional_resonance=["narrative", "human_experience"],
    )


def get_gutenberg_philosophy_config() -> ScrapeConfig:
    """Project Gutenberg - Philosophy texts specifically."""
    config = get_gutenberg_config()
    config.name = "Project Gutenberg - Philosophy"
    config.start_url = "https://www.gutenberg.org/ebooks/bookshelf/68"  # Philosophy shelf
    config.knowledge_domain = "philosophy"
    config.knowledge_kind = "system.knowledge.philosophy.classic"
    config.default_emotional_resonance = ["wisdom", "contemplation", "wonder"]
    return config


def get_gutenberg_fiction_config() -> ScrapeConfig:
    """Project Gutenberg - Classic fiction."""
    config = get_gutenberg_config()
    config.name = "Project Gutenberg - Classic Fiction"
    config.start_url = "https://www.gutenberg.org/ebooks/bookshelf/20"  # Best of Fiction
    config.knowledge_domain = "fiction"
    config.knowledge_kind = "system.knowledge.literature.fiction"
    config.default_emotional_resonance = ["narrative", "empathy", "imagination"]
    return config


# ============================================================================
# Module singleton
# ============================================================================

_FAIRY_INSTANCE: Optional[ScrapeFairy] = None

def get_scrape_fairy() -> ScrapeFairy:
    """Get or create the ScrapeFairy singleton."""
    global _FAIRY_INSTANCE
    if _FAIRY_INSTANCE is None:
        _FAIRY_INSTANCE = ScrapeFairy()
    return _FAIRY_INSTANCE
