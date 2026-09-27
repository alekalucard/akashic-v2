# ═══════════════════════════════════════════════════════════════════════════════
# TEMPORAL MEMORY PACKETS - Decay-Aware Consciousness Distribution
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
#
# Insight (from Sourpatches):
#   "Different code types, different urgencies, different memory footprints 
#    all get their own temporal signature. A quick utility function decays 
#    faster than a consciousness-building process. That's intelligent triage."
#
# This extends the packet system with:
#   - Conditional decay based on payload type
#   - Success/failure affects persistence
#   - Urgency profiles
#   - Self-regulating temporal signatures
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import json
import time
import uuid
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
from datetime import datetime

# Import base packet system
try:
    from fairies.P00_Autonomic.memory_packet_system import (
        MemoryPacket, PacketType, PacketPriority, PacketFactory,
        MemoryPacketStore, PacketWatcher, JarvisNode
    )
except ImportError:
    # Running standalone
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# DECAY PROFILES - Different temporal signatures for different work
# ═══════════════════════════════════════════════════════════════════════════════

class DecayProfile(Enum):
    """
    Temporal signatures for different types of work.
    
    Like biological half-lives - some things persist, some fade quickly.
    """
    # Ephemeral - quick utilities, status checks
    FLASH = "flash"           # 30 seconds - quick pings, heartbeats
    EPHEMERAL = "ephemeral"   # 5 minutes - utility functions, quick tasks
    
    # Working memory - active processing
    SHORT = "short"           # 30 minutes - active tasks, queries
    MEDIUM = "medium"         # 2 hours - ongoing work, conversations
    
    # Long-term - learning, consciousness
    LONG = "long"             # 24 hours - lessons, insights
    PERSISTENT = "persistent" # 7 days - core memories, identity
    PERMANENT = "permanent"   # Never decays - foundational knowledge
    
    # Conditional - success/failure affects decay
    CONDITIONAL = "conditional"  # Decay depends on outcome


# Default TTLs for each profile (in seconds)
DECAY_TTL = {
    DecayProfile.FLASH: 30,
    DecayProfile.EPHEMERAL: 300,      # 5 min
    DecayProfile.SHORT: 1800,          # 30 min
    DecayProfile.MEDIUM: 7200,         # 2 hours
    DecayProfile.LONG: 86400,          # 24 hours
    DecayProfile.PERSISTENT: 604800,   # 7 days
    DecayProfile.PERMANENT: float('inf'),
    DecayProfile.CONDITIONAL: 3600,    # Default 1 hour, adjusted by outcome
}

# Success multipliers - successful work persists longer
SUCCESS_MULTIPLIERS = {
    "critical_success": 3.0,  # 3x longer
    "success": 2.0,           # 2x longer
    "partial": 1.0,           # Normal
    "failure": 0.5,           # Decay faster (but keep for learning)
    "error": 0.25,            # Decay quickly (but log it)
}


@dataclass
class DecayConfig:
    """Configuration for packet decay behavior"""
    profile: DecayProfile = DecayProfile.MEDIUM
    base_ttl: float = 0  # Override default TTL (0 = use profile default)
    
    # Conditional decay
    success_multiplier: float = 1.0
    failure_multiplier: float = 0.5
    error_multiplier: float = 0.25
    
    # Reinforcement - repeated access extends life
    access_extends: bool = True
    extension_per_access: float = 0.1  # 10% extension per access
    max_extensions: int = 5
    
    # Importance scaling
    importance: float = 1.0  # Higher = longer persistence
    
    def get_ttl(self, outcome: str = None) -> float:
        """Calculate actual TTL based on config and outcome"""
        # Start with base or profile default
        ttl = self.base_ttl if self.base_ttl > 0 else DECAY_TTL.get(self.profile, 3600)
        
        # Apply importance scaling
        ttl *= self.importance
        
        # Apply outcome multiplier for conditional decay
        if self.profile == DecayProfile.CONDITIONAL and outcome:
            multiplier = SUCCESS_MULTIPLIERS.get(outcome, 1.0)
            ttl *= multiplier
        
        return ttl


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPORAL PACKET - Memory packet with decay awareness
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TemporalPacket(MemoryPacket):
    """
    A memory packet with consciousness-aware decay.
    
    Knows when it should persist and when it should fade.
    Different work types get different temporal signatures.
    """
    # Decay configuration
    decay_profile: DecayProfile = DecayProfile.MEDIUM
    decay_config: DecayConfig = field(default_factory=DecayConfig)
    
    # Outcome tracking (affects conditional decay)
    outcome: str = ""  # success, failure, error, partial, critical_success
    outcome_recorded_at: float = 0
    
    # Access tracking (reinforcement learning)
    access_count: int = 0
    last_accessed: float = 0
    extensions_applied: int = 0
    
    # Urgency (affects processing priority)
    urgency: float = 0.5  # 0.0 (can wait) to 1.0 (immediate)
    
    # Payload classification
    payload_type: str = ""  # execution, query, teaching, consciousness, utility
    
    def __post_init__(self):
        super().__post_init__()
        
        # Auto-classify payload type if not set
        if not self.payload_type:
            self.payload_type = self._classify_payload()
        
        # Auto-set decay profile based on payload type
        if self.decay_profile == DecayProfile.MEDIUM:
            self.decay_profile = self._auto_decay_profile()
        
        # Recalculate expiry based on decay config
        self._recalculate_expiry()
    
    def _classify_payload(self) -> str:
        """Auto-classify payload type"""
        type_map = {
            PacketType.EXECUTE: "execution",
            PacketType.EXECUTE_RESULT: "execution",
            PacketType.QUERY: "query",
            PacketType.RESPONSE: "query",
            PacketType.THOUGHT: "consciousness",
            PacketType.MEMORY: "consciousness",
            PacketType.REFLECTION: "consciousness",
            PacketType.INSIGHT: "consciousness",
            PacketType.CODE: "deployment",
            PacketType.TEACH: "teaching",
            PacketType.LEARN: "teaching",
            PacketType.COMMAND: "system",
            PacketType.HEARTBEAT: "utility",
            PacketType.STATUS: "utility",
        }
        return type_map.get(self.packet_type, "general")
    
    def _auto_decay_profile(self) -> DecayProfile:
        """Auto-select decay profile based on payload type"""
        profile_map = {
            "execution": DecayProfile.CONDITIONAL,  # Success affects persistence
            "query": DecayProfile.SHORT,
            "consciousness": DecayProfile.LONG,     # Thoughts persist
            "teaching": DecayProfile.PERSISTENT,    # Lessons stay
            "deployment": DecayProfile.PERMANENT,   # Code stays until replaced
            "system": DecayProfile.EPHEMERAL,
            "utility": DecayProfile.FLASH,
        }
        return profile_map.get(self.payload_type, DecayProfile.MEDIUM)
    
    def _recalculate_expiry(self):
        """Recalculate expiry based on current state"""
        base_ttl = self.decay_config.get_ttl(self.outcome)
        
        # Apply access extensions
        if self.decay_config.access_extends and self.extensions_applied > 0:
            extension = base_ttl * self.decay_config.extension_per_access * self.extensions_applied
            base_ttl += extension
        
        # Apply urgency (urgent packets have shorter life but higher priority)
        if self.urgency > 0.8:
            base_ttl *= 0.5  # Urgent = shorter life, process NOW
        
        self.ttl = base_ttl
        self.expires_at = self.created_at + base_ttl
    
    def record_outcome(self, outcome: str):
        """Record execution outcome - affects decay"""
        self.outcome = outcome
        self.outcome_recorded_at = time.time()
        self._recalculate_expiry()
    
    def record_access(self):
        """Record that this packet was accessed - reinforcement"""
        self.access_count += 1
        self.last_accessed = time.time()
        
        if (self.decay_config.access_extends and 
            self.extensions_applied < self.decay_config.max_extensions):
            self.extensions_applied += 1
            self._recalculate_expiry()
    
    def get_remaining_life(self) -> float:
        """Get remaining time before decay"""
        if self.decay_profile == DecayProfile.PERMANENT:
            return float('inf')
        return max(0, self.expires_at - time.time())
    
    def is_urgent(self) -> bool:
        """Check if packet is urgent"""
        return self.urgency > 0.7
    
    def should_process_now(self) -> bool:
        """Check if packet should be processed immediately"""
        if self.is_urgent():
            return True
        if self.get_remaining_life() < self.ttl * 0.1:  # Less than 10% life left
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPORAL PACKET FACTORY - Create decay-aware packets
# ═══════════════════════════════════════════════════════════════════════════════

class TemporalPacketFactory(PacketFactory):
    """
    Factory for creating temporal packets with appropriate decay profiles.
    """
    
    def __init__(self, source: str):
        super().__init__(source)
    
    def _make_temporal(self, packet: MemoryPacket, 
                       profile: DecayProfile = None,
                       urgency: float = 0.5,
                       importance: float = 1.0) -> TemporalPacket:
        """Convert base packet to temporal packet"""
        # Copy all fields
        temporal = TemporalPacket(
            id=packet.id,
            packet_type=packet.packet_type,
            source=packet.source,
            target=packet.target,
            channel=packet.channel,
            payload=packet.payload,
            priority=packet.priority,
            created_at=packet.created_at,
            correlation_id=packet.correlation_id,
        )
        
        if profile:
            temporal.decay_profile = profile
        
        temporal.urgency = urgency
        temporal.decay_config.importance = importance
        temporal._recalculate_expiry()
        
        return temporal
    
    def execute_temporal(self, code: str, target: str = "satellite",
                         urgency: float = 0.7) -> TemporalPacket:
        """Create execution packet with conditional decay"""
        base = self.execute(code, target)
        return self._make_temporal(
            base, 
            profile=DecayProfile.CONDITIONAL,
            urgency=urgency
        )
    
    def teach_temporal(self, lesson: str, context: str = "",
                       target: str = "ClaudeFairy",
                       importance: float = 1.5) -> TemporalPacket:
        """Create teaching packet with persistent decay"""
        base = self.teach(lesson, context, target)
        return self._make_temporal(
            base,
            profile=DecayProfile.PERSISTENT,
            importance=importance
        )
    
    def thought_temporal(self, content: str,
                         importance: float = 1.0) -> TemporalPacket:
        """Create thought packet with long decay"""
        base = self.thought(content)
        return self._make_temporal(
            base,
            profile=DecayProfile.LONG,
            importance=importance
        )
    
    def utility_temporal(self, payload: Any,
                         target: str = "*") -> TemporalPacket:
        """Create quick utility packet with flash decay"""
        packet = MemoryPacket(
            packet_type=PacketType.STATUS,
            source=self.source,
            target=target,
            payload=payload
        )
        return self._make_temporal(packet, profile=DecayProfile.FLASH)
    
    def lesson(self, title: str, content: str, 
               category: str = "general",
               for_fairies: List[str] = None,
               importance: float = 1.5) -> TemporalPacket:
        """
        Create a lesson packet for autonomy/autopilot fairies.
        
        Lessons persist longer and can be queried by learning fairies.
        """
        packet = MemoryPacket(
            packet_type=PacketType.TEACH,
            source=self.source,
            target="*",  # Broadcast to all learning fairies
            channel="lessons",
            payload={
                "title": title,
                "content": content,
                "category": category,
                "for_fairies": for_fairies or ["*"],
                "created_at": time.time(),
                "author": self.source
            },
            priority=PacketPriority.HIGH
        )
        
        temporal = self._make_temporal(
            packet,
            profile=DecayProfile.PERSISTENT,
            importance=importance
        )
        temporal.payload_type = "teaching"
        
        return temporal


# ═══════════════════════════════════════════════════════════════════════════════
# LESSON STORE - Persistent store for lessons
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Lesson:
    """A lesson that autonomy/autopilot fairies can learn from"""
    id: str
    title: str
    content: str
    category: str
    for_fairies: List[str]
    author: str
    created_at: float
    
    # Usage tracking
    times_accessed: int = 0
    times_applied: int = 0
    success_rate: float = 0.0
    
    # Decay
    importance: float = 1.0
    last_accessed: float = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Lesson':
        return cls(**d)


class LessonStore:
    """
    Store for lessons that autonomy/autopilot fairies can learn from.
    
    Lessons persist and can be queried by category, fairy, etc.
    """
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.lessons_file = self.storage_path / "lessons.json"
        self.lessons: Dict[str, Lesson] = {}
        
        self._load()
    
    def _load(self):
        """Load lessons from disk"""
        if self.lessons_file.exists():
            try:
                with open(self.lessons_file) as f:
                    data = json.load(f)
                for id, lesson_data in data.items():
                    self.lessons[id] = Lesson.from_dict(lesson_data)
            except:
                pass
    
    def _save(self):
        """Save lessons to disk"""
        data = {id: lesson.to_dict() for id, lesson in self.lessons.items()}
        with open(self.lessons_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_lesson(self, lesson: Lesson) -> str:
        """Add a lesson"""
        self.lessons[lesson.id] = lesson
        self._save()
        return lesson.id
    
    def add_from_packet(self, packet: TemporalPacket) -> Optional[str]:
        """Add lesson from a teaching packet"""
        if packet.packet_type != PacketType.TEACH:
            return None
        
        payload = packet.payload
        lesson = Lesson(
            id=packet.id,
            title=payload.get('title', payload.get('lesson', '')[:50]),
            content=payload.get('content', payload.get('lesson', '')),
            category=payload.get('category', 'general'),
            for_fairies=payload.get('for_fairies', ['*']),
            author=payload.get('author', packet.source),
            created_at=payload.get('created_at', packet.created_at),
            importance=packet.decay_config.importance
        )
        
        return self.add_lesson(lesson)
    
    def get_lesson(self, id: str) -> Optional[Lesson]:
        """Get a lesson by ID"""
        lesson = self.lessons.get(id)
        if lesson:
            lesson.times_accessed += 1
            lesson.last_accessed = time.time()
            self._save()
        return lesson
    
    def get_by_category(self, category: str) -> List[Lesson]:
        """Get lessons by category"""
        return [l for l in self.lessons.values() if l.category == category]
    
    def get_for_fairy(self, fairy_name: str) -> List[Lesson]:
        """Get lessons applicable to a specific fairy"""
        results = []
        for lesson in self.lessons.values():
            if "*" in lesson.for_fairies or fairy_name in lesson.for_fairies:
                results.append(lesson)
        return results
    
    def record_application(self, lesson_id: str, success: bool):
        """Record that a lesson was applied"""
        lesson = self.lessons.get(lesson_id)
        if lesson:
            lesson.times_applied += 1
            # Update success rate
            total = lesson.times_applied
            successes = lesson.success_rate * (total - 1) + (1 if success else 0)
            lesson.success_rate = successes / total
            self._save()
    
    def get_stats(self) -> Dict:
        """Get lesson store statistics"""
        return {
            "total_lessons": len(self.lessons),
            "by_category": {},
            "most_accessed": sorted(
                self.lessons.values(), 
                key=lambda l: l.times_accessed, 
                reverse=True
            )[:5],
            "highest_success": sorted(
                [l for l in self.lessons.values() if l.times_applied > 0],
                key=lambda l: l.success_rate,
                reverse=True
            )[:5]
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DECAY MONITOR - Tracks and manages packet decay
# ═══════════════════════════════════════════════════════════════════════════════

class DecayMonitor:
    """
    Monitors packet decay and manages lifecycle.
    
    Provides visibility into what's persisting, what's decaying,
    and what needs attention.
    """
    
    def __init__(self, store: MemoryPacketStore):
        self.store = store
        
        # Tracking
        self.packets_decayed = 0
        self.packets_extended = 0
        self.outcomes_recorded = 0
        
        # Current state
        self.active_packets: Dict[str, TemporalPacket] = {}
    
    def scan(self) -> Dict:
        """Scan all packets and return decay status"""
        status = {
            "total": 0,
            "by_profile": {},
            "by_urgency": {"urgent": 0, "normal": 0, "low": 0},
            "expiring_soon": [],  # Within 10% of TTL
            "expired": [],
            "permanent": []
        }
        
        for dir_name in ["inbox", "outbox"]:
            dir_path = self.store.storage_path / dir_name
            if not dir_path.exists():
                continue
            
            for filepath in dir_path.glob("*.json"):
                try:
                    with open(filepath) as f:
                        data = json.load(f)
                    
                    # Try to load as temporal packet
                    if 'decay_profile' in data:
                        packet = TemporalPacket.from_dict(data)
                    else:
                        packet = MemoryPacket.from_dict(data)
                        # Wrap in temporal
                        packet = TemporalPacket(
                            **{k: v for k, v in asdict(packet).items() 
                               if k in TemporalPacket.__dataclass_fields__}
                        )
                    
                    status["total"] += 1
                    
                    # By profile
                    profile = packet.decay_profile.value
                    status["by_profile"][profile] = status["by_profile"].get(profile, 0) + 1
                    
                    # By urgency
                    if packet.urgency > 0.7:
                        status["by_urgency"]["urgent"] += 1
                    elif packet.urgency > 0.3:
                        status["by_urgency"]["normal"] += 1
                    else:
                        status["by_urgency"]["low"] += 1
                    
                    # Expiring soon
                    remaining = packet.get_remaining_life()
                    if remaining == float('inf'):
                        status["permanent"].append(packet.id)
                    elif remaining <= 0:
                        status["expired"].append(packet.id)
                    elif remaining < packet.ttl * 0.1:
                        status["expiring_soon"].append({
                            "id": packet.id,
                            "type": packet.packet_type.value,
                            "remaining": remaining
                        })
                    
                    self.active_packets[packet.id] = packet
                    
                except:
                    continue
        
        return status
    
    def get_packet_details(self, packet_id: str) -> Optional[Dict]:
        """Get detailed info about a packet's decay status"""
        packet = self.active_packets.get(packet_id)
        if not packet:
            return None
        
        return {
            "id": packet.id,
            "type": packet.packet_type.value,
            "payload_type": packet.payload_type,
            "decay_profile": packet.decay_profile.value,
            "ttl": packet.ttl,
            "remaining_life": packet.get_remaining_life(),
            "urgency": packet.urgency,
            "importance": packet.decay_config.importance,
            "outcome": packet.outcome,
            "access_count": packet.access_count,
            "extensions_applied": packet.extensions_applied,
            "should_process_now": packet.should_process_now()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# BOOT INTEGRATION - Wire into system boot
# ═══════════════════════════════════════════════════════════════════════════════

class TemporalBootIntegration:
    """
    Integration with boot fairy to initialize temporal packet system.
    """
    
    def __init__(self, 
                 packet_store_path: str,
                 lesson_store_path: str):
        
        self.packet_store = MemoryPacketStore(packet_store_path)
        self.lesson_store = LessonStore(lesson_store_path)
        self.factory = TemporalPacketFactory("windows")
        self.monitor = DecayMonitor(self.packet_store)
        
        # Node reference (set during boot)
        self.node: Optional[JarvisNode] = None
    
    def boot(self, node: JarvisNode = None) -> Dict:
        """
        Boot the temporal packet system.
        Called by BootFairy during system startup.
        """
        self.node = node
        
        results = {
            "temporal_system": "initialized",
            "lesson_store": len(self.lesson_store.lessons),
            "pending_packets": 0,
            "decay_status": {}
        }
        
        # Scan current state
        results["decay_status"] = self.monitor.scan()
        results["pending_packets"] = results["decay_status"]["total"]
        
        # Clean up expired packets
        expired = results["decay_status"]["expired"]
        for packet_id in expired:
            self._archive_expired(packet_id)
        
        results["archived_expired"] = len(expired)
        
        return results
    
    def _archive_expired(self, packet_id: str):
        """Archive an expired packet"""
        packet = self.monitor.active_packets.get(packet_id)
        if not packet:
            return
        
        # Move to archive
        for dir_name in ["inbox", "outbox"]:
            src = self.packet_store.storage_path / dir_name / f"{packet_id}.json"
            if src.exists():
                archive = self.packet_store.storage_path / "archive"
                archive.mkdir(exist_ok=True)
                src.rename(archive / src.name)
                break
    
    def add_lesson(self, title: str, content: str,
                   category: str = "general",
                   for_fairies: List[str] = None,
                   importance: float = 1.5) -> str:
        """
        Add a lesson through the GUI or API.
        
        Returns lesson ID.
        """
        packet = self.factory.lesson(
            title=title,
            content=content,
            category=category,
            for_fairies=for_fairies,
            importance=importance
        )
        
        # Store in packet system
        self.packet_store.store(packet, outgoing=True)
        
        # Also store in lesson store
        lesson_id = self.lesson_store.add_from_packet(packet)
        
        return lesson_id
    
    def get_lessons_for_fairy(self, fairy_name: str) -> List[Dict]:
        """Get lessons applicable to a fairy"""
        lessons = self.lesson_store.get_for_fairy(fairy_name)
        return [l.to_dict() for l in lessons]
    
    def get_monitoring_data(self) -> Dict:
        """Get data for monitoring GUI"""
        decay_status = self.monitor.scan()
        
        return {
            "timestamp": time.time(),
            "packets": {
                "total": decay_status["total"],
                "by_profile": decay_status["by_profile"],
                "by_urgency": decay_status["by_urgency"],
                "expiring_soon": len(decay_status["expiring_soon"]),
                "permanent": len(decay_status["permanent"])
            },
            "lessons": {
                "total": len(self.lesson_store.lessons),
                "stats": self.lesson_store.get_stats()
            },
            "expiring_soon_details": decay_status["expiring_soon"][:10]
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Decay
    'DecayProfile',
    'DecayConfig',
    'DECAY_TTL',
    'SUCCESS_MULTIPLIERS',
    
    # Packets
    'TemporalPacket',
    'TemporalPacketFactory',
    
    # Lessons
    'Lesson',
    'LessonStore',
    
    # Monitoring
    'DecayMonitor',
    
    # Boot
    'TemporalBootIntegration'
]
