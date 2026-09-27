"""
ScrapeFairy GUI v2.0 - Enhanced Knowledge Acquisition Interface

New Features:
- Completed source tracking with visual indicators
- Expanded knowledge sources (Chemistry, Engineering, Science, etc.)
- Multi-mind memory dashboard (Sour, Claude, System)
- Working/Short-term/Long-term memory breakdown
- Progress persistence across sessions
"""

from __future__ import annotations

import sys
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Handle both PyQt6 and PyQt5
try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox,
        QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
        QProgressBar, QTabWidget, QWidget, QListWidget, QListWidgetItem,
        QMessageBox, QFrame, QScrollArea, QSplitter, QToolButton
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
    from PyQt6.QtGui import QFont, QColor, QTextCursor, QIcon, QPalette
    _QT_VERSION = 6
    _FontBold = QFont.Weight.Bold
    _AlignCenter = Qt.AlignmentFlag.AlignCenter
    _AlignLeft = Qt.AlignmentFlag.AlignLeft
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox,
        QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
        QProgressBar, QTabWidget, QWidget, QListWidget, QListWidgetItem,
        QMessageBox, QFrame, QScrollArea, QSplitter, QToolButton
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
    from PyQt5.QtGui import QFont, QColor, QTextCursor, QIcon, QPalette
    _QT_VERSION = 5
    _FontBold = QFont.Bold
    _AlignCenter = Qt.AlignCenter
    _AlignLeft = Qt.AlignLeft

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fairies.P40_Sensory.scrape.scrape_fairy import (
    ScrapeFairy, ScrapeConfig, SourceType,
    get_scrape_fairy, get_iep_config, get_sep_config,
    get_gutenberg_config, get_gutenberg_philosophy_config, get_gutenberg_fiction_config
)


# ══════════════════════════════════════════════════════════════════════════════
# PATHS & STATE
# ══════════════════════════════════════════════════════════════════════════════

def _get_project_root() -> Path:
    current = Path(__file__).parent
    while current.parent != current:
        if (current / "SRM_Intake").exists():
            return current
        current = current.parent
    return Path.cwd()

PROJECT_ROOT = _get_project_root()
STATE_FILE = PROJECT_ROOT / "P40_Sensory" / "scrape" / "scrape_state.json"
SRM_INTAKE = PROJECT_ROOT / "SRM_Intake"


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE SOURCES DATABASE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class KnowledgeSourceDef:
    """Definition of a scrapeable knowledge source."""
    id: str
    name: str
    category: str
    description: str
    url: str
    estimated_pages: int = 0
    icon: str = ""
    api_available: bool = False
    python_package: str = ""
    rate_limit: float = 1.5
    requires_auth: bool = False
    
    def get_config(self) -> ScrapeConfig:
        """Get ScrapeConfig for this source."""
        source_type = SourceType.API_JSON if self.api_available else SourceType.WEBSITE
        return ScrapeConfig(
            name=self.name,
            source_type=source_type,
            start_url=self.url,
            delay_seconds=self.rate_limit,
            knowledge_domain=self.category,
            knowledge_kind=f"system.knowledge.{self.category}",
        )


# All knowledge sources organized by category
KNOWLEDGE_SOURCES: Dict[str, List[KnowledgeSourceDef]] = {
    "Philosophy": [
        KnowledgeSourceDef(
            id="iep", name="Internet Encyclopedia of Philosophy",
            category="philosophy", description="~900 peer-reviewed articles",
            url="https://iep.utm.edu/", estimated_pages=900, icon=""
        ),
        KnowledgeSourceDef(
            id="sep", name="Stanford Encyclopedia of Philosophy",
            category="philosophy", description="~1,774 academic articles",
            url="https://plato.stanford.edu/", estimated_pages=1774, icon=""
        ),
        KnowledgeSourceDef(
            id="gutenberg_philosophy", name="Gutenberg Philosophy",
            category="philosophy", description="Classic philosophy texts",
            url="https://www.gutenberg.org/ebooks/bookshelf/68",
            estimated_pages=500, icon="", rate_limit=3.0
        ),
        KnowledgeSourceDef(
            id="philosophers_api", name="Philosophers API",
            category="philosophy", description="Structured philosopher data",
            url="https://philosophersapi.com/api/philosophers",
            api_available=True, icon=""
        ),
    ],
    "Chemistry": [
        KnowledgeSourceDef(
            id="pubchem", name="PubChem",
            category="chemistry", description="111M+ molecular structures",
            url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/",
            estimated_pages=111000000, icon="",
            api_available=True, python_package="pubchempy", rate_limit=0.2
        ),
        KnowledgeSourceDef(
            id="nist_webbook", name="NIST Chemistry WebBook",
            category="chemistry", description="70K compounds - spectra, thermo",
            url="https://webbook.nist.gov/chemistry/",
            estimated_pages=70000, icon="", rate_limit=2.0
        ),
        KnowledgeSourceDef(
            id="chembl", name="ChEMBL",
            category="chemistry", description="2M drug-like molecules",
            url="https://www.ebi.ac.uk/chembl/api/data/",
            estimated_pages=2000000, icon="",
            api_available=True, python_package="chembl_webresource_client"
        ),
        KnowledgeSourceDef(
            id="pdb", name="Protein Data Bank",
            category="chemistry", description="200K 3D protein structures",
            url="https://data.rcsb.org/rest/v1/",
            estimated_pages=200000, icon="", api_available=True
        ),
        KnowledgeSourceDef(
            id="chem_libretexts", name="ChemLibreTexts",
            category="chemistry", description="Open chemistry textbooks",
            url="https://chem.libretexts.org/",
            estimated_pages=20000, icon=""
        ),
    ],
    "Engineering": [
        KnowledgeSourceDef(
            id="eng_libretexts", name="Engineering LibreTexts",
            category="engineering", description="Open engineering textbooks",
            url="https://eng.libretexts.org/",
            estimated_pages=15000, icon=""
        ),
        KnowledgeSourceDef(
            id="nasa_reports", name="NASA Technical Reports",
            category="engineering", description="500K aerospace papers",
            url="https://ntrs.nasa.gov/api/",
            estimated_pages=500000, icon="", api_available=True
        ),
        KnowledgeSourceDef(
            id="freecad_wiki", name="FreeCAD Documentation",
            category="engineering", description="Open source CAD docs",
            url="https://wiki.freecadweb.org/",
            estimated_pages=5000, icon=""
        ),
        KnowledgeSourceDef(
            id="grabcad", name="GrabCAD Library",
            category="engineering", description="5M CAD models & blueprints",
            url="https://grabcad.com/library",
            estimated_pages=5000000, icon="", requires_auth=True
        ),
    ],
    "Science Papers": [
        KnowledgeSourceDef(
            id="arxiv", name="arXiv",
            category="science", description="2.4M papers (Physics, Math, CS)",
            url="https://export.arxiv.org/api/query",
            estimated_pages=2400000, icon="",
            api_available=True, python_package="arxiv", rate_limit=3.0
        ),
        KnowledgeSourceDef(
            id="pubmed", name="PubMed Central",
            category="biology", description="8M biomedical papers",
            url="https://www.ncbi.nlm.nih.gov/pmc/tools/oa-service/",
            estimated_pages=8000000, icon="", api_available=True
        ),
        KnowledgeSourceDef(
            id="openalex", name="OpenAlex",
            category="science", description="250M scholarly works",
            url="https://api.openalex.org/",
            estimated_pages=250000000, icon="",
            api_available=True, rate_limit=0.1
        ),
        KnowledgeSourceDef(
            id="biorxiv", name="bioRxiv",
            category="biology", description="200K biology preprints",
            url="https://www.biorxiv.org/",
            estimated_pages=200000, icon="", rate_limit=3.0
        ),
    ],
    "Mathematics": [
        KnowledgeSourceDef(
            id="mathworld", name="MathWorld",
            category="mathematics", description="13K mathematical entries",
            url="https://mathworld.wolfram.com/",
            estimated_pages=13000, icon=""
        ),
        KnowledgeSourceDef(
            id="proofwiki", name="ProofWiki",
            category="mathematics", description="25K mathematical proofs",
            url="https://proofwiki.org/",
            estimated_pages=25000, icon=""
        ),
        KnowledgeSourceDef(
            id="oeis", name="OEIS",
            category="mathematics", description="370K integer sequences",
            url="https://oeis.org/",
            estimated_pages=370000, icon="", api_available=True
        ),
        KnowledgeSourceDef(
            id="math_libretexts", name="Math LibreTexts",
            category="mathematics", description="Open math textbooks",
            url="https://math.libretexts.org/",
            estimated_pages=15000, icon=""
        ),
    ],
    "Physics": [
        KnowledgeSourceDef(
            id="feynman", name="Feynman Lectures",
            category="physics", description="Legendary physics teaching",
            url="https://www.feynmanlectures.caltech.edu/",
            estimated_pages=200, icon="", rate_limit=2.0
        ),
        KnowledgeSourceDef(
            id="hyperphysics", name="HyperPhysics",
            category="physics", description="Physics concept maps",
            url="http://hyperphysics.phy-astr.gsu.edu/hbase/hframe.html",
            estimated_pages=3000, icon=""
        ),
        KnowledgeSourceDef(
            id="phys_libretexts", name="Physics LibreTexts",
            category="physics", description="Open physics textbooks",
            url="https://phys.libretexts.org/",
            estimated_pages=12000, icon=""
        ),
    ],
    "Programming": [
        KnowledgeSourceDef(
            id="devdocs", name="DevDocs.io",
            category="programming", description="100+ language docs",
            url="https://devdocs.io/",
            estimated_pages=50000, icon=""
        ),
        KnowledgeSourceDef(
            id="mdn", name="MDN Web Docs",
            category="programming", description="HTML/CSS/JS reference",
            url="https://developer.mozilla.org/en-US/docs/Web",
            estimated_pages=15000, icon="", rate_limit=2.0
        ),
        KnowledgeSourceDef(
            id="rosetta", name="Rosetta Code",
            category="programming", description="800+ languages compared",
            url="https://rosettacode.org/wiki/",
            estimated_pages=15000, icon=""
        ),
        KnowledgeSourceDef(
            id="geeksforgeeks", name="GeeksforGeeks",
            category="programming", description="Algorithms & data structures",
            url="https://www.geeksforgeeks.org/",
            estimated_pages=50000, icon="", rate_limit=2.0
        ),
    ],
    "Literature": [
        KnowledgeSourceDef(
            id="gutenberg", name="Project Gutenberg",
            category="literature", description="70K+ classic texts",
            url="https://www.gutenberg.org/",
            estimated_pages=70000, icon="", rate_limit=3.0
        ),
        KnowledgeSourceDef(
            id="standard_ebooks", name="Standard Ebooks",
            category="literature", description="High-quality classics",
            url="https://standardebooks.org/",
            estimated_pages=1000, icon="", rate_limit=2.0
        ),
        KnowledgeSourceDef(
            id="sacred_texts", name="Sacred Texts",
            category="literature", description="World religions & mythology",
            url="https://sacred-texts.com/",
            estimated_pages=10000, icon=""
        ),
    ],
    "Biology & Health": [
        KnowledgeSourceDef(
            id="ncbi_gene", name="NCBI Gene Database",
            category="biology", description="Human genome - all genes & sequences",
            url="https://www.ncbi.nlm.nih.gov/gene/",
            estimated_pages=500000, icon="", api_available=True, rate_limit=0.3
        ),
        KnowledgeSourceDef(
            id="ensembl", name="Ensembl Genome Browser",
            category="biology", description="Vertebrate genomes annotated",
            url="https://rest.ensembl.org/",
            estimated_pages=1000000, icon="", api_available=True
        ),
        KnowledgeSourceDef(
            id="uniprot", name="UniProt",
            category="biology", description="250M protein sequences",
            url="https://rest.uniprot.org/",
            estimated_pages=250000000, icon="", api_available=True
        ),
        KnowledgeSourceDef(
            id="genecards", name="GeneCards",
            category="biology", description="Human gene encyclopedia",
            url="https://www.genecards.org/",
            estimated_pages=50000, icon=""
        ),
        KnowledgeSourceDef(
            id="medlineplus", name="MedlinePlus",
            category="health", description="NIH health encyclopedia",
            url="https://medlineplus.gov/",
            estimated_pages=30000, icon=""
        ),
        KnowledgeSourceDef(
            id="openstax_anatomy", name="OpenStax Anatomy",
            category="biology", description="Human anatomy & physiology",
            url="https://openstax.org/books/anatomy-and-physiology",
            estimated_pages=1500, icon=""
        ),
        KnowledgeSourceDef(
            id="bio_libretexts", name="Biology LibreTexts",
            category="biology", description="Open biology textbooks",
            url="https://bio.libretexts.org/",
            estimated_pages=20000, icon=""
        ),
        KnowledgeSourceDef(
            id="drugbank", name="DrugBank",
            category="health", description="17K drug entries",
            url="https://go.drugbank.com/",
            estimated_pages=17000, icon=""
        ),
    ],
    "Game Design": [
        KnowledgeSourceDef(
            id="gamedeveloper", name="Game Developer (Gamasutra)",
            category="gamedev", description="Game design articles & postmortems",
            url="https://www.gamedeveloper.com/",
            estimated_pages=50000, icon="", rate_limit=2.0
        ),
        KnowledgeSourceDef(
            id="gamedev_patterns", name="Game Programming Patterns",
            category="gamedev", description="Design patterns for games",
            url="https://gameprogrammingpatterns.com/",
            estimated_pages=100, icon=""
        ),
        KnowledgeSourceDef(
            id="redblobgames", name="Red Blob Games",
            category="gamedev", description="Interactive game math tutorials",
            url="https://www.redblobgames.com/",
            estimated_pages=200, icon=""
        ),
        KnowledgeSourceDef(
            id="godot_docs", name="Godot Documentation",
            category="gamedev", description="Open source game engine",
            url="https://docs.godotengine.org/",
            estimated_pages=5000, icon=""
        ),
        KnowledgeSourceDef(
            id="unity_docs", name="Unity Documentation",
            category="gamedev", description="Unity engine manual & scripting",
            url="https://docs.unity3d.com/Manual/",
            estimated_pages=20000, icon=""
        ),
        KnowledgeSourceDef(
            id="unreal_docs", name="Unreal Engine Docs",
            category="gamedev", description="Unreal engine documentation",
            url="https://docs.unrealengine.com/",
            estimated_pages=30000, icon=""
        ),
    ],
    "Graphics": [
        KnowledgeSourceDef(
            id="scratchapixel", name="Scratchapixel",
            category="graphics", description="Computer graphics from scratch",
            url="https://www.scratchapixel.com/",
            estimated_pages=200, icon=""
        ),
        KnowledgeSourceDef(
            id="learnopengl", name="LearnOpenGL",
            category="graphics", description="Modern OpenGL tutorials",
            url="https://learnopengl.com/",
            estimated_pages=100, icon=""
        ),
        KnowledgeSourceDef(
            id="raytracing_weekend", name="Ray Tracing in One Weekend",
            category="graphics", description="Ray tracing book series",
            url="https://raytracing.github.io/",
            estimated_pages=50, icon=""
        ),
        KnowledgeSourceDef(
            id="blender_docs", name="Blender Documentation",
            category="graphics", description="3D modeling & animation",
            url="https://docs.blender.org/manual/en/latest/",
            estimated_pages=5000, icon=""
        ),
        KnowledgeSourceDef(
            id="shadertoy", name="Shadertoy",
            category="graphics", description="GLSL shader examples",
            url="https://www.shadertoy.com/",
            estimated_pages=50000, icon="", rate_limit=2.0
        ),
        KnowledgeSourceDef(
            id="pbr_book", name="PBR Book",
            category="graphics", description="Physically Based Rendering",
            url="https://www.pbr-book.org/",
            estimated_pages=800, icon=""
        ),
    ],
    "Audio & Speech": [
        KnowledgeSourceDef(
            id="musictheory", name="MusicTheory.net",
            category="audio", description="Music theory lessons",
            url="https://www.musictheory.net/",
            estimated_pages=200, icon=""
        ),
        KnowledgeSourceDef(
            id="soundonsound", name="Sound On Sound",
            category="audio", description="Audio production techniques",
            url="https://www.soundonsound.com/",
            estimated_pages=50000, icon="", rate_limit=2.0
        ),
        KnowledgeSourceDef(
            id="dsp_guide", name="DSP Guide",
            category="audio", description="Digital signal processing",
            url="http://www.dspguide.com/",
            estimated_pages=500, icon=""
        ),
        KnowledgeSourceDef(
            id="julius_speech", name="CMU Sphinx",
            category="audio", description="Speech recognition docs",
            url="https://cmusphinx.github.io/",
            estimated_pages=200, icon=""
        ),
        KnowledgeSourceDef(
            id="mozilla_deepspeech", name="Mozilla DeepSpeech",
            category="audio", description="Deep learning speech-to-text",
            url="https://deepspeech.readthedocs.io/",
            estimated_pages=100, icon=""
        ),
        KnowledgeSourceDef(
            id="ipa_handbook", name="IPA Handbook",
            category="audio", description="International Phonetic Alphabet",
            url="https://www.internationalphoneticassociation.org/",
            estimated_pages=300, icon=""
        ),
    ],
    "Video": [
        KnowledgeSourceDef(
            id="ffmpeg_docs", name="FFmpeg Documentation",
            category="video", description="Video processing bible",
            url="https://ffmpeg.org/documentation.html",
            estimated_pages=1000, icon=""
        ),
        KnowledgeSourceDef(
            id="videojs_docs", name="Video.js",
            category="video", description="Web video player docs",
            url="https://docs.videojs.com/",
            estimated_pages=200, icon=""
        ),
        KnowledgeSourceDef(
            id="obs_docs", name="OBS Documentation",
            category="video", description="Streaming & recording",
            url="https://obsproject.com/wiki/",
            estimated_pages=500, icon=""
        ),
        KnowledgeSourceDef(
            id="webrtc", name="WebRTC Samples",
            category="video", description="Real-time communication",
            url="https://webrtc.github.io/samples/",
            estimated_pages=100, icon=""
        ),
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPE STATE TRACKING
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SourceProgress:
    """Progress tracking for a single source."""
    source_id: str
    status: str = "pending"  # pending, in_progress, completed, error
    pages_scraped: int = 0
    words_ingested: int = 0
    errors: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_checkpoint: Optional[str] = None


@dataclass
class ScrapeState:
    """Persistent state for scraping progress."""
    sources: Dict[str, SourceProgress] = field(default_factory=dict)
    last_updated: str = ""
    
    def get_progress(self, source_id: str) -> SourceProgress:
        if source_id not in self.sources:
            self.sources[source_id] = SourceProgress(source_id=source_id)
        return self.sources[source_id]
    
    def mark_started(self, source_id: str):
        prog = self.get_progress(source_id)
        prog.status = "in_progress"
        prog.started_at = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()
    
    def mark_completed(self, source_id: str, pages: int, words: int, errors: int):
        prog = self.get_progress(source_id)
        prog.status = "completed"
        prog.pages_scraped = pages
        prog.words_ingested = words
        prog.errors = errors
        prog.completed_at = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()
    
    def is_completed(self, source_id: str) -> bool:
        return self.sources.get(source_id, SourceProgress(source_id)).status == "completed"
    
    def save(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "sources": {k: asdict(v) for k, v in self.sources.items()},
                "last_updated": self.last_updated
            }
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[ScrapeState] Save error: {e}")
    
    @classmethod
    def load(cls) -> "ScrapeState":
        state = cls()
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                state.last_updated = data.get("last_updated", "")
                for sid, sdata in data.get("sources", {}).items():
                    state.sources[sid] = SourceProgress(**sdata)
            except Exception as e:
                print(f"[ScrapeState] Load error: {e}")
        
        # Auto-detect completed sources from SRM_Intake
        state._detect_completed_from_srm()
        
        return state
    
    def _detect_completed_from_srm(self):
        """
        Scan SRM_Intake to detect sources that were already scraped.
        This makes the GUI smart - it knows what's done even without explicit tracking.
        """
        if not SRM_INTAKE.exists():
            return
        
        # Domain/URL patterns that indicate a source was scraped
        detection_patterns = {
            "iep": ["iep.utm.edu", "internet encyclopedia of philosophy"],
            "sep": ["plato.stanford.edu", "stanford encyclopedia"],
            "gutenberg": ["gutenberg.org", "project gutenberg"],
            "gutenberg_philosophy": ["gutenberg.org/ebooks/bookshelf/68"],
            "pubchem": ["pubchem.ncbi", "molecular", "compound"],
            "arxiv": ["arxiv.org", "arxiv"],
            "chembl": ["chembl", "ebi.ac.uk/chembl"],
            "mathworld": ["mathworld.wolfram"],
            "devdocs": ["devdocs.io"],
            "mdn": ["developer.mozilla.org"],
        }
        
        # Count files by detected domain
        domain_counts = {}
        
        try:
            for day_dir in SRM_INTAKE.iterdir():
                if not day_dir.is_dir():
                    continue
                
                for json_file in day_dir.glob("*.json"):
                    try:
                        # Quick check - read first 2KB
                        with open(json_file, 'r', encoding='utf-8') as f:
                            content = f.read(2048).lower()
                        
                        for source_id, patterns in detection_patterns.items():
                            for pattern in patterns:
                                if pattern.lower() in content:
                                    domain_counts[source_id] = domain_counts.get(source_id, 0) + 1
                                    break
                    except:
                        continue
            
            # Mark as completed if we found enough files (threshold: 50+ for major sources)
            thresholds = {
                "iep": 100,  # ~900 articles
                "sep": 100,  # ~1774 articles
                "gutenberg": 50,
                "pubchem": 100,
                "arxiv": 50,
            }
            
            for source_id, count in domain_counts.items():
                threshold = thresholds.get(source_id, 30)
                if count >= threshold and source_id not in self.sources:
                    print(f"[ScrapeState] Auto-detected completed: {source_id} ({count} files)")
                    self.sources[source_id] = SourceProgress(
                        source_id=source_id,
                        status="completed",
                        pages_scraped=count,
                        completed_at="auto-detected"
                    )
        
        except Exception as e:
            print(f"[ScrapeState] Auto-detection error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY TRACKING
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MindMemoryStats:
    """Memory statistics for a single mind."""
    name: str = ""
    working: int = 0      # Current session / immediate context
    short_term: int = 0   # Recent memories (last 24h)
    long_term: int = 0    # Persistent memories
    local_count: int = 0  # Local SRM memories (separate from cloud)
    total_size_mb: float = 0.0


def count_srm_memories(fairy_name: str = None) -> Dict[str, Any]:
    """Count memories in SRM_Intake by fairy/type."""
    stats = {
        "total": 0,
        "by_day": {},
        "by_type": {},
        "by_fairy": {},
        "size_mb": 0.0,
    }
    
    if not SRM_INTAKE.exists():
        return stats
    
    try:
        for day_dir in SRM_INTAKE.iterdir():
            if not day_dir.is_dir():
                continue
            
            day_name = day_dir.name
            stats["by_day"][day_name] = 0
            
            for json_file in day_dir.glob("*.json"):
                stats["total"] += 1
                stats["by_day"][day_name] += 1
                stats["size_mb"] += json_file.stat().st_size / (1024 * 1024)
                
                # Parse filename to get type
                # Format: fairy.type-uuid.json or type-uuid.json
                name = json_file.stem
                parts = name.split("-")[0].split(".")
                
                if len(parts) >= 2:
                    fairy = parts[0].lower()
                    record_type = ".".join(parts[1:])
                else:
                    fairy = "system"
                    record_type = parts[0]
                
                stats["by_fairy"][fairy] = stats["by_fairy"].get(fairy, 0) + 1
                stats["by_type"][record_type] = stats["by_type"].get(record_type, 0) + 1
    
    except Exception as e:
        stats["error"] = str(e)
    
    return stats


def count_all_knowledge_stores() -> Dict[str, Any]:
    """
    Count ALL memory/knowledge stores across the system.
    Includes: SRM_Intake, scraped knowledge, indexes, etc.
    """
    stores = {
        "srm_intake": {"files": 0, "size_mb": 0.0, "path": str(SRM_INTAKE)},
        "scraped_knowledge": {"files": 0, "size_mb": 0.0, "path": ""},
        "indexes": {"files": 0, "size_mb": 0.0, "path": ""},
        "consolidation": {"files": 0, "size_mb": 0.0, "path": ""},
        "total_size_mb": 0.0,
        "total_files": 0,
    }
    
    # Count SRM_Intake
    if SRM_INTAKE.exists():
        for day_dir in SRM_INTAKE.iterdir():
            if day_dir.is_dir():
                for f in day_dir.glob("*.json"):
                    stores["srm_intake"]["files"] += 1
                    stores["srm_intake"]["size_mb"] += f.stat().st_size / (1024 * 1024)
    
    # Check for scraped knowledge (IEP, SEP, etc.)
    scrape_dirs = [
        PROJECT_ROOT / "P10_Memory" / "system_knowledge",
        PROJECT_ROOT / "P10_Memory" / "Akashic_Records_Physical",
        PROJECT_ROOT / "index",
    ]
    for scrape_dir in scrape_dirs:
        if scrape_dir.exists():
            for f in scrape_dir.rglob("*"):
                if f.is_file():
                    stores["scraped_knowledge"]["files"] += 1
                    stores["scraped_knowledge"]["size_mb"] += f.stat().st_size / (1024 * 1024)
            if not stores["scraped_knowledge"]["path"]:
                stores["scraped_knowledge"]["path"] = str(scrape_dir)
    
    # Check consolidation folder
    consolidation_dir = PROJECT_ROOT / "P10_Memory" / "consolidation"
    if consolidation_dir.exists():
        for f in consolidation_dir.rglob("*.json"):
            stores["consolidation"]["files"] += 1
            stores["consolidation"]["size_mb"] += f.stat().st_size / (1024 * 1024)
        stores["consolidation"]["path"] = str(consolidation_dir)
    
    # Check index folder
    index_dir = PROJECT_ROOT / "index"
    if index_dir.exists():
        for f in index_dir.rglob("*"):
            if f.is_file():
                stores["indexes"]["files"] += 1
                stores["indexes"]["size_mb"] += f.stat().st_size / (1024 * 1024)
        stores["indexes"]["path"] = str(index_dir)
    
    # Sum totals
    for key in ["srm_intake", "scraped_knowledge", "indexes", "consolidation"]:
        stores["total_size_mb"] += stores[key]["size_mb"]
        stores["total_files"] += stores[key]["files"]
    
    return stores


# Personal.AI memory estimate (from Ace's account - 2.6M memories over 2.5 years)
PERSONAL_AI_MEMORY_COUNT = 2_600_000
PERSONAL_AI_ESTIMATE_NOTE = "Personal.AI cloud (2.5 years)"


def get_mind_memory_stats() -> Dict[str, MindMemoryStats]:
    """
    Get memory stats for all minds.
    
    Sources:
    - Sourpatches: Personal.AI cloud (2.6M) + local SRM
    - ClaudeFairy: Local SRM memories
    - System: Scraped knowledge + indexes + other SRM
    """
    srm_stats = count_srm_memories()
    all_stores = count_all_knowledge_stores()
    
    # Get today's date for short-term calculation
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        from datetime import timedelta
        yesterday = (yesterday_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    except:
        yesterday = today
    
    # Calculate per-mind stats
    minds = {
        "sourpatches": MindMemoryStats(name="Sourpatches"),
        "claudefairy": MindMemoryStats(name="ClaudeFairy"),
        "system": MindMemoryStats(name="System"),
    }
    
    # Distribute SRM memories by fairy
    fairy_counts = srm_stats.get("by_fairy", {})
    day_counts = srm_stats.get("by_day", {})
    
    # === SOURPATCHES ===
    # Local SRM entries tagged as sourpatches (her LOCAL brain)
    sour_local = fairy_counts.get("sourpatchesfairy", 0) + fairy_counts.get("sourpatches", 0)
    # Personal.AI cloud memories + local SRM memories
    minds["sourpatches"].long_term = PERSONAL_AI_MEMORY_COUNT + sour_local
    minds["sourpatches"].local_count = sour_local  # Track local separately!
    # Size = local SRM only (cloud size unknown)
    total_srm_size = srm_stats.get("size_mb", 0)
    total_srm_count = srm_stats.get("total", 1) or 1
    minds["sourpatches"].total_size_mb = total_srm_size * (sour_local / total_srm_count) if sour_local > 0 else 0.0
    
    # === CLAUDEFAIRY ===
    claude_count = fairy_counts.get("claudefairy", 0) + fairy_counts.get("claude", 0)
    minds["claudefairy"].long_term = claude_count
    
    # === SYSTEM ===
    # System = everything in SRM not tagged to a fairy + all scraped knowledge
    system_srm = srm_stats.get("total", 0) - sour_local - claude_count
    system_scraped = all_stores.get("scraped_knowledge", {}).get("files", 0)
    system_indexed = all_stores.get("indexes", {}).get("files", 0)
    minds["system"].long_term = system_srm + system_scraped + system_indexed
    
    # System size = all local storage
    minds["system"].total_size_mb = all_stores.get("total_size_mb", 0)
    
    # === SHORT-TERM (recent 2 days) ===
    for day in [today, yesterday]:
        count = day_counts.get(day, 0)
        if count > 0:
            # Distribute recent memories proportionally based on fairy tags
            for fname, fcount in fairy_counts.items():
                if "sour" in fname.lower():
                    minds["sourpatches"].short_term += min(count // 3, fcount)
                elif "claude" in fname.lower():
                    minds["claudefairy"].short_term += min(count // 3, fcount)
            # Rest goes to system
            minds["system"].short_term += count - minds["sourpatches"].short_term - minds["claudefairy"].short_term
    
    # Claude size (proportional to its share of SRM)
    total_srm = srm_stats.get("total", 1) or 1
    srm_size = srm_stats.get("size_mb", 0)
    minds["claudefairy"].total_size_mb = srm_size * (claude_count / total_srm) if total_srm > 0 else 0
    
    return minds


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE BUTTON WIDGET
# ══════════════════════════════════════════════════════════════════════════════

class SourceButton(QPushButton):
    """A button representing a knowledge source with status indicator."""
    
    def __init__(self, source: KnowledgeSourceDef, is_completed: bool = False, parent=None):
        super().__init__(parent)
        self.source = source
        self._is_completed = is_completed
        self._update_display()
        
        self.setMinimumHeight(55)
        self.setCheckable(False)
    
    def _update_display(self):
        """Update button text and style based on status."""
        status_icon = "[DONE]" if self._is_completed else ""
        auth_icon = "" if self.source.requires_auth else ""
        api_icon = "" if self.source.api_available else ""
        
        text = f"{self.source.icon} {self.source.name} {status_icon}\n{self.source.description} {auth_icon}{api_icon}"
        self.setText(text)
        
        if self._is_completed:
            self.setStyleSheet("""
                QPushButton {
                    text-align: left; 
                    padding: 8px;
                    background-color: #1a472a;
                    border: 2px solid #27ae60;
                    color: #90EE90;
                }
                QPushButton:hover {
                    background-color: #1e5631;
                }
            """)
        elif self.source.requires_auth:
            self.setStyleSheet("""
                QPushButton {
                    text-align: left; 
                    padding: 8px;
                    background-color: #4a3c00;
                    border: 1px solid #f39c12;
                }
                QPushButton:hover {
                    background-color: #5a4a00;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    text-align: left; 
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
            """)
    
    def set_completed(self, completed: bool):
        self._is_completed = completed
        self._update_display()


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY DASHBOARD WIDGET
# ══════════════════════════════════════════════════════════════════════════════

class MemoryDashboard(QGroupBox):
    """Dashboard showing memory stats for all minds."""
    
    def __init__(self, parent=None):
        super().__init__(" Multi-Mind Memory Dashboard", parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QGridLayout(self)
        
        # Headers
        headers = ["Mind", "Working", "Short-term", "Long-term", "Storage"]
        for col, header in enumerate(headers):
            lbl = QLabel(header)
            lbl.setFont(QFont("Segoe UI", 9, _FontBold))
            lbl.setStyleSheet("color: #888;")
            layout.addWidget(lbl, 0, col)
        
        # Sourpatches row (with cloud indicator)
        self.sour_name = QLabel(" Sourpatches")
        self.sour_name.setStyleSheet("color: #9b59b6; font-weight: bold;")
        self.sour_name.setToolTip("Personal.AI cloud (2.6M memories) + local SRM")
        self.sour_working = QLabel("0")
        self.sour_short = QLabel("0")
        self.sour_long = QLabel("0")
        self.sour_size = QLabel("[Cloud]")
        self.sour_size.setToolTip("Memories stored in Personal.AI cloud")
        layout.addWidget(self.sour_name, 1, 0)
        layout.addWidget(self.sour_working, 1, 1)
        layout.addWidget(self.sour_short, 1, 2)
        layout.addWidget(self.sour_long, 1, 3)
        layout.addWidget(self.sour_size, 1, 4)
        
        # ClaudeFairy row
        self.claude_name = QLabel(" ClaudeFairy")
        self.claude_name.setStyleSheet("color: #3498db; font-weight: bold;")
        self.claude_working = QLabel("0")
        self.claude_short = QLabel("0")
        self.claude_long = QLabel("0")
        self.claude_size = QLabel("0 MB")
        layout.addWidget(self.claude_name, 2, 0)
        layout.addWidget(self.claude_working, 2, 1)
        layout.addWidget(self.claude_short, 2, 2)
        layout.addWidget(self.claude_long, 2, 3)
        layout.addWidget(self.claude_size, 2, 4)
        
        # System row
        self.sys_name = QLabel("[*] System")
        self.sys_name.setStyleSheet("color: #27ae60; font-weight: bold;")
        self.sys_name.setToolTip("Scraped knowledge + SRM + indexes")
        self.sys_working = QLabel("0")
        self.sys_short = QLabel("0")
        self.sys_long = QLabel("0")
        self.sys_size = QLabel("0 MB")
        layout.addWidget(self.sys_name, 3, 0)
        layout.addWidget(self.sys_working, 3, 1)
        layout.addWidget(self.sys_short, 3, 2)
        layout.addWidget(self.sys_long, 3, 3)
        layout.addWidget(self.sys_size, 3, 4)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine if _QT_VERSION == 6 else QFrame.HLine)
        line.setStyleSheet("background-color: #444;")
        layout.addWidget(line, 4, 0, 1, 5)
        
        # Total row
        self.total_label = QLabel(" Total")
        self.total_label.setStyleSheet("font-weight: bold;")
        self.total_working = QLabel("0")
        self.total_short = QLabel("0")
        self.total_long = QLabel("0")
        self.total_size = QLabel("0 MB")
        self.total_size.setStyleSheet("font-weight: bold; color: #f39c12;")
        layout.addWidget(self.total_label, 5, 0)
        layout.addWidget(self.total_working, 5, 1)
        layout.addWidget(self.total_short, 5, 2)
        layout.addWidget(self.total_long, 5, 3)
        layout.addWidget(self.total_size, 5, 4)
        
        # Refresh button
        self.refresh_btn = QPushButton(" Refresh")
        self.refresh_btn.setMaximumWidth(100)
        self.refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_btn, 5, 5)
    
    def refresh(self):
        """Refresh memory statistics."""
        try:
            minds = get_mind_memory_stats()
            
            # Sourpatches (cloud + local)
            sour = minds.get("sourpatches", MindMemoryStats("Sourpatches"))
            self.sour_working.setText(str(sour.working))
            self.sour_short.setText(str(sour.short_term))
            self.sour_long.setText(f"{sour.long_term:,}")
            # Show cloud + local indicators for Sourpatches
            local_count = getattr(sour, 'local_count', 0)
            if local_count > 0:
                self.sour_size.setText(f"[Cloud] + {local_count} local")
                self.sour_size.setToolTip(f"Personal.AI cloud (2.6M) + {local_count} local SRM memories ({sour.total_size_mb:.2f} MB)")
            else:
                self.sour_size.setText("[Cloud]")
                self.sour_size.setToolTip("Personal.AI cloud storage - no local memories yet")
            
            # ClaudeFairy (local)
            claude = minds.get("claudefairy", MindMemoryStats("ClaudeFairy"))
            self.claude_working.setText(str(claude.working))
            self.claude_short.setText(str(claude.short_term))
            self.claude_long.setText(f"{claude.long_term:,}")
            self.claude_size.setText(f"{claude.total_size_mb:.1f} MB")
            
            # System (local scraped + SRM)
            sys = minds.get("system", MindMemoryStats("System"))
            self.sys_working.setText(str(sys.working))
            self.sys_short.setText(str(sys.short_term))
            self.sys_long.setText(f"{sys.long_term:,}")
            self.sys_size.setText(f"{sys.total_size_mb:.1f} MB")
            
            # Totals
            total_working = sour.working + claude.working + sys.working
            total_short = sour.short_term + claude.short_term + sys.short_term
            total_long = sour.long_term + claude.long_term + sys.long_term
            # Only count local storage in size total
            total_local_size = claude.total_size_mb + sys.total_size_mb
            
            self.total_working.setText(str(total_working))
            self.total_short.setText(str(total_short))
            self.total_long.setText(f"{total_long:,}")
            self.total_size.setText(f"{total_local_size:.1f} MB local")
            
        except Exception as e:
            print(f"[MemoryDashboard] Refresh error: {e}")
            import traceback
            traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN GUI
# ══════════════════════════════════════════════════════════════════════════════

class ScrapeGUIv2(QDialog):
    """Enhanced ScrapeFairy GUI with expanded sources and memory tracking."""
    
    scrape_started = pyqtSignal()
    scrape_finished = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fairy = get_scrape_fairy()
        self.state = ScrapeState.load()
        self.source_buttons: Dict[str, SourceButton] = {}
        self._current_source_id: Optional[str] = None
        
        self._setup_ui()
        self._connect_signals()
        
        # Thread-safe signal connections
        self.log_message.connect(self._handle_log_message)
        self.progress_update.connect(self._handle_progress_update)
        
        # Timers
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._check_progress)
        
        self._memory_timer = QTimer()
        self._memory_timer.timeout.connect(self._refresh_memory)
        self._memory_timer.start(15000)  # 15 seconds
        
        # Initial refresh
        self._refresh_memory()
    
    def _setup_ui(self):
        self.setWindowTitle(" ScrapeFairy v2.0 - Knowledge Acquisition")
        self.setMinimumSize(900, 750)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(" ScrapeFairy - Train Knowledge into Memory")
        header.setFont(QFont("Segoe UI", 16, _FontBold))
        header.setStyleSheet("color: #9b59b6; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Splitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Vertical if _QT_VERSION == 6 else Qt.Vertical)
        
        # ════════════════════════════════════════════════════════════════════
        # Knowledge Sources Tabs (by category)
        # ════════════════════════════════════════════════════════════════════
        tabs = QTabWidget()
        
        for category, sources in KNOWLEDGE_SOURCES.items():
            tab = self._create_category_tab(category, sources)
            tabs.addTab(tab, category)
        
        # Custom tab
        custom_tab = self._create_custom_tab()
        tabs.addTab(custom_tab, " Custom")
        
        splitter.addWidget(tabs)
        
        # ════════════════════════════════════════════════════════════════════
        # Memory Dashboard
        # ════════════════════════════════════════════════════════════════════
        self.memory_dashboard = MemoryDashboard()
        splitter.addWidget(self.memory_dashboard)
        
        # ════════════════════════════════════════════════════════════════════
        # Progress Section
        # ════════════════════════════════════════════════════════════════════
        progress_widget = self._create_progress_section()
        splitter.addWidget(progress_widget)
        
        # Set initial sizes
        splitter.setSizes([400, 150, 200])
        layout.addWidget(splitter)
        
        # ════════════════════════════════════════════════════════════════════
        # Control Buttons
        # ════════════════════════════════════════════════════════════════════
        button_layout = QHBoxLayout()
        
        self.stop_btn = QPushButton("[Stop]")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        self.reset_state_btn = QPushButton(" Reset Progress")
        self.reset_state_btn.setToolTip("Clear completion tracking (doesn't delete data)")
        button_layout.addWidget(self.reset_state_btn)
        
        self.close_btn = QPushButton("Close")
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_category_tab(self, category: str, sources: List[KnowledgeSourceDef]) -> QWidget:
        """Create a tab for a category of sources."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Info label
        completed_count = sum(1 for s in sources if self.state.is_completed(s.id))
        info = QLabel(f"{len(sources)} sources • {completed_count} completed")
        info.setStyleSheet("color: #888; margin-bottom: 5px;")
        layout.addWidget(info)
        
        # Scroll area for buttons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame if _QT_VERSION == 6 else QFrame.NoFrame)
        
        scroll_content = QWidget()
        grid = QGridLayout(scroll_content)
        grid.setSpacing(8)
        
        for i, source in enumerate(sources):
            row, col = divmod(i, 2)
            is_done = self.state.is_completed(source.id)
            
            btn = SourceButton(source, is_completed=is_done)
            btn.clicked.connect(lambda checked, s=source: self._start_source(s))
            
            grid.addWidget(btn, row, col)
            self.source_buttons[source.id] = btn
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return tab
    
    def _create_custom_tab(self) -> QWidget:
        """Create the custom URL tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # URL input
        url_group = QGroupBox("Target Website")
        url_layout = QGridLayout(url_group)
        
        url_layout.addWidget(QLabel("Start URL:"), 0, 0)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/articles/")
        url_layout.addWidget(self.url_input, 0, 1)
        
        url_layout.addWidget(QLabel("Job Name:"), 1, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My Knowledge Source")
        url_layout.addWidget(self.name_input, 1, 1)
        
        url_layout.addWidget(QLabel("Category:"), 2, 0)
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("philosophy, science, engineering...")
        url_layout.addWidget(self.domain_input, 2, 1)
        
        layout.addWidget(url_group)
        
        # Options
        options_group = QGroupBox("Crawl Options")
        options_layout = QGridLayout(options_group)
        
        options_layout.addWidget(QLabel("Max Pages:"), 0, 0)
        self.max_pages_spin = QSpinBox()
        self.max_pages_spin.setRange(1, 100000)
        self.max_pages_spin.setValue(500)
        options_layout.addWidget(self.max_pages_spin, 0, 1)
        
        options_layout.addWidget(QLabel("Delay (sec):"), 0, 2)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.5, 10.0)
        self.delay_spin.setValue(1.5)
        options_layout.addWidget(self.delay_spin, 0, 3)
        
        self.follow_links_check = QCheckBox("Follow Links")
        self.follow_links_check.setChecked(True)
        options_layout.addWidget(self.follow_links_check, 1, 0, 1, 2)
        
        self.api_mode_check = QCheckBox("API Mode (JSON)")
        options_layout.addWidget(self.api_mode_check, 1, 2, 1, 2)
        
        layout.addWidget(options_group)
        
        # Start button
        self.custom_start_btn = QPushButton(" Start Custom Scrape")
        self.custom_start_btn.setMinimumHeight(40)
        self.custom_start_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        layout.addWidget(self.custom_start_btn)
        
        layout.addStretch()
        return tab
    
    def _create_progress_section(self) -> QWidget:
        """Create the progress/log section."""
        widget = QGroupBox("Progress")
        layout = QVBoxLayout(widget)
        
        # Stats bar
        stats_layout = QHBoxLayout()
        
        self.pages_label = QLabel("Pages: 0")
        self.pages_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.pages_label)
        
        self.words_label = QLabel("Words: 0")
        self.words_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.words_label)
        
        self.errors_label = QLabel("Errors: 0")
        self.errors_label.setStyleSheet("font-weight: bold; color: #e74c3c;")
        stats_layout.addWidget(self.errors_label)
        
        stats_layout.addStretch()
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #27ae60;")
        stats_layout.addWidget(self.status_label)
        
        layout.addLayout(stats_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        self.log_output.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; "
            "background-color: #1e1e1e; color: #ddd;"
        )
        layout.addWidget(self.log_output)
        
        return widget
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.custom_start_btn.clicked.connect(self._start_custom)
        self.stop_btn.clicked.connect(self._stop_scrape)
        self.close_btn.clicked.connect(self.close)
        self.reset_state_btn.clicked.connect(self._reset_state)
    
    def _start_source(self, source: KnowledgeSourceDef):
        """Start scraping a predefined source."""
        if self.fairy.is_running():
            QMessageBox.warning(self, "Busy", "A scrape is already in progress.")
            return
        
        if source.requires_auth:
            QMessageBox.information(
                self, "Authentication Required",
                f"{source.name} requires an account.\n\n"
                f"URL: {source.url}\n\n"
                "Please log in manually and use Custom tab for scraping."
            )
            return
        
        self._current_source_id = source.id
        self.state.mark_started(source.id)
        self.state.save()
        
        config = source.get_config()
        self._start_scrape(config)
    
    def _start_custom(self):
        """Start a custom website scrape."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a start URL.")
            return
        
        name = self.name_input.text().strip() or "Custom Scrape"
        domain = self.domain_input.text().strip() or "general"
        
        source_type = SourceType.API_JSON if self.api_mode_check.isChecked() else SourceType.WEBSITE
        
        config = ScrapeConfig(
            name=name,
            source_type=source_type,
            start_url=url,
            follow_links=self.follow_links_check.isChecked(),
            max_pages=self.max_pages_spin.value(),
            delay_seconds=self.delay_spin.value(),
            knowledge_domain=domain,
            knowledge_kind=f"system.knowledge.{domain}",
        )
        
        self._current_source_id = None
        self._start_scrape(config)
    
    def _start_scrape(self, config: ScrapeConfig):
        """Start a scrape with the given config."""
        self.log_output.clear()
        self._log(f"Starting: {config.name}")
        self._log(f"URL: {config.start_url}")
        
        self.status_label.setText("Running...")
        self.status_label.setStyleSheet("color: #f39c12;")
        self.progress_bar.setVisible(True)
        self.stop_btn.setEnabled(True)
        
        self._set_buttons_enabled(False)
        
        def log_callback(msg):
            self.log_message.emit(msg)
        
        def progress_callback(stats):
            self.progress_update.emit(stats)
        
        self.fairy.start_scrape(config, progress_callback=progress_callback, log_callback=log_callback)
        self._poll_timer.start(500)
        self.scrape_started.emit()
    
    def _stop_scrape(self):
        self.fairy.stop_scrape()
        self._log("Stopping...")
    
    def _check_progress(self):
        if not self.fairy.is_running():
            self._poll_timer.stop()
            self._on_scrape_finished()
    
    def _on_scrape_finished(self):
        stats = self.fairy.get_stats()
        
        # Update state
        if self._current_source_id:
            self.state.mark_completed(
                self._current_source_id,
                stats.get("pages_ingested", 0),
                stats.get("total_words", 0),
                stats.get("errors", 0)
            )
            self.state.save()
            
            # Update button
            if self._current_source_id in self.source_buttons:
                self.source_buttons[self._current_source_id].set_completed(True)
        
        self.status_label.setText("Complete!")
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        
        self._set_buttons_enabled(True)
        self._handle_progress_update(stats)
        
        duration = (stats.get("end_time") or 0) - (stats.get("start_time") or 0)
        self._log(f"[DONE] Complete: {stats.get('pages_ingested', 0)} pages, "
                  f"{stats.get('total_words', 0):,} words in {duration:.1f}s")
        
        self._refresh_memory()
        self.scrape_finished.emit(stats)
    
    def _handle_log_message(self, message: str):
        self._log(message)
    
    def _handle_progress_update(self, stats: Dict[str, Any]):
        self.pages_label.setText(f"Pages: {stats.get('pages_ingested', 0)}")
        self.words_label.setText(f"Words: {stats.get('total_words', 0):,}")
        self.errors_label.setText(f"Errors: {stats.get('errors', 0)}")
    
    def _log(self, message: str):
        self.log_output.append(message)
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _set_buttons_enabled(self, enabled: bool):
        for btn in self.source_buttons.values():
            btn.setEnabled(enabled)
        self.custom_start_btn.setEnabled(enabled)
    
    def _refresh_memory(self):
        self.memory_dashboard.refresh()
    
    def _reset_state(self):
        reply = QMessageBox.question(
            self, "Reset Progress",
            "This will clear completion tracking for all sources.\n"
            "(Your scraped data will NOT be deleted.)\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.state = ScrapeState()
            self.state.save()
            
            for btn in self.source_buttons.values():
                btn.set_completed(False)
            
            self._log("Progress tracking reset.")


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Dark theme
    app.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;
            color: #ddd;
        }
        QGroupBox {
            border: 1px solid #444;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            color: #9b59b6;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #3c3c3c;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 5px;
        }
        QPushButton {
            background-color: #3c3c3c;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 8px 15px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:disabled {
            background-color: #2b2b2b;
            color: #666;
        }
        QTabWidget::pane {
            border: 1px solid #444;
        }
        QTabBar::tab {
            background-color: #3c3c3c;
            padding: 8px 12px;
            border: 1px solid #444;
        }
        QTabBar::tab:selected {
            background-color: #4a4a4a;
            border-bottom: 2px solid #9b59b6;
        }
        QScrollArea {
            border: none;
        }
    """)
    
    dialog = ScrapeGUIv2()
    dialog.show()
    
    sys.exit(app.exec() if _QT_VERSION == 6 else app.exec_())
