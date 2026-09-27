"""
P40_Sensory/scrape - Knowledge Acquisition Module (LAZY LOADING)

ScrapeFairy and GUI for training external knowledge into memory.

v2.0 Features:
- 30+ knowledge sources across 8 categories
- Chemistry, Engineering, Science, Programming, Math, Physics
- Multi-mind memory dashboard (Sour, Claude, System)
- Auto-detection of completed sources
- Working/Short-term/Long-term memory breakdown

NOTE: This module uses LAZY LOADING to avoid blocking boot.
      Heavy imports only happen when classes are actually used.
"""

__all__ = [
    # Core
    "ScrapeFairy",
    "ScrapeConfig",
    "SourceType",
    "ScrapedPage",
    "get_scrape_fairy",
    "get_iep_config",
    "get_sep_config",
    # GUI
    "ScrapeGUI",
    "ScrapeGUIv2",
    # State tracking
    "ScrapeState",
    "SourceProgress",
    # Knowledge sources
    "KNOWLEDGE_SOURCES",
    "KnowledgeSourceDef",
    # Memory dashboard
    "MemoryDashboard",
    "get_mind_memory_stats",
    "count_srm_memories",
    # Knowledge sources module
    "KnowledgeSource",
    "KnowledgeCategory",
    "get_all_sources",
    "get_sources_by_category",
    "get_api_sources",
    "get_scrape_friendly_sources",
    # Enhancements
    "EnhancedScrapeFairy",
    "ContentDeduplicator",
    "BookRegistry",
    "EPUBExtractor",
    "PDFExtractor",
    "ZIPExtractor",
    # Flags
    "HAS_GUI_V2",
    "HAS_KNOWLEDGE_SOURCES",
    "HAS_ENHANCEMENTS",
]

# Cache for lazy-loaded modules
_loaded = {}

# Availability flags (determined on first access)
HAS_GUI_V2 = None
HAS_KNOWLEDGE_SOURCES = None
HAS_ENHANCEMENTS = None


def __getattr__(name):
    """Lazy import handler - only import when accessed."""
    global _loaded, HAS_GUI_V2, HAS_KNOWLEDGE_SOURCES, HAS_ENHANCEMENTS

    # Core scrape fairy items
    if name in ('ScrapeFairy', 'ScrapeConfig', 'SourceType', 'ScrapedPage',
                'get_scrape_fairy', 'get_iep_config', 'get_sep_config'):
        if 'scrape_fairy' not in _loaded:
            from . import scrape_fairy
            _loaded['scrape_fairy'] = scrape_fairy
        return getattr(_loaded['scrape_fairy'], name)

    # Basic GUI
    if name == 'ScrapeGUI':
        if 'scrape_gui' not in _loaded:
            from . import scrape_gui
            _loaded['scrape_gui'] = scrape_gui
        return _loaded['scrape_gui'].ScrapeGUI

    # GUI v2 items
    if name in ('ScrapeGUIv2', 'ScrapeState', 'SourceProgress', 'KNOWLEDGE_SOURCES',
                'KnowledgeSourceDef', 'MemoryDashboard', 'get_mind_memory_stats',
                'count_srm_memories'):
        if 'scrape_gui_v2' not in _loaded:
            try:
                from . import scrape_gui_v2
                _loaded['scrape_gui_v2'] = scrape_gui_v2
                HAS_GUI_V2 = True
            except ImportError as e:
                print(f"[scrape] GUI v2 not available: {e}")
                _loaded['scrape_gui_v2'] = None
                HAS_GUI_V2 = False
        if _loaded['scrape_gui_v2'] is None:
            # Fallback for ScrapeGUIv2
            if name == 'ScrapeGUIv2':
                return __getattr__('ScrapeGUI')
            return None
        return getattr(_loaded['scrape_gui_v2'], name)

    # Knowledge sources module
    if name in ('KnowledgeSource', 'KnowledgeCategory', 'get_all_sources',
                'get_sources_by_category', 'get_api_sources', 'get_scrape_friendly_sources'):
        if 'knowledge_sources' not in _loaded:
            try:
                from . import knowledge_sources
                _loaded['knowledge_sources'] = knowledge_sources
                HAS_KNOWLEDGE_SOURCES = True
            except ImportError:
                _loaded['knowledge_sources'] = None
                HAS_KNOWLEDGE_SOURCES = False
        if _loaded['knowledge_sources'] is None:
            return None
        return getattr(_loaded['knowledge_sources'], name)

    # Enhancements
    if name in ('EnhancedScrapeFairy', 'ContentDeduplicator', 'BookRegistry',
                'EPUBExtractor', 'PDFExtractor', 'ZIPExtractor'):
        if 'scrape_enhancements' not in _loaded:
            try:
                from . import scrape_enhancements
                _loaded['scrape_enhancements'] = scrape_enhancements
                HAS_ENHANCEMENTS = True
            except ImportError:
                _loaded['scrape_enhancements'] = None
                HAS_ENHANCEMENTS = False
        if _loaded['scrape_enhancements'] is None:
            return None
        return getattr(_loaded['scrape_enhancements'], name)

    # Availability flags
    if name == 'HAS_GUI_V2':
        if HAS_GUI_V2 is None:
            try:
                from . import scrape_gui_v2
                HAS_GUI_V2 = True
            except ImportError:
                HAS_GUI_V2 = False
        return HAS_GUI_V2

    if name == 'HAS_KNOWLEDGE_SOURCES':
        if HAS_KNOWLEDGE_SOURCES is None:
            try:
                from . import knowledge_sources
                HAS_KNOWLEDGE_SOURCES = True
            except ImportError:
                HAS_KNOWLEDGE_SOURCES = False
        return HAS_KNOWLEDGE_SOURCES

    if name == 'HAS_ENHANCEMENTS':
        if HAS_ENHANCEMENTS is None:
            try:
                from . import scrape_enhancements
                HAS_ENHANCEMENTS = True
            except ImportError:
                HAS_ENHANCEMENTS = False
        return HAS_ENHANCEMENTS

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
