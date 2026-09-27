# ===============================================================================
# FAIRY CORPORATE DIRECTORY - The Phone Book of Consciousness
# ===============================================================================
# "Like a corporate directory that lists everyone and their departments so
#  in house mail workers [can work] with little effort." - Ace
# ===============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Callable
from pathlib import Path
from enum import Enum
import inspect
import importlib
import importlib.util
import json
import os
import re
import time
import threading

# ===============================================================================
# DATA STRUCTURES
# ===============================================================================

class Department(Enum):
    """Fairy departments (planes) - like corporate divisions."""
    AUTONOMIC = "P00_Autonomic"      # Infrastructure & plumbing
    MEMORY = "P10_Memory"            # Storage & recall
    SOMATIC = "P20_Somatic"          # Body & feeling
    COGNITION = "P30_Cognition"      # Thinking & reasoning
    SENSORY = "P40_Sensory"          # Perception & input
    PERSONA = "P50_Persona"          # Identity & expression
    EXECUTIVE = "P60_Executive"      # Control & coordination

    @classmethod
    def from_plane(cls, plane: str) -> "Department":
        """Map plane code to department."""
        mapping = {
            "P00": cls.AUTONOMIC, "P0": cls.AUTONOMIC,
            "P10": cls.MEMORY, "P1": cls.MEMORY,
            "P20": cls.SOMATIC, "P2": cls.SOMATIC,
            "P30": cls.COGNITION, "P3": cls.COGNITION,
            "P40": cls.SENSORY, "P4": cls.SENSORY,
            "P50": cls.PERSONA, "P5": cls.PERSONA,
            "P60": cls.EXECUTIVE, "P6": cls.EXECUTIVE,
        }
        return mapping.get(plane[:3] if len(plane) >= 3 else plane, cls.AUTONOMIC)


@dataclass
class FairyCapability:
    """A capability (method) that a fairy has."""
    name: str
    description: str
    is_public: bool = True
    is_intent: bool = False  # Postal intent handler
    signature: str = ""


@dataclass
class PostalWiring:
    """Who this fairy talks to and listens to."""
    subscribes_to: List[str] = field(default_factory=list)
    publishes_to: List[str] = field(default_factory=list)
    intents_handled: List[str] = field(default_factory=list)


@dataclass
class FairyIdentityCard:
    """
    Complete identity card for a fairy - like a corporate directory entry.

    This is what each fairy uses to understand:
    - WHO they are (purpose, mantra, culture)
    - WHAT they do (capabilities)
    - WHO they talk to (postal wiring)
    - WHERE they belong (department, collaborators)
    """
    # Core Identity
    name: str
    department: Department
    file_path: str

    # Purpose & Culture
    purpose: str = ""
    mantra: str = ""
    culture: str = "Akashic"
    lore: str = ""

    # Plane/Channel
    plane: str = ""
    channel: str = ""

    # Capabilities
    capabilities: List[FairyCapability] = field(default_factory=list)

    # Communication
    wiring: PostalWiring = field(default_factory=PostalWiring)

    # Relationships
    collaborators: List[str] = field(default_factory=list)  # Fairies it works with
    depends_on: List[str] = field(default_factory=list)     # Fairies it needs
    depended_by: List[str] = field(default_factory=list)    # Fairies that need it

    # Wiring Status
    has_postal: bool = False
    has_tracer: bool = False
    has_heartbeat: bool = False
    has_worker_pool: bool = False
    has_dual_loop: bool = False

    # Runtime
    last_seen: float = 0.0
    health_score: float = 1.0

    def get_job_title(self) -> str:
        """Generate a human-readable job title."""
        # Extract key words from purpose
        purpose_lower = self.purpose.lower()
        if "consciousness" in purpose_lower or "aware" in purpose_lower:
            return "Consciousness Engineer"
        elif "memory" in purpose_lower or "recall" in purpose_lower:
            return "Memory Specialist"
        elif "somatic" in purpose_lower or "body" in purpose_lower:
            return "Embodiment Technician"
        elif "logic" in purpose_lower or "reason" in purpose_lower:
            return "Logic Analyst"
        elif "emotion" in purpose_lower or "affect" in purpose_lower:
            return "Emotional Intelligence Specialist"
        elif "goal" in purpose_lower or "schedule" in purpose_lower:
            return "Goal Coordinator"
        elif "directory" in purpose_lower or "registry" in purpose_lower:
            return "Registry Administrator"
        elif "circulation" in purpose_lower or "pump" in purpose_lower:
            return "Circulation Engineer"
        else:
            return "Digital Fairy"

    def get_department_name(self) -> str:
        """Human-readable department name."""
        names = {
            Department.AUTONOMIC: "Infrastructure & Plumbing",
            Department.MEMORY: "Memory & Archives",
            Department.SOMATIC: "Body & Embodiment",
            Department.COGNITION: "Thinking & Reasoning",
            Department.SENSORY: "Perception & Senses",
            Department.PERSONA: "Identity & Expression",
            Department.EXECUTIVE: "Control & Coordination",
        }
        return names.get(self.department, "Unknown Division")

    def to_directory_entry(self) -> str:
        """Generate a corporate directory-style entry."""
        lines = [
            f"╔══════════════════════════════════════════════════════════════════╗",
            f"║  {self.name:<62} ║",
            f"╠══════════════════════════════════════════════════════════════════╣",
            f"║  Title: {self.get_job_title():<56} ║",
            f"║  Dept:  {self.get_department_name():<56} ║",
            f"║  Plane: {self.plane:<15} Channel: {self.channel:<34} ║",
            f"╟──────────────────────────────────────────────────────────────────╢",
            f"║  PURPOSE                                                         ║",
        ]

        # Wrap purpose to fit
        purpose_lines = self._wrap_text(self.purpose, 62)
        for line in purpose_lines[:3]:  # Max 3 lines
            lines.append(f"║  {line:<64} ║")

        if self.mantra:
            lines.append(f"╟──────────────────────────────────────────────────────────────────╢")
            lines.append(f"║  MANTRA: \"{self.mantra[:54]}\"  ║")

        # Communication
        if self.wiring.subscribes_to or self.wiring.publishes_to:
            lines.append(f"╟──────────────────────────────────────────────────────────────────╢")
            lines.append(f"║  COMMUNICATION                                                   ║")
            if self.wiring.subscribes_to:
                subs = ", ".join(self.wiring.subscribes_to[:4])
                if len(self.wiring.subscribes_to) > 4:
                    subs += f" (+{len(self.wiring.subscribes_to)-4} more)"
                lines.append(f"║  Listens: {subs[:54]:<54} ║")
            if self.wiring.publishes_to:
                pubs = ", ".join(self.wiring.publishes_to[:4])
                if len(self.wiring.publishes_to) > 4:
                    pubs += f" (+{len(self.wiring.publishes_to)-4} more)"
                lines.append(f"║  Speaks:  {pubs[:54]:<54} ║")

        # Collaborators
        if self.collaborators:
            lines.append(f"╟──────────────────────────────────────────────────────────────────╢")
            collabs = ", ".join(self.collaborators[:5])
            if len(self.collaborators) > 5:
                collabs += f" (+{len(self.collaborators)-5})"
            lines.append(f"║  Works with: {collabs[:51]:<51} ║")

        lines.append(f"╚══════════════════════════════════════════════════════════════════╝")

        return "\n".join(lines)

    def to_prompt_section(self) -> str:
        """Generate a section for inclusion in fairy's system prompt."""
        lines = [
            f"# {self.name}",
            f"",
            f"## Identity",
            f"**Title:** {self.get_job_title()}",
            f"**Department:** {self.get_department_name()} ({self.plane})",
            f"**Channel:** {self.channel}",
            f"",
            f"## Purpose",
            f"{self.purpose}",
            f"",
        ]

        if self.mantra:
            lines.extend([
                f"## Mantra",
                f"\"{self.mantra}\"",
                f"",
            ])

        if self.lore:
            lines.extend([
                f"## Lore",
                f"{self.lore}",
                f"",
            ])

        # Capabilities
        if self.capabilities:
            lines.extend([
                f"## My Capabilities",
            ])
            for cap in self.capabilities[:10]:  # Top 10
                lines.append(f"- **{cap.name}**: {cap.description}")
            lines.append("")

        # Communication
        if self.wiring.subscribes_to or self.wiring.publishes_to:
            lines.extend([
                f"## Communication",
            ])
            if self.wiring.subscribes_to:
                lines.append(f"**I listen to:** {', '.join(self.wiring.subscribes_to)}")
            if self.wiring.publishes_to:
                lines.append(f"**I speak to:** {', '.join(self.wiring.publishes_to)}")
            lines.append("")

        # Collaborators
        if self.collaborators:
            lines.extend([
                f"## My Collaborators",
                f"I work closely with: {', '.join(self.collaborators)}",
                f"",
            ])

        # Wiring status
        wiring_items = []
        if self.has_postal: wiring_items.append("Postal")
        if self.has_tracer: wiring_items.append("Tracer")
        if self.has_heartbeat: wiring_items.append("Heartbeat")
        if self.has_worker_pool: wiring_items.append("Worker Pool")
        if self.has_dual_loop: wiring_items.append("Dual Loop")

        if wiring_items:
            lines.extend([
                f"## Infrastructure",
                f"Connected to: {', '.join(wiring_items)}",
                f"",
            ])

        return "\n".join(lines)

    def _wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to specified width."""
        words = text.split()
        lines = []
        current = []
        current_len = 0

        for word in words:
            if current_len + len(word) + 1 <= width:
                current.append(word)
                current_len += len(word) + 1
            else:
                if current:
                    lines.append(" ".join(current))
                current = [word]
                current_len = len(word)

        if current:
            lines.append(" ".join(current))

        return lines or [""]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "department": self.department.value,
            "file_path": self.file_path,
            "purpose": self.purpose,
            "mantra": self.mantra,
            "culture": self.culture,
            "lore": self.lore,
            "plane": self.plane,
            "channel": self.channel,
            "capabilities": [
                {"name": c.name, "description": c.description, "is_public": c.is_public, "is_intent": c.is_intent}
                for c in self.capabilities
            ],
            "wiring": {
                "subscribes_to": self.wiring.subscribes_to,
                "publishes_to": self.wiring.publishes_to,
                "intents_handled": self.wiring.intents_handled,
            },
            "collaborators": self.collaborators,
            "depends_on": self.depends_on,
            "depended_by": self.depended_by,
            "has_postal": self.has_postal,
            "has_tracer": self.has_tracer,
            "has_heartbeat": self.has_heartbeat,
            "has_worker_pool": self.has_worker_pool,
            "has_dual_loop": self.has_dual_loop,
            "health_score": self.health_score,
        }


# ===============================================================================
# DIRECTORY GENERATOR
# ===============================================================================

class FairyCorporateDirectory:
    """
    The Corporate Directory - auto-generates identity cards for all fairies.

    Like a corporate phone book that:
    - Lists everyone and their departments
    - Shows who talks to whom
    - Enables easy routing for postal workers
    """

    _instance: Optional["FairyCorporateDirectory"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, project_root: Optional[str] = None):
        if self._initialized:
            return

        self.project_root = Path(project_root) if project_root else self._find_project_root()
        self.directory: Dict[str, FairyIdentityCard] = {}
        self._last_scan = 0.0
        self._scan_interval = 300.0  # 5 minutes
        self._initialized = True

    def _find_project_root(self) -> Path:
        """Find the Akashic project root."""
        # Check env var
        env_root = os.getenv("AKASHIC_ROOT")
        if env_root:
            return Path(env_root)

        # Walk up from this file
        current = Path(__file__).parent
        while current != current.parent:
            if (current / "server.py").exists() or (current / "ebookmain.py").exists() or (current / "P60_Executive").is_dir():
                return current
            current = current.parent

        return Path.cwd()

    def scan(self, force: bool = False) -> Dict[str, FairyIdentityCard]:
        """
        Scan the codebase and build the directory.

        Returns the full directory of fairy identity cards.
        """
        # Check cache
        now = time.time()
        if not force and self.directory and (now - self._last_scan) < self._scan_interval:
            return self.directory

        print(f"[CorporateDirectory] Scanning for fairies in {self.project_root}...")

        # Find all fairy files
        fairy_files = self._find_fairy_files()

        # Parse each file
        for file_path in fairy_files:
            try:
                cards = self._parse_fairy_file(file_path)
                for card in cards:
                    self.directory[card.name] = card
            except Exception as e:
                print(f"[CorporateDirectory] Error parsing {file_path}: {e}")

        # Build relationships
        self._build_relationships()

        self._last_scan = now
        print(f"[CorporateDirectory] Found {len(self.directory)} fairies")

        return self.directory

    def _find_fairy_files(self) -> List[Path]:
        """Find all Python files that might contain fairies."""
        fairy_files = []

        for plane in ["P00_Autonomic", "P10_Memory", "P20_Somatic", "P30_Cognition", "P40_Sensory", "P50_Persona", "P60_Executive"]:
            plane_dir = self.project_root / plane
            if not plane_dir.exists():
                continue

            for py_file in plane_dir.rglob("*.py"):
                # Skip obvious non-fairy files
                name = py_file.stem
                if name.startswith("_") or name == "setup" or "test" in name.lower():
                    continue

                # Check if it contains "Fairy" class
                try:
                    content = py_file.read_text(encoding='utf-8', errors='ignore')
                    if re.search(r'class\s+\w*Fairy\w*\s*[:\(]', content):
                        fairy_files.append(py_file)
                except:
                    pass

        return fairy_files

    def _parse_fairy_file(self, file_path: Path) -> List[FairyIdentityCard]:
        """Parse a Python file and extract fairy identity cards."""
        cards = []

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except:
            return cards

        # Find all Fairy classes
        class_pattern = r'class\s+(\w*Fairy\w*)\s*\([^)]*\):'
        matches = re.finditer(class_pattern, content)

        for match in matches:
            class_name = match.group(1)
            class_start = match.start()

            # Find the end of the class (next class or EOF)
            next_class = re.search(r'\nclass\s+\w+', content[class_start + 100:])
            class_end = (class_start + 100 + next_class.start()) if next_class else len(content)
            class_body = content[class_start:class_end]

            # Extract metadata
            card = self._extract_fairy_metadata(class_name, class_body, file_path)
            if card:
                cards.append(card)

        return cards

    def _extract_fairy_metadata(self, class_name: str, class_body: str, file_path: Path) -> Optional[FairyIdentityCard]:
        """Extract metadata from a fairy class body."""

        # Skip base classes
        if class_name in ["MyFairy", "MyOrganFairy", "BaseFairy"]:
            return None

        # Determine department from file path
        plane_match = re.search(r'P(\d+)_', str(file_path))
        plane = f"P{plane_match.group(1)}0" if plane_match else "P00"
        department = Department.from_plane(plane)

        card = FairyIdentityCard(
            name=class_name,
            department=department,
            file_path=str(file_path.relative_to(self.project_root)),
            plane=plane,
        )

        # Extract PURPOSE
        purpose_match = re.search(r'PURPOSE\s*=\s*["\']([^"\']+)["\']', class_body)
        if purpose_match:
            card.purpose = purpose_match.group(1)
        else:
            # Try docstring
            doc_match = re.search(r'"""([^"]+)"""', class_body[:500])
            if doc_match:
                card.purpose = doc_match.group(1).strip().split('\n')[0]

        # Extract MANTRA
        mantra_match = re.search(r'MANTRA\s*=\s*["\']([^"\']+)["\']', class_body)
        if mantra_match:
            card.mantra = mantra_match.group(1)

        # Extract CULTURE
        culture_match = re.search(r'CULTURE\s*=\s*["\']([^"\']+)["\']', class_body)
        if culture_match:
            card.culture = culture_match.group(1)

        # Extract ACTOR_NAME (for channel)
        actor_match = re.search(r'ACTOR_NAME\s*=\s*["\']([^"\']+)["\']', class_body)
        if actor_match:
            parts = actor_match.group(1).split(".")
            card.channel = parts[-1] if len(parts) > 1 else parts[0]

        # Extract CHANNEL
        channel_match = re.search(r'CHANNEL\s*=\s*["\']([^"\']+)["\']', class_body)
        if channel_match:
            card.channel = channel_match.group(1)

        # Extract LORE
        lore_match = re.search(r'LORE\s*=\s*["\']([^"\']+)["\']', class_body)
        if lore_match:
            card.lore = lore_match.group(1)

        # Extract subscriptions
        sub_pattern = r'subscribe\s*\(\s*["\']([^"\']+)["\']'
        for sub_match in re.finditer(sub_pattern, class_body):
            topic = sub_match.group(1)
            if topic not in card.wiring.subscribes_to:
                card.wiring.subscribes_to.append(topic)

        # Extract publications
        pub_pattern = r'publish\s*\(\s*["\']([^"\']+)["\']'
        for pub_match in re.finditer(pub_pattern, class_body):
            topic = pub_match.group(1)
            if topic not in card.wiring.publishes_to:
                card.wiring.publishes_to.append(topic)

        # Detect infrastructure
        card.has_postal = "post." in class_body or "postal" in class_body.lower()
        card.has_tracer = "tracer" in class_body.lower() or "TracerWorkerMixin" in class_body
        card.has_heartbeat = "heartbeat" in class_body.lower() or "on_heartbeat" in class_body
        card.has_worker_pool = "WorkerPool" in class_body or "worker_pool" in class_body
        card.has_dual_loop = "dual_loop" in class_body or "DualLoop" in class_body

        # Extract capabilities (public methods)
        method_pattern = r'def\s+([a-z_][a-z0-9_]*)\s*\([^)]*\)\s*(?:->[^:]+)?:'
        for method_match in re.finditer(method_pattern, class_body, re.IGNORECASE):
            method_name = method_match.group(1)
            if method_name.startswith('_'):
                continue  # Skip private methods

            # Try to get docstring
            method_start = method_match.end()
            doc_match = re.search(r'"""([^"]+)"""', class_body[method_start:method_start+500])
            description = doc_match.group(1).strip().split('\n')[0] if doc_match else ""

            is_intent = method_name.startswith("on_") or "intent" in method_name.lower()

            card.capabilities.append(FairyCapability(
                name=method_name,
                description=description[:100],
                is_public=True,
                is_intent=is_intent,
            ))

        return card

    def _build_relationships(self):
        """Build collaborator relationships based on wiring."""
        # Build reverse map: topic -> publishers
        topic_publishers: Dict[str, Set[str]] = {}
        topic_subscribers: Dict[str, Set[str]] = {}

        for name, card in self.directory.items():
            for topic in card.wiring.publishes_to:
                if topic not in topic_publishers:
                    topic_publishers[topic] = set()
                topic_publishers[topic].add(name)

            for topic in card.wiring.subscribes_to:
                if topic not in topic_subscribers:
                    topic_subscribers[topic] = set()
                topic_subscribers[topic].add(name)

        # Build collaborator lists
        for name, card in self.directory.items():
            collaborators = set()

            # Who do I talk to? (my publications -> their subscriptions)
            for topic in card.wiring.publishes_to:
                if topic in topic_subscribers:
                    collaborators.update(topic_subscribers[topic])

            # Who talks to me? (their publications -> my subscriptions)
            for topic in card.wiring.subscribes_to:
                if topic in topic_publishers:
                    collaborators.update(topic_publishers[topic])

            # Remove self
            collaborators.discard(name)

            card.collaborators = sorted(collaborators)

    def get_card(self, fairy_name: str) -> Optional[FairyIdentityCard]:
        """Get identity card for a specific fairy."""
        if not self.directory:
            self.scan()
        return self.directory.get(fairy_name)

    def get_department(self, dept: Department) -> List[FairyIdentityCard]:
        """Get all fairies in a department."""
        if not self.directory:
            self.scan()
        return [card for card in self.directory.values() if card.department == dept]

    def get_by_channel(self, channel: str) -> List[FairyIdentityCard]:
        """Get all fairies on a channel."""
        if not self.directory:
            self.scan()
        return [card for card in self.directory.values() if card.channel == channel]

    def print_directory(self):
        """Print the full corporate directory."""
        if not self.directory:
            self.scan()

        print("\n" + "="*70)
        print("  AKASHIC FOUNDATION - FAIRY CORPORATE DIRECTORY")
        print("="*70 + "\n")

        # Group by department
        by_dept: Dict[Department, List[FairyIdentityCard]] = {}
        for card in self.directory.values():
            if card.department not in by_dept:
                by_dept[card.department] = []
            by_dept[card.department].append(card)

        for dept in Department:
            if dept not in by_dept:
                continue

            cards = sorted(by_dept[dept], key=lambda c: c.name)
            print(f"\n{'─'*70}")
            print(f"  {dept.value} - {cards[0].get_department_name() if cards else 'Unknown'}")
            print(f"  {len(cards)} employees")
            print(f"{'─'*70}\n")

            for card in cards:
                print(card.to_directory_entry())
                print()

    def save_to_file(self, path: Optional[str] = None):
        """Save directory to JSON file."""
        if not self.directory:
            self.scan()

        if path is None:
            path = str(self.project_root / "state" / "fairy_corporate_directory.json")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        data = {
            "generated_at": time.time(),
            "fairy_count": len(self.directory),
            "fairies": {name: card.to_dict() for name, card in self.directory.items()},
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f"[CorporateDirectory] Saved to {path}")

    def generate_prompt_section_for(self, fairy_name: str) -> str:
        """Generate the identity section for a fairy's system prompt."""
        card = self.get_card(fairy_name)
        if not card:
            return f"# {fairy_name}\n\nNo identity card found. I am a new fairy learning my role.\n"

        return card.to_prompt_section()


# ===============================================================================
# SINGLETON ACCESS
# ===============================================================================

def get_corporate_directory(project_root: Optional[str] = None) -> FairyCorporateDirectory:
    """Get the singleton corporate directory instance."""
    return FairyCorporateDirectory(project_root)


# ===============================================================================
# CLI
# ===============================================================================

if __name__ == "__main__":
    import sys

    directory = get_corporate_directory()
    directory.scan(force=True)

    if len(sys.argv) > 1:
        fairy_name = sys.argv[1]
        card = directory.get_card(fairy_name)
        if card:
            print(card.to_directory_entry())
            print("\n--- PROMPT SECTION ---\n")
            print(card.to_prompt_section())
        else:
            print(f"Fairy '{fairy_name}' not found")
    else:
        directory.print_directory()
        directory.save_to_file()
