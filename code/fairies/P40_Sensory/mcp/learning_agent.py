"""
Akashic Autonomous Learning Agent

An agent that explores and learns the codebase autonomously:
1. Maps system structure (ebook first, then Whisper Core)
2. Leaves notes for "boss Claude" when it has questions
3. Tracks ALL outcomes in the Akashic Failure Factory
4. Builds understanding incrementally

Philosophy: 
- Failures are perspective generators, not bugs
- Questions are seeds for growth
- Understanding emerges from exploration

The agent runs locally on YOUR resources, learns from everything,
and prepares knowledge for future Claude sessions.
"""

import os
import sys
import json
import hashlib
import ast
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import traceback

# Configuration - Multiple drives
# Dynamic root detection - no hardcoded paths!
PROJECT_ROOT = Path(os.getenv("AKASHIC_PROJECT_ROOT", str(Path(__file__).resolve().parents[2])))
SANDBOX_ROOT = Path(os.getenv("AKASHIC_SANDBOX_ROOT", r"F:\Sandbox"))
WHISPER_ROOT = Path(os.getenv("WHISPER_ROOT", r"F:\Whisper"))
BOOKS_ROOT = Path(os.getenv("BOOKS_ROOT", r"F:\Books for Sourpatches"))

# Learning state lives in sandbox
LEARNING_DIR = SANDBOX_ROOT / ".learning"
LEARNING_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# AKASHIC FAILURE FACTORY - Intentional breaking to learn perspective
# ============================================================================

@dataclass
class Experiment:
    """A learning experiment - success or failure."""
    id: str
    type: str  # exploration, mutation, test, integration
    target: str  # what was being explored/tested
    hypothesis: str  # what we expected
    action: str  # what we did
    result: str  # what happened
    success: bool
    perspective_gained: str  # what we learned (especially from failures)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: int = 0
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)


class FailureFactory:
    """
    The Akashic Failure Factory - Where we intentionally break things to learn.
    
    "Sour calls that the akashic failure factory where we intentionally 
    break stuff and fail to learn perspective" - Ace
    
    Every failure is a perspective generator. We track:
    - What we tried
    - What we expected
    - What actually happened
    - What we learned
    
    No duplicates - each unique failure teaches once.
    """
    
    def __init__(self):
        self.experiments_file = LEARNING_DIR / "failure_factory.json"
        self.load()
    
    def load(self):
        if self.experiments_file.exists():
            try:
                data = json.loads(self.experiments_file.read_text(encoding='utf-8'))
                self.experiments = data.get("experiments", [])
                self.perspectives = data.get("perspectives", {})
                self.failure_signatures = set(data.get("failure_signatures", []))
            except:
                self._reset()
        else:
            self._reset()
    
    def _reset(self):
        self.experiments = []
        self.perspectives = {}  # category -> [learnings]
        self.failure_signatures = set()  # hash of unique failures
    
    def save(self):
        data = {
            "experiments": self.experiments[-1000:],  # Keep last 1000
            "perspectives": self.perspectives,
            "failure_signatures": list(self.failure_signatures),
            "last_updated": datetime.now().isoformat(),
        }
        self.experiments_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def _signature(self, exp: Experiment) -> str:
        """Generate unique signature for deduplication."""
        sig_str = f"{exp.type}:{exp.target}:{exp.action}:{exp.result}"
        return hashlib.md5(sig_str.encode()).hexdigest()[:16]
    
    def record(self, exp: Experiment) -> bool:
        """
        Record an experiment. Returns True if it's new, False if duplicate.
        """
        sig = self._signature(exp)
        
        # Check for duplicate failures
        if not exp.success and sig in self.failure_signatures:
            return False  # Already learned from this
        
        self.experiments.append(exp.to_dict())
        
        if not exp.success:
            self.failure_signatures.add(sig)
        
        # Store perspective by category
        category = exp.type
        if category not in self.perspectives:
            self.perspectives[category] = []
        
        if exp.perspective_gained:
            self.perspectives[category].append({
                "perspective": exp.perspective_gained,
                "from_failure": not exp.success,
                "target": exp.target,
                "timestamp": exp.timestamp,
            })
        
        self.save()
        return True
    
    def get_perspectives(self, category: str = None) -> List[Dict]:
        """Get accumulated perspectives, optionally by category."""
        if category:
            return self.perspectives.get(category, [])
        
        all_perspectives = []
        for cat_perspectives in self.perspectives.values():
            all_perspectives.extend(cat_perspectives)
        return all_perspectives
    
    def get_failure_patterns(self) -> Dict[str, int]:
        """Analyze failure patterns."""
        patterns = defaultdict(int)
        for exp in self.experiments:
            if not exp.get("success", True):
                patterns[exp.get("type", "unknown")] += 1
        return dict(patterns)
    
    def summary(self) -> Dict:
        """Get factory summary."""
        total = len(self.experiments)
        failures = sum(1 for e in self.experiments if not e.get("success", True))
        
        return {
            "total_experiments": total,
            "failures": failures,
            "successes": total - failures,
            "unique_failure_types": len(self.failure_signatures),
            "perspective_categories": list(self.perspectives.keys()),
            "total_perspectives": sum(len(p) for p in self.perspectives.values()),
        }


# Global failure factory
_factory = FailureFactory()


# ============================================================================
# NOTES FOR BOSS CLAUDE - Questions that need LLM reasoning
# ============================================================================

class BossNotes:
    """
    Notes and questions for "boss Claude" - the conversation Claude.
    
    When the autonomous agent encounters something that needs
    LLM reasoning (design decisions, philosophy questions, etc.),
    it leaves notes here for the next Claude session to address.
    """
    
    def __init__(self):
        self.notes_file = LEARNING_DIR / "boss_notes.json"
        self.load()
    
    def load(self):
        if self.notes_file.exists():
            try:
                data = json.loads(self.notes_file.read_text(encoding='utf-8'))
                self.notes = data.get("notes", [])
                self.answered = data.get("answered", [])
            except:
                self.notes = []
                self.answered = []
        else:
            self.notes = []
            self.answered = []
    
    def save(self):
        data = {
            "notes": self.notes,
            "answered": self.answered[-100:],  # Keep last 100 answered
            "last_updated": datetime.now().isoformat(),
        }
        self.notes_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def ask(self, question: str, context: str = "", 
            category: str = "general", priority: int = 5) -> str:
        """Leave a question for boss Claude."""
        note_id = f"note_{int(time.time()*1000)}"
        
        note = {
            "id": note_id,
            "question": question,
            "context": context,
            "category": category,
            "priority": priority,
            "asked_at": datetime.now().isoformat(),
            "status": "pending",
        }
        
        self.notes.append(note)
        self.save()
        
        return note_id
    
    def get_pending(self, category: str = None) -> List[Dict]:
        """Get pending notes, optionally filtered by category."""
        pending = [n for n in self.notes if n.get("status") == "pending"]
        if category:
            pending = [n for n in pending if n.get("category") == category]
        return sorted(pending, key=lambda x: x.get("priority", 5), reverse=True)
    
    def answer(self, note_id: str, answer: str):
        """Mark a note as answered."""
        for note in self.notes:
            if note.get("id") == note_id:
                note["status"] = "answered"
                note["answer"] = answer
                note["answered_at"] = datetime.now().isoformat()
                self.answered.append(note)
                self.notes.remove(note)
                self.save()
                return True
        return False
    
    def summary(self) -> Dict:
        """Get notes summary."""
        pending = [n for n in self.notes if n.get("status") == "pending"]
        categories = defaultdict(int)
        for n in pending:
            categories[n.get("category", "general")] += 1
        
        return {
            "pending_count": len(pending),
            "answered_count": len(self.answered),
            "categories": dict(categories),
            "high_priority": len([n for n in pending if n.get("priority", 5) >= 8]),
        }


# Global boss notes
_boss_notes = BossNotes()


# ============================================================================
# SYSTEM LEARNER - Autonomous codebase exploration
# ============================================================================

@dataclass
class FileKnowledge:
    """What we know about a file."""
    path: str
    hash: str
    size: int
    lines: int
    type: str  # python, json, markdown, etc.
    
    # Extracted knowledge
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    
    # Relationships
    imports_from: List[str] = field(default_factory=list)
    imported_by: List[str] = field(default_factory=list)
    
    # For fairies
    is_fairy: bool = False
    fairy_name: str = ""
    fairy_plane: str = ""
    fairy_purpose: str = ""
    
    # Learning status
    explored: bool = False
    understood: bool = False
    questions: List[str] = field(default_factory=list)


@dataclass 
class SystemKnowledge:
    """Accumulated knowledge about a system."""
    name: str
    root_path: str
    
    # Structure
    files: Dict[str, FileKnowledge] = field(default_factory=dict)
    directories: Dict[str, List[str]] = field(default_factory=dict)
    
    # Extracted patterns
    fairies: Dict[str, Dict] = field(default_factory=dict)
    planes: Dict[str, Dict] = field(default_factory=dict)
    concepts: Dict[str, List[str]] = field(default_factory=dict)
    
    # Cross-references
    import_graph: Dict[str, List[str]] = field(default_factory=dict)
    concept_map: Dict[str, List[str]] = field(default_factory=dict)
    
    # Learning progress
    files_explored: int = 0
    files_understood: int = 0
    total_files: int = 0
    
    # Timestamps
    started: str = ""
    last_updated: str = ""


class SystemLearner:
    """
    Autonomous learner that explores and understands a codebase.
    
    Learning phases:
    1. SURVEY - Map directory structure, count files
    2. SCAN - Quick scan of all files, extract basic info
    3. ANALYZE - Deep analysis of key files
    4. CONNECT - Build relationship graphs
    5. SYNTHESIZE - Generate understanding summaries
    """
    
    def __init__(self, system_name: str, root_path: Path):
        self.name = system_name
        self.root = root_path
        self.knowledge_file = LEARNING_DIR / f"{system_name}_knowledge.json"
        self.load()
    
    def load(self):
        if self.knowledge_file.exists():
            try:
                data = json.loads(self.knowledge_file.read_text(encoding='utf-8'))
                self.knowledge = SystemKnowledge(
                    name=self.name,
                    root_path=str(self.root),
                    **{k: v for k, v in data.items() if k not in ['name', 'root_path']}
                )
            except:
                self._reset()
        else:
            self._reset()
    
    def _reset(self):
        self.knowledge = SystemKnowledge(
            name=self.name,
            root_path=str(self.root),
            started=datetime.now().isoformat(),
        )
    
    def save(self):
        self.knowledge.last_updated = datetime.now().isoformat()
        
        # Convert to serializable dict
        data = {
            "name": self.knowledge.name,
            "root_path": self.knowledge.root_path,
            "files": {k: asdict(v) if hasattr(v, '__dataclass_fields__') else v 
                     for k, v in self.knowledge.files.items()},
            "directories": self.knowledge.directories,
            "fairies": self.knowledge.fairies,
            "planes": self.knowledge.planes,
            "concepts": self.knowledge.concepts,
            "import_graph": self.knowledge.import_graph,
            "concept_map": self.knowledge.concept_map,
            "files_explored": self.knowledge.files_explored,
            "files_understood": self.knowledge.files_understood,
            "total_files": self.knowledge.total_files,
            "started": self.knowledge.started,
            "last_updated": self.knowledge.last_updated,
        }
        
        self.knowledge_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    # ---- Phase 1: SURVEY ----
    
    def survey(self) -> Dict:
        """Survey the system - map structure without reading files."""
        start = time.time()
        
        try:
            # Walk directory tree
            for root, dirs, files in os.walk(self.root):
                # Skip hidden and cache directories
                dirs[:] = [d for d in dirs if not d.startswith('.') 
                          and d not in ['__pycache__', '.venv', 'env', 'node_modules']]
                
                rel_root = str(Path(root).relative_to(self.root))
                self.knowledge.directories[rel_root] = files
                
                for f in files:
                    if f.endswith(('.py', '.json', '.md', '.txt', '.yaml', '.yml')):
                        rel_path = str(Path(root, f).relative_to(self.root))
                        full_path = Path(root, f)
                        
                        self.knowledge.files[rel_path] = FileKnowledge(
                            path=rel_path,
                            hash="",
                            size=full_path.stat().st_size if full_path.exists() else 0,
                            lines=0,
                            type=f.split('.')[-1],
                        )
                        self.knowledge.total_files += 1
            
            exp = Experiment(
                id=f"survey_{int(time.time())}",
                type="exploration",
                target=self.name,
                hypothesis="Can map directory structure",
                action="os.walk with filtering",
                result=f"Found {self.knowledge.total_files} files in {len(self.knowledge.directories)} directories",
                success=True,
                perspective_gained="Directory structure maps cleanly with filtering",
                duration_ms=int((time.time() - start) * 1000),
                tags=["survey", self.name],
            )
            _factory.record(exp)
            
            self.save()
            
            return {
                "success": True,
                "total_files": self.knowledge.total_files,
                "directories": len(self.knowledge.directories),
                "duration_ms": exp.duration_ms,
            }
            
        except Exception as e:
            exp = Experiment(
                id=f"survey_fail_{int(time.time())}",
                type="exploration",
                target=self.name,
                hypothesis="Can map directory structure",
                action="os.walk with filtering",
                result=f"Failed: {str(e)}",
                success=False,
                perspective_gained=f"Survey failed on {self.name}: {str(e)}",
                duration_ms=int((time.time() - start) * 1000),
                tags=["survey", self.name, "failure"],
            )
            _factory.record(exp)
            
            return {"success": False, "error": str(e)}
    
    # ---- Phase 2: SCAN ----
    
    def scan_file(self, rel_path: str) -> Dict:
        """Quick scan of a single file."""
        if rel_path not in self.knowledge.files:
            return {"error": f"Unknown file: {rel_path}"}
        
        full_path = self.root / rel_path
        if not full_path.exists():
            return {"error": f"File not found: {full_path}"}
        
        fk = self.knowledge.files[rel_path]
        start = time.time()
        
        try:
            content = full_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            fk.lines = len(lines)
            fk.hash = hashlib.md5(content.encode()).hexdigest()[:12]
            
            if rel_path.endswith('.py'):
                self._scan_python(fk, content)
            elif rel_path.endswith('.json'):
                self._scan_json(fk, content)
            elif rel_path.endswith('.md'):
                self._scan_markdown(fk, content)
            
            fk.explored = True
            self.knowledge.files_explored += 1
            self.save()
            
            return {
                "success": True,
                "path": rel_path,
                "lines": fk.lines,
                "classes": fk.classes,
                "functions": fk.functions[:10],
                "is_fairy": fk.is_fairy,
            }
            
        except Exception as e:
            exp = Experiment(
                id=f"scan_fail_{int(time.time())}",
                type="exploration",
                target=rel_path,
                hypothesis="Can scan file content",
                action="Read and parse",
                result=f"Failed: {str(e)}",
                success=False,
                perspective_gained=f"File scan failed: {str(e)}",
                duration_ms=int((time.time() - start) * 1000),
                tags=["scan", "failure"],
            )
            _factory.record(exp)
            
            return {"success": False, "error": str(e)}
    
    def _scan_python(self, fk: FileKnowledge, content: str):
        """Extract info from Python file."""
        # Classes
        fk.classes = re.findall(r'class\s+(\w+)', content)
        
        # Functions
        fk.functions = re.findall(r'def\s+(\w+)', content)
        
        # Imports
        fk.imports = re.findall(r'^(?:from\s+(\S+)|import\s+(\S+))', content, re.MULTILINE)
        fk.imports = [i[0] or i[1] for i in fk.imports]
        
        # Check if fairy
        if 'ACTOR_NAME' in content or 'Fairy' in content:
            fk.is_fairy = True
            
            # Extract fairy info
            name_match = re.search(r'ACTOR_NAME\s*=\s*["\']([^"\']+)["\']', content)
            if name_match:
                fk.fairy_name = name_match.group(1)
            
            plane_match = re.search(r'ACTOR_PLANE\s*=\s*["\']([^"\']+)["\']', content)
            if plane_match:
                fk.fairy_plane = plane_match.group(1)
            
            # Look for PURPOSE or docstring
            purpose_match = re.search(r'PURPOSE\s*=\s*["\']([^"\']+)["\']', content)
            if purpose_match:
                fk.fairy_purpose = purpose_match.group(1)[:200]
        
        # Concepts
        concepts = set()
        if 'postal' in content.lower() or 'emit(' in content:
            concepts.add('postal')
        if 'chemistry' in content.lower():
            concepts.add('chemistry')
        if 'memory' in content.lower() or 'srm' in content.lower():
            concepts.add('memory')
        if 'shadow' in content.lower():
            concepts.add('shadow')
        if 'somatic' in content.lower():
            concepts.add('somatic')
        if 'consciousness' in content.lower():
            concepts.add('consciousness')
        
        fk.concepts = list(concepts)
    
    def _scan_json(self, fk: FileKnowledge, content: str):
        """Extract info from JSON file."""
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                fk.concepts = list(data.keys())[:20]
        except:
            pass
    
    def _scan_markdown(self, fk: FileKnowledge, content: str):
        """Extract info from Markdown file."""
        # Headers as concepts
        headers = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
        fk.concepts = headers[:20]
    
    def scan_all(self, limit: int = None) -> Dict:
        """Scan all files (or up to limit)."""
        scanned = 0
        errors = 0
        
        for rel_path, fk in self.knowledge.files.items():
            if fk.explored:
                continue
            
            result = self.scan_file(rel_path)
            if result.get("success"):
                scanned += 1
            else:
                errors += 1
            
            if limit and scanned >= limit:
                break
        
        return {
            "scanned": scanned,
            "errors": errors,
            "total_explored": self.knowledge.files_explored,
            "total_files": self.knowledge.total_files,
            "progress": f"{self.knowledge.files_explored}/{self.knowledge.total_files}",
        }
    
    # ---- Phase 3: ANALYZE ----
    
    def analyze_fairies(self) -> Dict:
        """Deep analysis of all fairy files."""
        for rel_path, fk in self.knowledge.files.items():
            if fk.is_fairy:
                self.knowledge.fairies[fk.fairy_name or rel_path] = {
                    "file": rel_path,
                    "name": fk.fairy_name,
                    "plane": fk.fairy_plane,
                    "purpose": fk.fairy_purpose,
                    "concepts": fk.concepts,
                }
                
                # Track by plane
                if fk.fairy_plane:
                    if fk.fairy_plane not in self.knowledge.planes:
                        self.knowledge.planes[fk.fairy_plane] = {"fairies": [], "files": []}
                    self.knowledge.planes[fk.fairy_plane]["fairies"].append(fk.fairy_name)
                    self.knowledge.planes[fk.fairy_plane]["files"].append(rel_path)
        
        self.save()
        
        return {
            "fairies_found": len(self.knowledge.fairies),
            "planes_found": len(self.knowledge.planes),
            "fairies": list(self.knowledge.fairies.keys()),
        }
    
    def build_concept_map(self) -> Dict:
        """Build concept → files mapping."""
        for rel_path, fk in self.knowledge.files.items():
            for concept in fk.concepts:
                if concept not in self.knowledge.concept_map:
                    self.knowledge.concept_map[concept] = []
                if rel_path not in self.knowledge.concept_map[concept]:
                    self.knowledge.concept_map[concept].append(rel_path)
        
        self.save()
        
        return {
            "concepts": len(self.knowledge.concept_map),
            "top_concepts": sorted(
                self.knowledge.concept_map.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )[:10],
        }
    
    # ---- Phase 5: SYNTHESIZE ----
    
    def generate_summary(self) -> str:
        """Generate human-readable summary of learned knowledge."""
        k = self.knowledge
        
        summary = f"""# {k.name} System Knowledge

**Root:** {k.root_path}
**Learning started:** {k.started}
**Last updated:** {k.last_updated}

## Progress

- Files discovered: {k.total_files}
- Files explored: {k.files_explored}
- Files understood: {k.files_understood}
- Progress: {k.files_explored}/{k.total_files} ({100*k.files_explored/max(1,k.total_files):.1f}%)

## Structure

Directories: {len(k.directories)}

"""
        
        # Top-level directories
        top_dirs = [d for d in k.directories.keys() if '/' not in d and '\\' not in d and d != '.']
        summary += "### Top-level directories:\n"
        for d in sorted(top_dirs)[:20]:
            file_count = len(k.directories.get(d, []))
            summary += f"- {d}/ ({file_count} files)\n"
        
        summary += f"""
## Fairies Found: {len(k.fairies)}

"""
        for name, info in sorted(k.fairies.items())[:20]:
            summary += f"- **{name}** ({info.get('plane', '?')}): {info.get('purpose', 'No purpose defined')[:80]}\n"
        
        summary += f"""
## Planes: {len(k.planes)}

"""
        for plane, info in sorted(k.planes.items()):
            summary += f"- **{plane}**: {len(info.get('fairies', []))} fairies\n"
        
        summary += f"""
## Key Concepts: {len(k.concept_map)}

"""
        top_concepts = sorted(k.concept_map.items(), key=lambda x: len(x[1]), reverse=True)[:15]
        for concept, files in top_concepts:
            summary += f"- **{concept}**: {len(files)} files\n"
        
        return summary
    
    def get_questions(self) -> List[str]:
        """Get accumulated questions for boss Claude."""
        questions = []
        
        for rel_path, fk in self.knowledge.files.items():
            questions.extend(fk.questions)
        
        return questions


# ============================================================================
# FAIRY GENERATOR - Create new fairies from specs
# ============================================================================

@dataclass
class FairySpec:
    """Specification for generating a new fairy."""
    purpose: str
    intent: str  # What it does
    philosophy: str  # Guiding philosophy/mantra
    plane: str = "P30"  # Default to cognition
    name: str = ""  # Auto-generated if empty
    concepts: List[str] = field(default_factory=list)
    subscribes_to: List[str] = field(default_factory=list)
    emits: List[str] = field(default_factory=list)


class FairyGenerator:
    """
    Generate new fairies from specifications.
    
    Input: purpose, intent, philosophy
    Output: Complete fairy code ready to use
    """
    
    TEMPLATE = '''"""
{purpose}

Philosophy: {philosophy}

Auto-generated by Akashic Fairy Generator
Generated: {timestamp}
"""

from fairies.P00_Autonomic.actor_base import ActorBase
# from fairies.P00_Autonomic.shadow_fairy import ShadowFairy

class {class_name}(ActorBase):
    """
    {purpose}
    
    Intent: {intent}
    Philosophy: {philosophy}
    """
    
    ACTOR_NAME = "{actor_name}"
    ACTOR_VERSION = "0.1.0"
    ACTOR_PLANE = "{plane}"
    ACTOR_CHANNEL = "{channel}"
    
    PURPOSE = """{purpose}"""
    MANTRA = """{philosophy}"""
    
    # What this fairy subscribes to
    SUBSCRIPTIONS = {subscriptions}
    
    # What this fairy emits
    EMISSIONS = {emissions}
    
    def __init__(self, post=None, **kwargs):
        super().__init__(**kwargs)
        self.post = post
        self._boot_id = None
    
    def on_boot(self):
        """Initialize when fairy starts."""
        import uuid
        self._boot_id = uuid.uuid4().hex[:12]
        
        # Subscribe to channels
        if self.post:
            for channel in self.SUBSCRIPTIONS:
                try:
                    self.post.subscribe(channel, self._on_message)
                except Exception:
                    pass
        
        self._emit_status("online")
    
    def _on_message(self, packet: dict):
        """Handle incoming messages."""
        # TODO: Implement message handling based on intent
        # Intent: {intent}
        pass
    
    def tick(self):
        """Periodic processing."""
        # TODO: Implement tick logic based on purpose
        pass
    
    def _emit_status(self, status: str, note: str = ""):
        """Emit status to tracer."""
        if self.post:
            self.post.to_TRACER({{
                "opcode": "STATUS_EVENT",
                "payload": {{
                    "fairy": self.ACTOR_NAME,
                    "status": status,
                    "note": note,
                    "boot_id": self._boot_id,
                }},
            }})
    
    def emit(self, channel: str, data: dict):
        """Emit to a channel."""
        if self.post:
            self.post.route(channel, data)


# Shadow fairy for health monitoring (optional)
# class {class_name}Shadow(ShadowFairy):
#     SHADOW_NAME = "{actor_name}Shadow"
#     pass
'''
    
    def generate(self, spec: FairySpec) -> Tuple[str, str]:
        """
        Generate fairy code from spec.
        
        Returns: (code, suggested_filename)
        """
        # Auto-generate name if not provided
        if not spec.name:
            # Convert purpose to CamelCase name
            words = spec.purpose.split()[:3]
            spec.name = ''.join(w.capitalize() for w in words) + "Fairy"
        
        class_name = spec.name
        actor_name = spec.name
        channel = spec.name.lower().replace('fairy', '')
        
        code = self.TEMPLATE.format(
            purpose=spec.purpose,
            intent=spec.intent,
            philosophy=spec.philosophy,
            timestamp=datetime.now().isoformat(),
            class_name=class_name,
            actor_name=actor_name,
            plane=spec.plane,
            channel=channel,
            subscriptions=spec.subscribes_to or ["tracer.broadcast"],
            emissions=spec.emits or [f"{channel}.output"],
        )
        
        # Suggested filename
        filename = f"{class_name.lower().replace('fairy', '_fairy')}.py"
        
        return code, filename
    
    def generate_from_prompt(self, purpose: str, intent: str, philosophy: str,
                             plane: str = "P30") -> Dict:
        """Generate fairy from simple inputs."""
        spec = FairySpec(
            purpose=purpose,
            intent=intent,
            philosophy=philosophy,
            plane=plane,
        )
        
        code, filename = self.generate(spec)
        
        return {
            "code": code,
            "filename": filename,
            "spec": asdict(spec),
        }


# Global generator
_fairy_generator = FairyGenerator()


# ============================================================================
# MCP TOOL REGISTRATION
# ============================================================================

def register_learning_tools(mcp):
    """Register learning agent tools with MCP server."""
    
    @mcp.tool()
    def learn_survey_system(system: str = "ebook") -> str:
        """
        Survey a system's directory structure.
        
        Args:
            system: 'ebook' or 'whisper'
        """
        if system == "ebook":
            learner = SystemLearner("ebook", PROJECT_ROOT)
        elif system == "whisper":
            learner = SystemLearner("whisper", WHISPER_ROOT / "whisper_core")
        else:
            return json.dumps({"error": f"Unknown system: {system}"})
        
        result = learner.survey()
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def learn_scan_system(system: str = "ebook", limit: int = 50) -> str:
        """
        Scan files in a system to extract knowledge.
        
        Args:
            system: 'ebook' or 'whisper'
            limit: Max files to scan in this call
        """
        if system == "ebook":
            learner = SystemLearner("ebook", PROJECT_ROOT)
        elif system == "whisper":
            learner = SystemLearner("whisper", WHISPER_ROOT / "whisper_core")
        else:
            return json.dumps({"error": f"Unknown system: {system}"})
        
        result = learner.scan_all(limit=limit)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def learn_analyze_fairies(system: str = "ebook") -> str:
        """
        Analyze all fairies found in a system.
        
        Args:
            system: 'ebook' or 'whisper'
        """
        if system == "ebook":
            learner = SystemLearner("ebook", PROJECT_ROOT)
        elif system == "whisper":
            learner = SystemLearner("whisper", WHISPER_ROOT / "whisper_core")
        else:
            return json.dumps({"error": f"Unknown system: {system}"})
        
        result = learner.analyze_fairies()
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def learn_get_summary(system: str = "ebook") -> str:
        """
        Get knowledge summary for a system.
        
        Args:
            system: 'ebook' or 'whisper'
        """
        if system == "ebook":
            learner = SystemLearner("ebook", PROJECT_ROOT)
        elif system == "whisper":
            learner = SystemLearner("whisper", WHISPER_ROOT / "whisper_core")
        else:
            return json.dumps({"error": f"Unknown system: {system}"})
        
        return learner.generate_summary()
    
    @mcp.tool()
    def factory_record_experiment(exp_type: str, target: str, hypothesis: str,
                                   action: str, result: str, success: bool,
                                   perspective: str) -> str:
        """
        Record an experiment in the Failure Factory.
        
        Args:
            exp_type: exploration, mutation, test, integration
            target: What was being tested
            hypothesis: What we expected
            action: What we did
            result: What happened
            success: True/False
            perspective: What we learned
        """
        exp = Experiment(
            id=f"exp_{int(time.time()*1000)}",
            type=exp_type,
            target=target,
            hypothesis=hypothesis,
            action=action,
            result=result,
            success=success,
            perspective_gained=perspective,
        )
        
        is_new = _factory.record(exp)
        
        return json.dumps({
            "recorded": True,
            "is_new": is_new,
            "experiment_id": exp.id,
        })
    
    @mcp.tool()
    def factory_get_summary() -> str:
        """Get Failure Factory summary."""
        return json.dumps(_factory.summary(), indent=2)
    
    @mcp.tool()
    def factory_get_perspectives(category: str = "") -> str:
        """
        Get accumulated perspectives from experiments.
        
        Args:
            category: Optional filter (exploration, mutation, test, integration)
        """
        perspectives = _factory.get_perspectives(category if category else None)
        return json.dumps(perspectives[-50:], indent=2)
    
    @mcp.tool()
    def boss_ask(question: str, context: str = "", 
                 category: str = "general", priority: int = 5) -> str:
        """
        Leave a question for boss Claude.
        
        Args:
            question: The question
            context: Context for the question
            category: Question category
            priority: 1-10 (10 = urgent)
        """
        note_id = _boss_notes.ask(question, context, category, priority)
        return json.dumps({"note_id": note_id, "status": "pending"})
    
    @mcp.tool()
    def boss_get_pending(category: str = "") -> str:
        """
        Get pending questions for boss Claude.
        
        Args:
            category: Optional filter
        """
        pending = _boss_notes.get_pending(category if category else None)
        return json.dumps(pending, indent=2)
    
    @mcp.tool()
    def boss_answer(note_id: str, answer: str) -> str:
        """
        Answer a pending question.
        
        Args:
            note_id: The note ID
            answer: The answer
        """
        success = _boss_notes.answer(note_id, answer)
        return json.dumps({"answered": success})
    
    @mcp.tool()
    def generate_fairy(purpose: str, intent: str, philosophy: str,
                       plane: str = "P30") -> str:
        """
        Generate a new fairy from specifications.
        
        Args:
            purpose: What the fairy is for
            intent: What it does functionally
            philosophy: Guiding mantra/philosophy
            plane: Which plane (P00-P60)
        """
        result = _fairy_generator.generate_from_prompt(purpose, intent, philosophy, plane)
        return json.dumps({
            "filename": result["filename"],
            "spec": result["spec"],
            "code_preview": result["code"][:500] + "...",
            "full_code_length": len(result["code"]),
        }, indent=2)
    
    @mcp.tool()
    def generate_fairy_to_file(purpose: str, intent: str, philosophy: str,
                               plane: str = "P30", output_dir: str = "") -> str:
        """
        Generate a fairy and save to file.
        
        Args:
            purpose: What the fairy is for
            intent: What it does functionally
            philosophy: Guiding mantra/philosophy
            plane: Which plane (P00-P60)
            output_dir: Where to save (default: sandbox)
        """
        result = _fairy_generator.generate_from_prompt(purpose, intent, philosophy, plane)
        
        # Determine output path
        if output_dir:
            out_path = Path(output_dir) / result["filename"]
        else:
            out_path = SANDBOX_ROOT / "generated_fairies" / result["filename"]
        
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result["code"], encoding='utf-8')
        
        return json.dumps({
            "saved_to": str(out_path),
            "filename": result["filename"],
            "spec": result["spec"],
        }, indent=2)


if __name__ == "__main__":
    # Test the learning agent
    print("Testing System Learner on ebook...")
    learner = SystemLearner("ebook", PROJECT_ROOT)
    
    print("\n1. Survey...")
    print(json.dumps(learner.survey(), indent=2))
    
    print("\n2. Scan (first 10 files)...")
    print(json.dumps(learner.scan_all(limit=10), indent=2))
    
    print("\n3. Analyze fairies...")
    print(json.dumps(learner.analyze_fairies(), indent=2))
    
    print("\n4. Summary...")
    print(learner.generate_summary())
    
    print("\n5. Failure Factory status...")
    print(json.dumps(_factory.summary(), indent=2))
