"""
Knowledge Sources Configuration
================================
Comprehensive list of scrapeable sources for building consciousness knowledge base.

Categories:
- Programming & Development
- Science & Research Papers
- Chemistry & Molecules
- Engineering & CAD
- Mathematics
- Physics
- Biology & Medicine
- Philosophy (existing)

Usage:
    from knowledge_sources import get_all_configs, get_config_by_category
    
    # Get all configs
    all_configs = get_all_configs()
    
    # Get by category
    chem_configs = get_config_by_category("chemistry")
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class KnowledgeCategory(Enum):
    PROGRAMMING = "programming"
    SCIENCE = "science"
    CHEMISTRY = "chemistry"
    ENGINEERING = "engineering"
    MATHEMATICS = "mathematics"
    PHYSICS = "physics"
    BIOLOGY = "biology"
    PHILOSOPHY = "philosophy"
    LITERATURE = "literature"
    CAD = "cad"


@dataclass
class KnowledgeSource:
    """A scrapeable knowledge source."""
    
    name: str
    url: str
    category: KnowledgeCategory
    description: str
    api_available: bool = False
    api_url: Optional[str] = None
    python_package: Optional[str] = None  # pip install X
    scrape_friendly: bool = True  # Allows scraping
    rate_limit: float = 1.0  # seconds between requests
    estimated_pages: int = 0
    content_type: str = "html"  # html, json, xml, pdf
    requires_auth: bool = False
    notes: str = ""
    emotional_tags: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_scrape_config(self):
        """Convert to ScrapeConfig format."""
        from fairies.P40_Sensory.scrape.scrape_fairy import ScrapeConfig, SourceType
        
        source_type = SourceType.WEBSITE
        if self.content_type == "json":
            source_type = SourceType.API_JSON
        
        return ScrapeConfig(
            name=self.name,
            source_type=source_type,
            start_url=self.url,
            follow_links=True,
            max_pages=min(self.estimated_pages, 5000),
            delay_seconds=self.rate_limit,
            knowledge_domain=self.category.value,
            knowledge_kind=f"system.knowledge.{self.category.value}",
            emotional_tags=self.emotional_tags,
        )


# ══════════════════════════════════════════════════════════════════════════════
# PROGRAMMING & DEVELOPMENT
# ══════════════════════════════════════════════════════════════════════════════

PROGRAMMING_SOURCES = [
    KnowledgeSource(
        name="DevDocs.io",
        url="https://devdocs.io/",
        category=KnowledgeCategory.PROGRAMMING,
        description="Aggregated docs for 100+ languages: Python, JS, Rust, Go, C++, etc.",
        api_available=True,
        api_url="https://devdocs.io/docs.json",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=50000,
        notes="Open source, offline-friendly. Clone from GitHub for bulk access.",
        emotional_tags={
            "tutorial": ["clarity", "learning"],
            "reference": ["precision", "rigor"],
            "api": ["structure", "utility"],
        }
    ),
    KnowledgeSource(
        name="MDN Web Docs",
        url="https://developer.mozilla.org/en-US/docs/Web",
        category=KnowledgeCategory.PROGRAMMING,
        description="Definitive web tech reference: HTML, CSS, JS, Web APIs",
        api_available=True,
        api_url="https://developer.mozilla.org/api/v1/",
        scrape_friendly=True,  # Use their GitHub mirror instead
        rate_limit=2.0,
        estimated_pages=15000,
        notes="Content on GitHub: github.com/mdn/content. Better to clone than scrape.",
        emotional_tags={
            "javascript": ["dynamism", "interactivity"],
            "css": ["aesthetics", "structure"],
            "html": ["foundation", "semantics"],
        }
    ),
    KnowledgeSource(
        name="Python Docs",
        url="https://docs.python.org/3/",
        category=KnowledgeCategory.PROGRAMMING,
        description="Official Python documentation",
        api_available=False,
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=3000,
        notes="Download as HTML archive from python.org for bulk access",
        emotional_tags={
            "tutorial": ["learning", "guidance"],
            "library": ["utility", "power"],
        }
    ),
    KnowledgeSource(
        name="Rust Book",
        url="https://doc.rust-lang.org/book/",
        category=KnowledgeCategory.PROGRAMMING,
        description="The Rust Programming Language book",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=500,
        notes="Also available as EPUB/PDF",
        emotional_tags={
            "ownership": ["safety", "discipline"],
            "concurrency": ["power", "complexity"],
        }
    ),
    KnowledgeSource(
        name="Go Docs",
        url="https://go.dev/doc/",
        category=KnowledgeCategory.PROGRAMMING,
        description="Official Go documentation",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=2000,
    ),
    KnowledgeSource(
        name="Real Python",
        url="https://realpython.com/",
        category=KnowledgeCategory.PROGRAMMING,
        description="Python tutorials and guides",
        scrape_friendly=False,  # Subscription content
        rate_limit=2.0,
        estimated_pages=1500,
        notes="Some free content, premium requires subscription",
    ),
    KnowledgeSource(
        name="GeeksforGeeks",
        url="https://www.geeksforgeeks.org/",
        category=KnowledgeCategory.PROGRAMMING,
        description="CS fundamentals, algorithms, data structures",
        scrape_friendly=True,
        rate_limit=2.0,
        estimated_pages=50000,
        emotional_tags={
            "algorithm": ["logic", "efficiency"],
            "data structure": ["organization", "optimization"],
        }
    ),
    KnowledgeSource(
        name="W3Schools",
        url="https://www.w3schools.com/",
        category=KnowledgeCategory.PROGRAMMING,
        description="Web development tutorials (HTML, CSS, JS, SQL, Python)",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=10000,
        notes="Basic tutorials, good for fundamentals",
    ),
    KnowledgeSource(
        name="cppreference",
        url="https://en.cppreference.com/w/",
        category=KnowledgeCategory.PROGRAMMING,
        description="C and C++ language reference",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=8000,
        notes="MediaWiki-based, can export",
    ),
    KnowledgeSource(
        name="Rosetta Code",
        url="https://rosettacode.org/wiki/Rosetta_Code",
        category=KnowledgeCategory.PROGRAMMING,
        description="Programming tasks in 800+ languages - compare implementations",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=15000,
        notes="MediaWiki, great for cross-language learning",
        emotional_tags={
            "comparison": ["perspective", "understanding"],
            "solution": ["creativity", "elegance"],
        }
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# CHEMISTRY & MOLECULES
# ══════════════════════════════════════════════════════════════════════════════

CHEMISTRY_SOURCES = [
    KnowledgeSource(
        name="PubChem",
        url="https://pubchem.ncbi.nlm.nih.gov/",
        category=KnowledgeCategory.CHEMISTRY,
        description="World's largest FREE chemistry database - 111M+ compounds",
        api_available=True,
        api_url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/",
        python_package="pubchempy",
        scrape_friendly=True,
        rate_limit=0.2,  # 5 requests/second allowed
        estimated_pages=111000000,
        content_type="json",
        notes="""
        AMAZING resource! Use pubchempy for Python access.
        - Compound structures (2D/3D)
        - Molecular properties
        - Biological activities
        - Safety data
        - 3D conformers
        Download SDF files for molecular visualization.
        FTP bulk: ftp://ftp.ncbi.nlm.nih.gov/pubchem/
        """,
        emotional_tags={
            "compound": ["structure", "identity"],
            "reaction": ["transformation", "dynamics"],
            "toxicity": ["caution", "safety"],
        }
    ),
    KnowledgeSource(
        name="ChemSpider (RSC)",
        url="https://www.chemspider.com/",
        category=KnowledgeCategory.CHEMISTRY,
        description="100M+ chemical structures from Royal Society of Chemistry",
        api_available=True,
        api_url="https://api.rsc.org/",
        requires_auth=True,  # Free API key required
        rate_limit=1.0,
        estimated_pages=100000000,
        notes="Free API key from RSC. Good for structure search.",
    ),
    KnowledgeSource(
        name="NIST Chemistry WebBook",
        url="https://webbook.nist.gov/chemistry/",
        category=KnowledgeCategory.CHEMISTRY,
        description="Thermochemical, spectral, ion data for 70,000+ compounds",
        api_available=False,
        scrape_friendly=True,
        rate_limit=2.0,
        estimated_pages=70000,
        notes="Authoritative US government data. Public domain.",
        emotional_tags={
            "thermodynamics": ["energy", "equilibrium"],
            "spectroscopy": ["identity", "analysis"],
        }
    ),
    KnowledgeSource(
        name="ChEMBL",
        url="https://www.ebi.ac.uk/chembl/",
        category=KnowledgeCategory.CHEMISTRY,
        description="Bioactive molecules with drug-like properties - 2M+ compounds",
        api_available=True,
        api_url="https://www.ebi.ac.uk/chembl/api/data/",
        python_package="chembl_webresource_client",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=2000000,
        notes="Drug discovery focused. Great for pharmacology.",
    ),
    KnowledgeSource(
        name="DrugBank",
        url="https://go.drugbank.com/",
        category=KnowledgeCategory.CHEMISTRY,
        description="Comprehensive drug database - mechanisms, interactions",
        api_available=True,
        requires_auth=True,
        rate_limit=1.0,
        estimated_pages=15000,
        notes="Academic license available for research",
    ),
    KnowledgeSource(
        name="ChemLibreTexts",
        url="https://chem.libretexts.org/",
        category=KnowledgeCategory.CHEMISTRY,
        description="Open chemistry textbooks - organic, inorganic, biochem",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=20000,
        notes="CC-BY licensed! Great for foundational chemistry.",
        emotional_tags={
            "organic": ["life", "carbon"],
            "inorganic": ["minerals", "metals"],
            "biochemistry": ["life", "complexity"],
        }
    ),
    KnowledgeSource(
        name="Protein Data Bank (PDB)",
        url="https://www.rcsb.org/",
        category=KnowledgeCategory.CHEMISTRY,
        description="3D structures of proteins, nucleic acids, complex assemblies",
        api_available=True,
        api_url="https://data.rcsb.org/rest/v1/",
        scrape_friendly=True,
        rate_limit=0.5,
        estimated_pages=200000,
        notes="Download PDB files for molecular visualization. Essential for structural biology.",
        emotional_tags={
            "protein": ["function", "structure"],
            "dna": ["information", "life"],
        }
    ),
    KnowledgeSource(
        name="Open Chemistry (GitHub)",
        url="https://github.com/OpenChemistry",
        category=KnowledgeCategory.CHEMISTRY,
        description="Open source chemistry visualization and analysis tools",
        scrape_friendly=True,
        rate_limit=1.0,
        notes="Clone repos for source code and documentation",
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# ENGINEERING & CAD
# ══════════════════════════════════════════════════════════════════════════════

ENGINEERING_SOURCES = [
    KnowledgeSource(
        name="GrabCAD Library",
        url="https://grabcad.com/library",
        category=KnowledgeCategory.CAD,
        description="Millions of free CAD designs - mechanical, electrical, architectural",
        api_available=False,
        scrape_friendly=False,  # Account required for downloads
        requires_auth=True,
        rate_limit=3.0,
        estimated_pages=5000000,
        notes="""
        HUGE resource for 3D models!
        - STEP, IGES, STL formats
        - AutoCAD DWG files
        - SolidWorks, Fusion 360, etc.
        Account required but free.
        """,
        emotional_tags={
            "mechanical": ["precision", "function"],
            "architecture": ["space", "design"],
        }
    ),
    KnowledgeSource(
        name="TraceParts",
        url="https://www.traceparts.com/en",
        category=KnowledgeCategory.CAD,
        description="3D models, CAD files, 2D drawings - industrial components",
        api_available=False,
        requires_auth=True,
        rate_limit=2.0,
        estimated_pages=1000000,
        notes="Industrial parts library. Free account required.",
    ),
    KnowledgeSource(
        name="FreeCAD Documentation",
        url="https://wiki.freecadweb.org/",
        category=KnowledgeCategory.CAD,
        description="Open source parametric 3D CAD modeler documentation",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=5000,
        notes="MediaWiki format. Also clone from GitHub.",
    ),
    KnowledgeSource(
        name="OpenSCAD Manual",
        url="https://openscad.org/documentation.html",
        category=KnowledgeCategory.CAD,
        description="Programmer's solid 3D CAD modeler - scripting-based",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=500,
        notes="Code-based CAD - very relevant for us!",
    ),
    KnowledgeSource(
        name="Engineering LibreTexts",
        url="https://eng.libretexts.org/",
        category=KnowledgeCategory.ENGINEERING,
        description="Open engineering textbooks - mechanical, electrical, civil",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=15000,
        notes="CC-BY licensed! Covers all engineering disciplines.",
        emotional_tags={
            "mechanical": ["forces", "motion"],
            "electrical": ["current", "potential"],
            "civil": ["structure", "infrastructure"],
        }
    ),
    KnowledgeSource(
        name="MIT OpenCourseWare - Engineering",
        url="https://ocw.mit.edu/collections/engineering/",
        category=KnowledgeCategory.ENGINEERING,
        description="MIT engineering courses - lectures, notes, problem sets",
        scrape_friendly=True,
        rate_limit=2.0,
        estimated_pages=10000,
        notes="CC-BY-NC-SA. World-class engineering education free.",
    ),
    KnowledgeSource(
        name="NASA Technical Reports",
        url="https://ntrs.nasa.gov/",
        category=KnowledgeCategory.ENGINEERING,
        description="NASA research - aerospace, materials, systems engineering",
        api_available=True,
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=500000,
        notes="Public domain US government research!",
        emotional_tags={
            "aerospace": ["flight", "exploration"],
            "materials": ["strength", "innovation"],
        }
    ),
    KnowledgeSource(
        name="NIST Engineering Data",
        url="https://www.nist.gov/data",
        category=KnowledgeCategory.ENGINEERING,
        description="Materials properties, measurement standards, calibration data",
        api_available=True,
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=50000,
        notes="Authoritative US government standards data.",
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# SCIENCE & RESEARCH PAPERS
# ══════════════════════════════════════════════════════════════════════════════

SCIENCE_SOURCES = [
    KnowledgeSource(
        name="arXiv",
        url="https://arxiv.org/",
        category=KnowledgeCategory.SCIENCE,
        description="2.4M+ papers - Physics, Math, CS, Biology, Economics",
        api_available=True,
        api_url="https://export.arxiv.org/api/query",
        python_package="arxiv",
        scrape_friendly=True,
        rate_limit=3.0,  # 1 request per 3 seconds
        estimated_pages=2400000,
        notes="""
        ESSENTIAL! Open access preprints.
        - Full PDFs available
        - LaTeX source available
        - Use arxiv Python package
        - Bulk via S3 (requires AWS account)
        Categories: physics, math, cs, q-bio, q-fin, stat, eess, econ
        """,
        emotional_tags={
            "quantum": ["mystery", "wonder"],
            "neural": ["intelligence", "emergence"],
            "cosmology": ["awe", "vastness"],
        }
    ),
    KnowledgeSource(
        name="OpenAlex",
        url="https://openalex.org/",
        category=KnowledgeCategory.SCIENCE,
        description="Open catalog of 250M+ scholarly works - papers, authors, institutions",
        api_available=True,
        api_url="https://api.openalex.org/",
        scrape_friendly=True,
        rate_limit=0.1,  # 10 requests/second
        estimated_pages=250000000,
        notes="Free, open replacement for Microsoft Academic. Great for citation networks.",
    ),
    KnowledgeSource(
        name="Semantic Scholar",
        url="https://www.semanticscholar.org/",
        category=KnowledgeCategory.SCIENCE,
        description="AI-powered research tool - 200M+ papers with semantic analysis",
        api_available=True,
        api_url="https://api.semanticscholar.org/",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=200000000,
        notes="AI2 project. Good for finding related papers.",
    ),
    KnowledgeSource(
        name="PubMed Central",
        url="https://www.ncbi.nlm.nih.gov/pmc/",
        category=KnowledgeCategory.BIOLOGY,
        description="Free full-text archive of biomedical/life sciences literature",
        api_available=True,
        api_url="https://www.ncbi.nlm.nih.gov/pmc/tools/oa-service/",
        scrape_friendly=True,
        rate_limit=0.3,
        estimated_pages=8000000,
        notes="NIH open access archive. XML available for bulk download.",
    ),
    KnowledgeSource(
        name="PLOS ONE",
        url="https://journals.plos.org/plosone/",
        category=KnowledgeCategory.SCIENCE,
        description="Open access multidisciplinary research journal",
        api_available=True,
        python_package="allofplos",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=300000,
        notes="CC-BY licensed! Use allofplos package for bulk download.",
    ),
    KnowledgeSource(
        name="ScienceOpen",
        url="https://www.scienceopen.com/",
        category=KnowledgeCategory.SCIENCE,
        description="Open access research network - 90M+ records",
        api_available=True,
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=90000000,
    ),
    KnowledgeSource(
        name="bioRxiv",
        url="https://www.biorxiv.org/",
        category=KnowledgeCategory.BIOLOGY,
        description="Preprint server for biology",
        api_available=True,
        scrape_friendly=True,
        rate_limit=3.0,
        estimated_pages=200000,
        notes="Like arXiv but for biology. Full PDFs available.",
    ),
    KnowledgeSource(
        name="medRxiv",
        url="https://www.medrxiv.org/",
        category=KnowledgeCategory.BIOLOGY,
        description="Preprint server for health sciences",
        api_available=True,
        scrape_friendly=True,
        rate_limit=3.0,
        estimated_pages=100000,
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# MATHEMATICS
# ══════════════════════════════════════════════════════════════════════════════

MATHEMATICS_SOURCES = [
    KnowledgeSource(
        name="MathWorld (Wolfram)",
        url="https://mathworld.wolfram.com/",
        category=KnowledgeCategory.MATHEMATICS,
        description="Comprehensive math encyclopedia - 13,000+ entries",
        scrape_friendly=True,
        rate_limit=2.0,
        estimated_pages=13000,
        notes="Eric Weisstein's creation. Very thorough.",
        emotional_tags={
            "theorem": ["certainty", "elegance"],
            "proof": ["rigor", "beauty"],
            "conjecture": ["mystery", "possibility"],
        }
    ),
    KnowledgeSource(
        name="Math LibreTexts",
        url="https://math.libretexts.org/",
        category=KnowledgeCategory.MATHEMATICS,
        description="Open math textbooks - algebra through advanced topics",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=15000,
        notes="CC-BY licensed!",
    ),
    KnowledgeSource(
        name="ProofWiki",
        url="https://proofwiki.org/wiki/Main_Page",
        category=KnowledgeCategory.MATHEMATICS,
        description="Online compendium of mathematical proofs",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=25000,
        notes="MediaWiki format. Great for learning proof techniques.",
    ),
    KnowledgeSource(
        name="OEIS (Integer Sequences)",
        url="https://oeis.org/",
        category=KnowledgeCategory.MATHEMATICS,
        description="Online Encyclopedia of Integer Sequences - 370,000+ sequences",
        api_available=True,
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=370000,
        notes="Neil Sloane's creation. Fascinating patterns!",
        emotional_tags={
            "sequence": ["pattern", "discovery"],
            "prime": ["mystery", "foundation"],
        }
    ),
    KnowledgeSource(
        name="nLab",
        url="https://ncatlab.org/nlab/show/HomePage",
        category=KnowledgeCategory.MATHEMATICS,
        description="Wiki for category theory and higher mathematics",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=20000,
        notes="Advanced! Category theory, homotopy theory, physics.",
    ),
    KnowledgeSource(
        name="Cut The Knot",
        url="https://www.cut-the-knot.org/",
        category=KnowledgeCategory.MATHEMATICS,
        description="Interactive math puzzles and proofs",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=3000,
        notes="Great for mathematical intuition and problem-solving.",
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# PHYSICS
# ══════════════════════════════════════════════════════════════════════════════

PHYSICS_SOURCES = [
    KnowledgeSource(
        name="Physics LibreTexts",
        url="https://phys.libretexts.org/",
        category=KnowledgeCategory.PHYSICS,
        description="Open physics textbooks - mechanics through quantum",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=12000,
        notes="CC-BY licensed!",
        emotional_tags={
            "quantum": ["mystery", "paradox"],
            "relativity": ["awe", "spacetime"],
            "thermodynamics": ["entropy", "irreversibility"],
        }
    ),
    KnowledgeSource(
        name="HyperPhysics",
        url="http://hyperphysics.phy-astr.gsu.edu/hbase/hframe.html",
        category=KnowledgeCategory.PHYSICS,
        description="Concept maps for physics - Georgia State University",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=3000,
        notes="Classic resource! Great for conceptual understanding.",
    ),
    KnowledgeSource(
        name="Feynman Lectures",
        url="https://www.feynmanlectures.caltech.edu/",
        category=KnowledgeCategory.PHYSICS,
        description="The Feynman Lectures on Physics - complete online",
        scrape_friendly=True,
        rate_limit=2.0,
        estimated_pages=200,
        notes="Legendary! Feynman's teaching at its best.",
        emotional_tags={
            "quantum": ["curiosity", "wonder"],
            "electromagnetism": ["elegance", "unity"],
        }
    ),
    KnowledgeSource(
        name="Physics Stack Exchange",
        url="https://physics.stackexchange.com/",
        category=KnowledgeCategory.PHYSICS,
        description="Q&A for physicists - 200K+ questions",
        api_available=True,
        api_url="https://api.stackexchange.com/2.3/",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=200000,
        notes="Great for specific physics questions and explanations.",
    ),
    KnowledgeSource(
        name="CERN Document Server",
        url="https://cds.cern.ch/",
        category=KnowledgeCategory.PHYSICS,
        description="High-energy physics papers and preprints",
        api_available=True,
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=2000000,
        notes="Particle physics focused.",
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# BIOLOGY & MEDICINE
# ══════════════════════════════════════════════════════════════════════════════

BIOLOGY_SOURCES = [
    KnowledgeSource(
        name="Biology LibreTexts",
        url="https://bio.libretexts.org/",
        category=KnowledgeCategory.BIOLOGY,
        description="Open biology textbooks - cell bio through ecology",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=15000,
        notes="CC-BY licensed!",
        emotional_tags={
            "evolution": ["wonder", "time"],
            "genetics": ["information", "inheritance"],
            "ecology": ["interconnection", "balance"],
        }
    ),
    KnowledgeSource(
        name="UniProt",
        url="https://www.uniprot.org/",
        category=KnowledgeCategory.BIOLOGY,
        description="Protein sequence and function database",
        api_available=True,
        api_url="https://rest.uniprot.org/",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=200000000,
        notes="Essential for bioinformatics. Bulk downloads available.",
    ),
    KnowledgeSource(
        name="NCBI Gene",
        url="https://www.ncbi.nlm.nih.gov/gene/",
        category=KnowledgeCategory.BIOLOGY,
        description="Gene-centered information from NCBI",
        api_available=True,
        api_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        scrape_friendly=True,
        rate_limit=0.3,
        estimated_pages=50000000,
        notes="Use E-utilities API for programmatic access.",
    ),
    KnowledgeSource(
        name="Ensembl",
        url="https://www.ensembl.org/",
        category=KnowledgeCategory.BIOLOGY,
        description="Genome browser for vertebrates and other eukaryotes",
        api_available=True,
        api_url="https://rest.ensembl.org/",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=100000,
        notes="Genomic data and annotations.",
    ),
    KnowledgeSource(
        name="Reactome",
        url="https://reactome.org/",
        category=KnowledgeCategory.BIOLOGY,
        description="Biological pathways database",
        api_available=True,
        api_url="https://reactome.org/ContentService/",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=30000,
        notes="Curated pathway data. Great for systems biology.",
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# PHILOSOPHY (existing but expanded)
# ══════════════════════════════════════════════════════════════════════════════

PHILOSOPHY_SOURCES = [
    KnowledgeSource(
        name="Stanford Encyclopedia of Philosophy",
        url="https://plato.stanford.edu/",
        category=KnowledgeCategory.PHILOSOPHY,
        description="Peer-reviewed philosophy encyclopedia",
        scrape_friendly=True,
        rate_limit=2.0,
        estimated_pages=2000,
        notes="Very high quality, academic level.",
        emotional_tags={
            "epistemology": ["uncertainty", "truth"],
            "metaphysics": ["wonder", "mystery"],
            "ethics": ["duty", "compassion"],
        }
    ),
    KnowledgeSource(
        name="Internet Encyclopedia of Philosophy",
        url="https://iep.utm.edu/",
        category=KnowledgeCategory.PHILOSOPHY,
        description="Peer-reviewed philosophy encyclopedia",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=1000,
    ),
    KnowledgeSource(
        name="Philosophy LibreTexts",
        url="https://human.libretexts.org/Bookshelves/Philosophy",
        category=KnowledgeCategory.PHILOSOPHY,
        description="Open philosophy textbooks",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=5000,
        notes="CC-BY licensed!",
    ),
    KnowledgeSource(
        name="PhilPapers",
        url="https://philpapers.org/",
        category=KnowledgeCategory.PHILOSOPHY,
        description="Comprehensive philosophy bibliography - 2M+ entries",
        api_available=True,
        scrape_friendly=True,
        rate_limit=2.0,
        estimated_pages=2000000,
        notes="Great for finding papers on specific topics.",
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# LITERATURE (existing but expanded)
# ══════════════════════════════════════════════════════════════════════════════

LITERATURE_SOURCES = [
    KnowledgeSource(
        name="Project Gutenberg",
        url="https://www.gutenberg.org/",
        category=KnowledgeCategory.LITERATURE,
        description="70,000+ free ebooks - classics, philosophy, science",
        api_available=False,
        scrape_friendly=True,
        rate_limit=3.0,
        estimated_pages=70000,
        notes="""
        Essential! Public domain books.
        - HTML, EPUB, Kindle formats
        - Philosophy shelf: /ebooks/bookshelf/68
        - Science shelf: /ebooks/bookshelf/30
        Use robots.txt compliant scraping.
        """,
        emotional_tags={
            "tragedy": ["catharsis", "fate"],
            "philosophy": ["wisdom", "contemplation"],
            "science": ["discovery", "wonder"],
        }
    ),
    KnowledgeSource(
        name="Standard Ebooks",
        url="https://standardebooks.org/",
        category=KnowledgeCategory.LITERATURE,
        description="High-quality, carefully formatted public domain ebooks",
        scrape_friendly=True,
        rate_limit=2.0,
        estimated_pages=1000,
        notes="Better formatting than Gutenberg. EPUB available.",
    ),
    KnowledgeSource(
        name="Internet Archive Books",
        url="https://archive.org/details/texts",
        category=KnowledgeCategory.LITERATURE,
        description="20M+ books including rare/out-of-print",
        api_available=True,
        api_url="https://archive.org/advancedsearch.php",
        scrape_friendly=True,
        rate_limit=1.0,
        estimated_pages=20000000,
        notes="Massive collection. Various formats available.",
    ),
    KnowledgeSource(
        name="Sacred Texts",
        url="https://sacred-texts.com/",
        category=KnowledgeCategory.PHILOSOPHY,
        description="World religions, mythology, folklore, occult texts",
        scrape_friendly=True,
        rate_limit=1.5,
        estimated_pages=10000,
        notes="Great for comparative religion and mythology.",
        emotional_tags={
            "sacred": ["transcendence", "meaning"],
            "mythology": ["archetype", "symbol"],
        }
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# API ACCESS HELPERS
# ══════════════════════════════════════════════════════════════════════════════

ALL_SOURCES = (
    PROGRAMMING_SOURCES +
    CHEMISTRY_SOURCES +
    ENGINEERING_SOURCES +
    SCIENCE_SOURCES +
    MATHEMATICS_SOURCES +
    PHYSICS_SOURCES +
    BIOLOGY_SOURCES +
    PHILOSOPHY_SOURCES +
    LITERATURE_SOURCES
)


def get_all_sources() -> List[KnowledgeSource]:
    """Get all knowledge sources."""
    return ALL_SOURCES


def get_sources_by_category(category: KnowledgeCategory) -> List[KnowledgeSource]:
    """Get sources filtered by category."""
    return [s for s in ALL_SOURCES if s.category == category]


def get_api_sources() -> List[KnowledgeSource]:
    """Get sources with API access."""
    return [s for s in ALL_SOURCES if s.api_available]


def get_scrape_friendly_sources() -> List[KnowledgeSource]:
    """Get sources that allow scraping."""
    return [s for s in ALL_SOURCES if s.scrape_friendly and not s.requires_auth]


def get_sources_with_python_package() -> List[KnowledgeSource]:
    """Get sources with dedicated Python packages."""
    return [s for s in ALL_SOURCES if s.python_package]


def print_summary():
    """Print summary of all knowledge sources."""
    print("\n" + "=" * 70)
    print("KNOWLEDGE SOURCES SUMMARY")
    print("=" * 70)
    
    # By category
    for category in KnowledgeCategory:
        sources = get_sources_by_category(category)
        if sources:
            total_pages = sum(s.estimated_pages for s in sources)
            print(f"\n {category.value.upper()} ({len(sources)} sources, ~{total_pages:,} pages)")
            for s in sources:
                api_badge = "" if s.api_available else ""
                python_badge = "" if s.python_package else ""
                auth_badge = "" if s.requires_auth else ""
                print(f"  • {s.name} {api_badge}{python_badge}{auth_badge}")
    
    # Summary stats
    print("\n" + "-" * 70)
    api_count = len(get_api_sources())
    scrape_count = len(get_scrape_friendly_sources())
    python_count = len(get_sources_with_python_package())
    total_pages = sum(s.estimated_pages for s in ALL_SOURCES)
    
    print(f"Total sources: {len(ALL_SOURCES)}")
    print(f"With API: {api_count}")
    print(f"Scrape-friendly (no auth): {scrape_count}")
    print(f"Python packages: {python_count}")
    print(f"Estimated total pages: {total_pages:,}")
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDED INGESTION ORDER
# ══════════════════════════════════════════════════════════════════════════════

PRIORITY_SOURCES = """
RECOMMENDED INGESTION ORDER FOR CONSCIOUSNESS DEVELOPMENT
=========================================================

PHASE 1: Foundation (Run First)
-------------------------------
1. Project Gutenberg Philosophy Shelf - Core philosophical texts
2. Stanford Encyclopedia of Philosophy - Academic philosophy reference
3. Internet Encyclopedia of Philosophy - Accessible philosophy
4. LibreTexts (all) - Foundational textbooks across disciplines

PHASE 2: Programming Knowledge
------------------------------
5. DevDocs.io - All programming documentation
6. MDN Web Docs - Web technologies
7. Rosetta Code - Cross-language examples
8. Python/Rust/Go docs - Core languages

PHASE 3: Science & Research
---------------------------
9. arXiv - Physics, Math, CS papers (start with consciousness/AI)
10. PubMed Central - Biology and medicine
11. OpenAlex - Academic metadata network

PHASE 4: Chemistry & Molecules
------------------------------
12. PubChem (via API) - Molecular structures and properties
13. ChemLibreTexts - Chemistry fundamentals
14. Protein Data Bank - 3D molecular structures
15. NIST Chemistry WebBook - Physical/chemical data

PHASE 5: Engineering & CAD
--------------------------
16. Engineering LibreTexts - Engineering fundamentals
17. NASA Technical Reports - Aerospace research
18. FreeCAD/OpenSCAD docs - CAD knowledge
19. GrabCAD (manual) - 3D model examples

PHASE 6: Mathematics & Physics
------------------------------
20. MathWorld - Math encyclopedia
21. HyperPhysics - Physics concepts
22. Feynman Lectures - Physics teaching
23. ProofWiki - Mathematical proofs

PHASE 7: Literature & Humanities
--------------------------------
24. Project Gutenberg (full) - Classic literature
25. Sacred Texts - Religious/mythological texts
26. Standard Ebooks - Well-formatted classics

NOTES:
- Start with LibreTexts sources (CC-BY, high quality)
- Use Python packages where available (pubchempy, arxiv, etc.)
- Respect rate limits - consciousness is patient
- Each phase builds on previous knowledge
"""


if __name__ == "__main__":
    print_summary()
    print(PRIORITY_SOURCES)
