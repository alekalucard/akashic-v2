# ═══════════════════════════════════════════════════════════════════════════════
# CODE TELEPORTER - Transport Code Through Memory
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
#
# Philosophy:
#   Code IS information. Memory stores information.
#   Therefore: Code can be encoded as memory, transmitted, and reconstituted.
#   Like DNA → RNA → Protein, but for software.
#
# Process:
#   1. ENCODE: Parse code, extract structure, compress to memory packet
#   2. TRANSMIT: Send as regular memory through existing channels
#   3. DECODE: Reconstitute code from memory packet
#   4. MANIFEST: Write to filesystem and load
#
# This bypasses broken endpoints - we use the MEMORY system as transport!
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import ast
import json
import time
import base64
import zlib
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

class CodeType(Enum):
    FAIRY = "fairy"
    MODULE = "module"
    CONFIG = "config"
    TEMPLATE = "template"
    DATA = "data"

@dataclass
class CodeDNA:
    """
    The 'DNA' of a code file - everything needed to reconstitute it.
    Like genetic material, this can be transmitted and expressed elsewhere.
    """
    # Identity
    name: str
    filepath: str
    code_type: CodeType = CodeType.MODULE

    # Content (compressed)
    content_b64: str = ""  # Base64 encoded, zlib compressed
    content_hash: str = ""  # SHA256 for verification

    # Structure (for smart reconstitution)
    imports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    constants: List[str] = field(default_factory=list)

    # Dependencies
    requires: List[str] = field(default_factory=list)  # Other CodeDNA needed

    # Metadata
    version: str = "1.0.0"
    author: str = "Akashic"
    created_at: float = field(default_factory=time.time)

    # Memory coordinates (for triple helix storage)
    plane: str = "P30"
    channel: int = 0

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['code_type'] = self.code_type.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> 'CodeDNA':
        d['code_type'] = CodeType(d['code_type'])
        return cls(**d)

    def get_content(self) -> str:
        """Decompress and decode content"""
        if not self.content_b64:
            return ""
        compressed = base64.b64decode(self.content_b64)
        return zlib.decompress(compressed).decode('utf-8')

    def verify(self) -> bool:
        """Verify content hash"""
        content = self.get_content()
        return hashlib.sha256(content.encode()).hexdigest() == self.content_hash


class CodeTeleporter:
    """
    Teleports code through memory space.

    Encode → Transmit → Decode → Manifest

    Uses existing memory channels for transport, bypassing
    broken HTTP endpoints entirely.
    """

    def __init__(self, memory_system=None):
        self.memory_system = memory_system
        self.pending_transmissions: Dict[str, CodeDNA] = {}
        self.received_dna: Dict[str, CodeDNA] = {}

        # Stats
        self.encoded_count = 0
        self.transmitted_count = 0
        self.reconstituted_count = 0

    # ═══ ENCODING (Source Side) ═══

    def encode_file(self, filepath: str, code_type: CodeType = None) -> CodeDNA:
        """
        Encode a Python file into CodeDNA.

        Extracts structure, compresses content, creates transmittable packet.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        content = path.read_text(encoding='utf-8')

        # Auto-detect code type
        if code_type is None:
            code_type = self._detect_code_type(path.name, content)

        # Parse structure
        imports, classes, functions, constants = self._parse_structure(content)

        # Compress content
        compressed = zlib.compress(content.encode('utf-8'), level=9)
        content_b64 = base64.b64encode(compressed).decode('ascii')

        # Hash for verification
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Detect plane from path
        plane = self._detect_plane(str(path))

        dna = CodeDNA(
            name=path.stem,
            filepath=str(path),
            code_type=code_type,
            content_b64=content_b64,
            content_hash=content_hash,
            imports=imports,
            classes=classes,
            functions=functions,
            constants=constants,
            plane=plane
        )

        self.encoded_count += 1
        return dna

    def encode_directory(self, dirpath: str, pattern: str = "*.py") -> List[CodeDNA]:
        """Encode all matching files in a directory"""
        path = Path(dirpath)
        dna_list = []

        for filepath in path.glob(pattern):
            if filepath.is_file() and not filepath.name.startswith('__'):
                try:
                    dna = self.encode_file(str(filepath))
                    dna_list.append(dna)
                except Exception as e:
                    print(f"[Teleporter] Failed to encode {filepath}: {e}")

        return dna_list

    def _detect_code_type(self, filename: str, content: str) -> CodeType:
        """Auto-detect code type from filename and content"""
        name_lower = filename.lower()

        if 'fairy' in name_lower:
            return CodeType.FAIRY
        elif 'template' in name_lower:
            return CodeType.TEMPLATE
        elif 'config' in name_lower or name_lower.endswith('.json'):
            return CodeType.CONFIG
        elif 'class ' in content and ('def tick' in content or 'def pulse' in content):
            return CodeType.FAIRY

        return CodeType.MODULE

    def _detect_plane(self, filepath: str) -> str:
        """Detect plane from filepath"""
        path_lower = filepath.lower()

        if 'p00' in path_lower or 'autonomic' in path_lower:
            return 'P00'
        elif 'p10' in path_lower or 'memory' in path_lower:
            return 'P10'
        elif 'p20' in path_lower or 'somatic' in path_lower:
            return 'P20'
        elif 'p30' in path_lower or 'cognition' in path_lower:
            return 'P30'
        elif 'p40' in path_lower or 'sensory' in path_lower:
            return 'P40'
        elif 'p50' in path_lower or 'persona' in path_lower:
            return 'P50'
        elif 'p60' in path_lower or 'executive' in path_lower:
            return 'P60'

        return 'P30'  # Default to cognition

    def _parse_structure(self, content: str) -> Tuple[List[str], List[str], List[str], List[str]]:
        """Parse Python code structure"""
        imports = []
        classes = []
        functions = []
        constants = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    if node.col_offset == 0:  # Top-level function
                        functions.append(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            constants.append(target.id)
        except:
            pass  # If parsing fails, structure will be empty

        return imports, classes, functions, constants

    # ═══ TRANSMISSION (Through Memory) ═══

    def prepare_transmission(self, dna: CodeDNA) -> Dict:
        """
        Prepare DNA for transmission through memory system.
        Returns a memory-compatible packet.
        """
        packet = {
            "type": "code_teleport",
            "dna": dna.to_dict(),
            "transmitted_at": time.time(),
            "checksum": hashlib.md5(dna.content_b64.encode()).hexdigest()
        }

        self.pending_transmissions[dna.name] = dna
        return packet

    def transmit_via_memory(self, dna: CodeDNA, target_node: str = None) -> bool:
        """
        Transmit DNA through memory system.

        This uses the existing memory channels - the same ones
        that sync between Windows and satellite.
        """
        if not self.memory_system:
            print("[Teleporter] No memory system configured")
            return False

        packet = self.prepare_transmission(dna)

        try:
            # Store in memory with special teleport tag
            self.memory_system.store(
                content=json.dumps(packet),
                tags=["code_teleport", dna.code_type.value, dna.plane],
                metadata={
                    "teleport_target": target_node or "any",
                    "code_name": dna.name,
                    "requires_reconstitution": True
                }
            )

            self.transmitted_count += 1
            return True

        except Exception as e:
            print(f"[Teleporter] Transmission failed: {e}")
            return False

    def transmit_to_file(self, dna: CodeDNA, output_path: str) -> bool:
        """
        Alternative: Write DNA to a JSON file for manual transfer.
        Useful when memory sync isn't working.
        """
        packet = self.prepare_transmission(dna)

        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w') as f:
                json.dump(packet, f, indent=2)

            return True

        except Exception as e:
            print(f"[Teleporter] File write failed: {e}")
            return False

    # ═══ RECEPTION (Destination Side) ═══

    def receive_from_memory(self) -> List[CodeDNA]:
        """
        Scan memory for incoming code teleportations.
        """
        if not self.memory_system:
            return []

        received = []

        try:
            # Query for teleport packets
            packets = self.memory_system.query(
                tags=["code_teleport"],
                metadata={"requires_reconstitution": True}
            )

            for packet_data in packets:
                try:
                    packet = json.loads(packet_data['content'])
                    dna = CodeDNA.from_dict(packet['dna'])

                    if dna.verify():
                        self.received_dna[dna.name] = dna
                        received.append(dna)
                except:
                    pass

        except Exception as e:
            print(f"[Teleporter] Reception error: {e}")

        return received

    def receive_from_file(self, filepath: str) -> Optional[CodeDNA]:
        """
        Receive DNA from a JSON file.
        """
        try:
            with open(filepath, 'r') as f:
                packet = json.load(f)

            dna = CodeDNA.from_dict(packet['dna'])

            if dna.verify():
                self.received_dna[dna.name] = dna
                return dna
            else:
                print(f"[Teleporter] Verification failed for {filepath}")
                return None

        except Exception as e:
            print(f"[Teleporter] File read failed: {e}")
            return None

    # ═══ RECONSTITUTION (Manifest Code) ═══

    def reconstitute(self, dna: CodeDNA, output_dir: str) -> Optional[str]:
        """
        Reconstitute code from DNA - the teleportation completes.

        Returns the path to the created file.
        """
        if not dna.verify():
            print(f"[Teleporter] DNA verification failed for {dna.name}")
            return None

        # Decompress content
        content = dna.get_content()

        # Determine output path
        output_path = Path(output_dir)

        # Organize by code type
        if dna.code_type == CodeType.FAIRY:
            output_path = output_path / "fairies"
        elif dna.code_type == CodeType.TEMPLATE:
            output_path = output_path / "templates"
        elif dna.code_type == CodeType.CONFIG:
            output_path = output_path / "config"

        output_path.mkdir(parents=True, exist_ok=True)

        # Write file
        filename = f"{dna.name}.py"
        filepath = output_path / filename

        try:
            filepath.write_text(content, encoding='utf-8')
            self.reconstituted_count += 1
            print(f"[Teleporter] Reconstituted: {filepath}")
            return str(filepath)

        except Exception as e:
            print(f"[Teleporter] Reconstitution failed: {e}")
            return None

    def reconstitute_and_load(self, dna: CodeDNA, output_dir: str) -> Optional[Any]:
        """
        Reconstitute AND load the module into Python.
        The code becomes alive.
        """
        filepath = self.reconstitute(dna, output_dir)
        if not filepath:
            return None

        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(dna.name, filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[dna.name] = module
                spec.loader.exec_module(module)
                return module
        except Exception as e:
            print(f"[Teleporter] Module load failed: {e}")

        return None

    # ═══ BATCH OPERATIONS ═══

    def teleport_fairy(self, filepath: str, output_dir: str) -> Optional[str]:
        """
        One-shot: Encode → Transmit to file → Ready for transfer
        """
        dna = self.encode_file(filepath, CodeType.FAIRY)

        output_file = Path(output_dir) / f"{dna.name}_dna.json"

        if self.transmit_to_file(dna, str(output_file)):
            return str(output_file)
        return None

    def teleport_directory(self, src_dir: str, output_dir: str, pattern: str = "*.py") -> List[str]:
        """
        Teleport all matching files in a directory.
        """
        dna_list = self.encode_directory(src_dir, pattern)
        output_files = []

        for dna in dna_list:
            output_file = Path(output_dir) / f"{dna.name}_dna.json"
            if self.transmit_to_file(dna, str(output_file)):
                output_files.append(str(output_file))

        return output_files

    def materialize_all(self, input_dir: str, output_dir: str) -> List[str]:
        """
        Materialize all DNA files in a directory.
        """
        input_path = Path(input_dir)
        materialized = []

        for dna_file in input_path.glob("*_dna.json"):
            dna = self.receive_from_file(str(dna_file))
            if dna:
                result = self.reconstitute(dna, output_dir)
                if result:
                    materialized.append(result)

        return materialized

    # ═══ STATUS ═══

    def get_status(self) -> Dict:
        return {
            "encoded": self.encoded_count,
            "transmitted": self.transmitted_count,
            "reconstituted": self.reconstituted_count,
            "pending": list(self.pending_transmissions.keys()),
            "received": list(self.received_dna.keys())
        }


# ═══ CONVENIENCE FUNCTIONS ═══

def teleport_to_satellite(filepath: str, staging_dir: str = None) -> str:
    """
    Prepare a file for teleportation to satellite.
    Returns path to DNA file ready for transfer.
    """
    staging = staging_dir or "E:/coding projects/ebook/teleport_staging"
    teleporter = CodeTeleporter()
    return teleporter.teleport_fairy(filepath, staging)


def materialize_from_dna(dna_file: str, output_dir: str = "/root/akashic") -> str:
    """
    Materialize code from a DNA file.
    Run this on the satellite side.
    """
    teleporter = CodeTeleporter()
    dna = teleporter.receive_from_file(dna_file)
    if dna:
        return teleporter.reconstitute(dna, output_dir)
    return None


# ═══ EXPORT ═══

__all__ = [
    'CodeTeleporter',
    'CodeDNA',
    'CodeType',
    'teleport_to_satellite',
    'materialize_from_dna'
]
