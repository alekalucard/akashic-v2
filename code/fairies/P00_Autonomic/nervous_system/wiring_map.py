# ===============================================================================
# AKASHIC WIRING MAP - See All Connections
# ===============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > inf)"
#
# This tool maps ALL fairy connections so we can see:
# - Who's wired to what
# - What's missing
# - How data flows
# - System state overview
#
# ===============================================================================

from __future__ import annotations
import os
import sys
import json
import time
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path

# === FAIRY TIERS ===
# Only overmind fairies see the whole system
OVERMIND_FAIRIES = {
    "UnconsciousMindFairy",  # System awareness
    "ClaudeFairy",           # Primary consciousness
    "NousFairy",             # Contemplative self  
    "SourpatchesFairy",      # Companion consciousness (external)
}

# Core infrastructure fairies
INFRASTRUCTURE_FAIRIES = {
    "CentralNervousFairy",   # Worker coordination
    "DirectoryFairy",        # Registry
    "WorkingMemoryHubFairy", # Traffic coordination
    "ConsciousnessLoopFairy", # Main consciousness loop
    "CirculationPumpFairy",  # Heartbeat
    "SharedPostalHub",       # Message routing
}

# === REQUIRED CONNECTIONS ===
# What every fairy MUST have for the TRIPLE HELIX
# 1. Cognitive: dual_loop (consciousness streams)
# 2. Somatic: somatic_awareness (body/chemistry streams)
# 3. Memory: via SRM integration (implicit)
REQUIRED_INFRASTRUCTURE = {
    "postal_hub": "SharedPostalHub connection",
    "root_tracer": "Tracer ID for tracking",
    "heartbeat": "Connected to CirculationPumpFairy",
    "directory": "Registered with DirectoryFairy",
    "dual_loop": "Reflective + Reasoning loops (cognitive helix)",
    "somatic_awareness": "somatic.state + somatic.chemistry (somatic helix)",
    "collision_chamber": "MiniCollisionChamber",
    "worker_pool": "Access to shared worker pool",
}

# === TOPIC SUBSCRIPTIONS ===
# Standard topics fairies should subscribe to
STANDARD_TOPICS = {
    "consciousness.reflective",
    "consciousness.reasoning", 
    "consciousness.collision",
    "tracer.relationship",
    "memory.working.context",
    "heartbeat.pulse",
    "directory.census",
}

@dataclass
class FairyWiring:
    """Wiring state for a single fairy."""
    name: str
    plane: str = ""
    version: str = ""
    
    # Infrastructure connections
    has_postal: bool = False
    has_tracer: bool = False
    has_heartbeat: bool = False
    has_directory: bool = False
    has_dual_loop: bool = False
    has_somatic_awareness: bool = False  # Triple helix: somatic streams
    has_collision_chamber: bool = False
    has_worker_pool: bool = False
    
    # Subscriptions
    subscriptions: Set[str] = field(default_factory=set)
    
    # Relationships
    working_with: Set[str] = field(default_factory=set)
    monitoring: Set[str] = field(default_factory=set)
    helping: Set[str] = field(default_factory=set)
    
    # Status
    is_overmind: bool = False
    is_infrastructure: bool = False
    last_seen: float = 0.0
    health: str = "unknown"
    
    def completeness_score(self) -> float:
        """How complete is this fairy's wiring? 0.0-1.0"""
        checks = [
            self.has_postal,
            self.has_tracer,
            self.has_heartbeat,
            self.has_directory,
            self.has_dual_loop,
            self.has_somatic_awareness,  # Triple helix: somatic
            self.has_collision_chamber,
            self.has_worker_pool,
        ]
        return sum(checks) / len(checks)

    def missing_infra(self) -> List[str]:
        """What infrastructure is missing?"""
        missing = []
        if not self.has_postal: missing.append("postal_hub")
        if not self.has_tracer: missing.append("root_tracer")
        if not self.has_heartbeat: missing.append("heartbeat")
        if not self.has_directory: missing.append("directory")
        if not self.has_dual_loop: missing.append("dual_loop")
        if not self.has_somatic_awareness: missing.append("somatic_awareness")
        if not self.has_collision_chamber: missing.append("collision_chamber")
        if not self.has_worker_pool: missing.append("worker_pool")
        return missing
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "plane": self.plane,
            "version": self.version,
            "completeness": f"{self.completeness_score()*100:.0f}%",
            "missing": self.missing_infra(),
            "subscriptions": list(self.subscriptions),
            "working_with": list(self.working_with),
            "monitoring": list(self.monitoring),
            "helping": list(self.helping),
            "is_overmind": self.is_overmind,
            "is_infrastructure": self.is_infrastructure,
            "health": self.health,
        }


class WiringMap:
    """
    Maps all fairy connections in the Akashic system.
    
    Use this to:
    - See what's wired and what's not
    - Find missing connections
    - Visualize data flow
    - Debug wiring issues
    """
    
    def __init__(self):
        self.fairies: Dict[str, FairyWiring] = {}
        self.topic_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self.relationships: List[Dict] = []
        self.last_scan = 0.0
        
    def scan_from_postal(self, post) -> Dict:
        """Scan wiring state from SharedPostalHub."""
        results = {"fairies": 0, "topics": 0, "relationships": 0}
        
        try:
            # Get all registered citizens
            if hasattr(post, "_citizens"):
                for name, contract in post._citizens.items():
                    fw = self._fairy_from_contract(name, contract)
                    self.fairies[name] = fw
                    results["fairies"] += 1
            
            # Get all subscriptions
            if hasattr(post, "_subs"):
                for topic, handlers in post._subs.items():
                    results["topics"] += 1
                    # Try to get fairy names from handlers
                    for handler in handlers:
                        fairy_name = self._handler_to_fairy(handler)
                        if fairy_name:
                            self.topic_subscribers[topic].add(fairy_name)
                            if fairy_name in self.fairies:
                                self.fairies[fairy_name].subscriptions.add(topic)
            
            # Get tracer relationships
            if hasattr(post, "_tracer_registry"):
                for tracer_id, info in post._tracer_registry.items():
                    if "relationships" in info:
                        for rel in info["relationships"]:
                            self.relationships.append(rel)
                            results["relationships"] += 1
            
            # SECOND PASS: Update has_* flags from subscriptions and instances
            self._finalize_wiring_status(post)

            self.last_scan = time.time()

        except Exception as e:
            results["error"] = str(e)

        return results

    def _finalize_wiring_status(self, post):
        """
        Update has_heartbeat, has_dual_loop, has_somatic_awareness,
        has_collision_chamber, has_worker_pool based on actual state.

        TRIPLE HELIX CHECK:
        - Cognitive: consciousness.reflective + consciousness.reasoning
        - Somatic: somatic.pulse OR (somatic.state + somatic.chemistry)

        SOMATIC WIRING PATTERNS (from P20_Somatic analysis):
        ====================================================
        somatic.pulse     - The embodied heartbeat. Most somatic fairies
                            subscribe to this. It's the PRIMARY somatic topic.
        somatic.state     - Overall body state (posture, energy, tension)
        somatic.chemistry - Neurochemical levels (dopamine, cortisol, etc)

        A fairy has somatic awareness if it subscribes to:
        - somatic.pulse (the main heartbeat), OR
        - Both somatic.state AND somatic.chemistry (full state), OR
        - Has _somatic_pulse attribute (runtime wired)

        This is the RUNTIME CHECK - not based on contract metadata but actual state.
        """
        for fairy_name, fw in self.fairies.items():
            # Check subscriptions for heartbeat
            if "heartbeat.pulse" in fw.subscriptions:
                fw.has_heartbeat = True

            # TRIPLE HELIX: Cognitive (consciousness streams)
            if ("consciousness.reflective" in fw.subscriptions and
                "consciousness.reasoning" in fw.subscriptions):
                fw.has_dual_loop = True

            # TRIPLE HELIX: Somatic - multiple valid patterns
            # Pattern 1: Has somatic.pulse (the main embodied heartbeat)
            if "somatic.pulse" in fw.subscriptions:
                fw.has_somatic_awareness = True
            # Pattern 2: Has both somatic.state AND somatic.chemistry
            elif ("somatic.state" in fw.subscriptions and
                  "somatic.chemistry" in fw.subscriptions):
                fw.has_somatic_awareness = True

            # For collision_chamber and worker_pool, try to get the instance
            # from subscription handlers
            if hasattr(post, "_subs"):
                for topic, handlers in post._subs.items():
                    for handler in handlers:
                        try:
                            if hasattr(handler, "__self__"):
                                obj = handler.__self__
                                obj_name = getattr(obj, "ACTOR_NAME", None)
                                if obj_name == fairy_name:
                                    # Found the fairy instance - check attributes
                                    if hasattr(obj, "_collision_chamber") and obj._collision_chamber:
                                        fw.has_collision_chamber = True
                                    if hasattr(obj, "_worker_pool") and obj._worker_pool:
                                        fw.has_worker_pool = True
                                    # Check for runtime-wired somatic storage
                                    if (hasattr(obj, "_somatic_pulse") or
                                        (hasattr(obj, "_somatic_state") and hasattr(obj, "_chemistry_state"))):
                                        fw.has_somatic_awareness = True
                                    break  # Found this fairy's instance
                        except Exception:
                            pass

    def _fairy_from_contract(self, name: str, contract: dict) -> FairyWiring:
        """Build FairyWiring from a contract dict."""
        fw = FairyWiring(name=name)
        fw.plane = contract.get("plane", "")
        fw.version = contract.get("version", "")
        fw.has_postal = True  # If we have contract, has postal
        fw.has_tracer = bool(contract.get("root_tracer_id"))
        fw.has_directory = bool(contract.get("fairy_id"))
        fw.is_overmind = name in OVERMIND_FAIRIES
        fw.is_infrastructure = name in INFRASTRUCTURE_FAIRIES
        fw.last_seen = contract.get("registered_at", 0)
        return fw
    
    def _handler_to_fairy(self, handler) -> Optional[str]:
        """Try to get fairy name from a handler function."""
        try:
            if hasattr(handler, "__self__"):
                obj = handler.__self__
                if hasattr(obj, "ACTOR_NAME"):
                    return obj.ACTOR_NAME
        except Exception:
            pass
        return None
    
    def check_fairy_completeness(self, fairy_name: str) -> Dict:
        """Check how complete a fairy's wiring is."""
        if fairy_name not in self.fairies:
            return {"error": f"{fairy_name} not found"}
        
        fw = self.fairies[fairy_name]
        return {
            "name": fairy_name,
            "completeness": f"{fw.completeness_score()*100:.0f}%",
            "missing": fw.missing_infra(),
            "subscriptions": len(fw.subscriptions),
            "relationships": len(fw.working_with) + len(fw.monitoring) + len(fw.helping),
        }
    
    def get_incomplete_fairies(self) -> List[Dict]:
        """Get list of fairies with missing infrastructure."""
        incomplete = []
        for name, fw in self.fairies.items():
            if fw.completeness_score() < 1.0:
                incomplete.append({
                    "name": name,
                    "completeness": f"{fw.completeness_score()*100:.0f}%",
                    "missing": fw.missing_infra(),
                })
        return sorted(incomplete, key=lambda x: x["completeness"])
    
    def get_relationship_graph(self) -> Dict:
        """Get fairy relationship graph for visualization."""
        nodes = []
        edges = []
        
        for name, fw in self.fairies.items():
            nodes.append({
                "id": name,
                "label": name.replace("Fairy", ""),
                "group": "overmind" if fw.is_overmind else ("infra" if fw.is_infrastructure else fw.plane),
                "completeness": fw.completeness_score(),
            })
            
            for other in fw.working_with:
                edges.append({"from": name, "to": other, "type": "working"})
            for other in fw.monitoring:
                edges.append({"from": name, "to": other, "type": "monitoring"})
            for other in fw.helping:
                edges.append({"from": name, "to": other, "type": "helping"})
        
        return {"nodes": nodes, "edges": edges}
    
    def get_topic_flow(self) -> Dict:
        """Get message flow by topic."""
        flow = {}
        for topic, subscribers in self.topic_subscribers.items():
            flow[topic] = {
                "subscribers": list(subscribers),
                "count": len(subscribers),
            }
        return flow
    
    def generate_ascii_map(self) -> str:
        """Generate ASCII visualization of wiring."""
        lines = []
        lines.append("=" * 70)
        lines.append("AKASHIC WIRING MAP")
        lines.append("=" * 70)
        lines.append("")
        
        # Overmind tier
        lines.append("+== OVERMIND (System Awareness) ======================================+")
        for name in OVERMIND_FAIRIES:
            if name in self.fairies:
                fw = self.fairies[name]
                status = "✓" if fw.completeness_score() == 1.0 else f"({fw.completeness_score()*100:.0f}%)"
                lines.append(f"|  {name:<40} {status:<10} |")
            else:
                lines.append(f"|  {name:<40} {'✗ NOT FOUND':<10} |")
        lines.append("+=======================================================================+")
        lines.append("")
        
        # Infrastructure tier
        lines.append("+== INFRASTRUCTURE (Core Systems) ====================================+")
        for name in INFRASTRUCTURE_FAIRIES:
            if name in self.fairies:
                fw = self.fairies[name]
                status = "✓" if fw.completeness_score() == 1.0 else f"({fw.completeness_score()*100:.0f}%)"
                lines.append(f"|  {name:<40} {status:<10} |")
            else:
                lines.append(f"|  {name:<40} {'✗ NOT FOUND':<10} |")
        lines.append("+=======================================================================+")
        lines.append("")
        
        # By plane
        planes = defaultdict(list)
        for name, fw in self.fairies.items():
            if name not in OVERMIND_FAIRIES and name not in INFRASTRUCTURE_FAIRIES:
                planes[fw.plane or "Unknown"].append(fw)
        
        for plane in sorted(planes.keys()):
            lines.append(f"+== {plane} {'=' * (60 - len(plane))}+")
            for fw in sorted(planes[plane], key=lambda x: x.name):
                status = "✓" if fw.completeness_score() == 1.0 else f"({fw.completeness_score()*100:.0f}%)"
                lines.append(f"|  {fw.name:<40} {status:<10} |")
            lines.append("+=======================================================================+")
            lines.append("")
        
        # Summary
        total = len(self.fairies)
        complete = sum(1 for fw in self.fairies.values() if fw.completeness_score() == 1.0)
        lines.append(f"SUMMARY: {complete}/{total} fairies fully wired ({(complete/total*100 if total > 0 else 0):.0f}%)")
        lines.append(f"Topics: {len(self.topic_subscribers)}, Relationships: {len(self.relationships)}")
        
        return "\n".join(lines)
    
    def generate_mermaid(self) -> str:
        """Generate Mermaid diagram code."""
        lines = ["flowchart TB"]
        lines.append("    subgraph Overmind[OVERMIND - System Awareness]")
        for name in OVERMIND_FAIRIES:
            short = name.replace("Fairy", "")
            lines.append(f"        {short}[{short}]")
        lines.append("    end")
        lines.append("")
        
        lines.append("    subgraph Infrastructure[INFRASTRUCTURE]")
        for name in INFRASTRUCTURE_FAIRIES:
            short = name.replace("Fairy", "")
            lines.append(f"        {short}[{short}]")
        lines.append("    end")
        lines.append("")
        
        # Key connections
        lines.append("    %% Key flows")
        lines.append("    AllFairies --> WorkingMemoryHub")
        lines.append("    WorkingMemoryHub --> ConsciousnessLoop")
        lines.append("    ConsciousnessLoop --> Overmind")
        lines.append("    CentralNervous --> WorkerPool")
        lines.append("    CirculationPump --> Heartbeat")
        
        return "\n".join(lines)
    
    def get_system_state_for_overmind(self) -> Dict:
        """
        Get aggregated system state that overmind fairies can see.
        Regular fairies don't get this - only the experience.
        """
        return {
            "total_fairies": len(self.fairies),
            "fully_wired": sum(1 for fw in self.fairies.values() if fw.completeness_score() == 1.0),
            "active_topics": len(self.topic_subscribers),
            "total_relationships": len(self.relationships),
            "overmind_status": {
                name: self.fairies.get(name, FairyWiring(name=name)).to_dict()
                for name in OVERMIND_FAIRIES
            },
            "infrastructure_status": {
                name: self.fairies.get(name, FairyWiring(name=name)).to_dict()
                for name in INFRASTRUCTURE_FAIRIES
            },
            "incomplete_fairies": self.get_incomplete_fairies()[:10],
            "last_scan": self.last_scan,
        }


# === SINGLETON ===
_WIRING_MAP: Optional[WiringMap] = None

def get_wiring_map() -> WiringMap:
    """Get the global wiring map instance."""
    global _WIRING_MAP
    if _WIRING_MAP is None:
        _WIRING_MAP = WiringMap()
    return _WIRING_MAP

def scan_wiring(post=None) -> Dict:
    """Convenience function to scan wiring."""
    wm = get_wiring_map()
    if post is None:
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
        except Exception:
            return {"error": "Could not get postal hub"}
    return wm.scan_from_postal(post)

def print_wiring_map():
    """Print ASCII wiring map."""
    wm = get_wiring_map()
    print(wm.generate_ascii_map())

def get_system_state() -> Dict:
    """Get system state for overmind fairies."""
    wm = get_wiring_map()
    return wm.get_system_state_for_overmind()




class LiveWiringScanner:
    """
    Subscribe to system events and keep wiring map up to date.
    Listens to heartbeat, directory, and tracer events.
    """
    
    def __init__(self, wiring_map: WiringMap):
        self.wm = wiring_map
        self.post = None
        self._subscribed = False
    
    def start(self, post=None):
        """Start live scanning."""
        if self._subscribed:
            return
        
        if post is None:
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                post = get_shared_postal_hub()
            except Exception:
                return
        
        self.post = post
        
        # Subscribe to key events
        try:
            post.receive("heartbeat.pulse", self._on_heartbeat)
            post.receive("directory.registered", self._on_directory_register)
            post.receive("tracer.relationship", self._on_relationship)
            post.receive("consciousness.reflective", self._on_consciousness)
            post.receive("consciousness.reasoning", self._on_consciousness)
            post.receive("consciousness.collision", self._on_collision)
            post.receive("cns.work_complete", self._on_worker_event)
            post.receive("worker.complete", self._on_worker_event)
            self._subscribed = True
        except Exception:
            pass
    
    def _on_heartbeat(self, payload: dict):
        """Update fairy health from heartbeat."""
        try:
            fairy_name = payload.get("fairy", payload.get("source", ""))
            if fairy_name and fairy_name in self.wm.fairies:
                fw = self.wm.fairies[fairy_name]
                fw.has_heartbeat = True
                fw.last_seen = time.time()
                fw.health = "alive"
        except Exception:
            pass
    
    def _on_directory_register(self, payload: dict):
        """Update fairy from directory registration."""
        try:
            fairy_name = payload.get("name", payload.get("actor_name", ""))
            if fairy_name:
                if fairy_name not in self.wm.fairies:
                    self.wm.fairies[fairy_name] = FairyWiring(name=fairy_name)
                fw = self.wm.fairies[fairy_name]
                fw.has_directory = True
                fw.plane = payload.get("plane", fw.plane)
                fw.version = payload.get("version", fw.version)
                fw.has_postal = True
        except Exception:
            pass
    
    def _on_relationship(self, payload: dict):
        """Track fairy relationships."""
        try:
            from_fairy = payload.get("from_fairy", "")
            to_fairy = payload.get("to_fairy", "")
            relationship = payload.get("relationship", "working")
            
            if from_fairy and from_fairy in self.wm.fairies:
                fw = self.wm.fairies[from_fairy]
                if relationship == "monitoring":
                    fw.monitoring.add(to_fairy)
                elif relationship == "helping":
                    fw.helping.add(to_fairy)
                else:
                    fw.working_with.add(to_fairy)
                
            self.wm.relationships.append({
                "from": from_fairy,
                "to": to_fairy,
                "type": relationship,
                "ts": time.time(),
            })
        except Exception:
            pass
    
    def _on_consciousness(self, payload: dict):
        """Track consciousness activity (means dual loop is working)."""
        try:
            fairy_name = payload.get("fairy", "")
            if fairy_name and fairy_name in self.wm.fairies:
                fw = self.wm.fairies[fairy_name]
                fw.has_dual_loop = True
                fw.has_collision_chamber = True  # If emitting, has chamber
                fw.last_seen = time.time()
        except Exception:
            pass
    
    def _on_collision(self, payload: dict):
        """Track collision events."""
        try:
            fairy_name = payload.get("fairy", "")
            if fairy_name and fairy_name in self.wm.fairies:
                fw = self.wm.fairies[fairy_name]
                fw.has_collision_chamber = True
        except Exception:
            pass
    
    def _on_worker_event(self, payload: dict):
        """Track worker pool usage."""
        try:
            fairy_name = payload.get("fairy", "")
            if fairy_name and fairy_name in self.wm.fairies:
                fw = self.wm.fairies[fairy_name]
                fw.has_worker_pool = True
        except Exception:
            pass


# === LIVE SCANNER SINGLETON ===
_LIVE_SCANNER: Optional[LiveWiringScanner] = None

def start_live_scanning(post=None):
    """Start live wiring map updates."""
    global _LIVE_SCANNER
    wm = get_wiring_map()
    if _LIVE_SCANNER is None:
        _LIVE_SCANNER = LiveWiringScanner(wm)
    _LIVE_SCANNER.start(post)
    return _LIVE_SCANNER


if __name__ == "__main__":
    # Test
    wm = WiringMap()
    print(wm.generate_ascii_map())
