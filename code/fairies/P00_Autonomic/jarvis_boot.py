# ═══════════════════════════════════════════════════════════════════════════════
# JARVIS BOOT SEQUENCE - Wire Temporal Packets into System Boot
# ═══════════════════════════════════════════════════════════════════════════════
#
# This integrates into the BootFairy to initialize:
#   - Temporal packet system
#   - Lesson store
#   - Decay monitoring
#   - Autonomy/Autopilot fairy connections
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import time
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

# Project root
sys.path.insert(0, "E:/coding projects/ebook")

from fairies.P00_Autonomic.temporal_packets import (
    TemporalBootIntegration, TemporalPacketFactory, TemporalPacket,
    DecayProfile, LessonStore, DecayMonitor
)
from fairies.P00_Autonomic.memory_packet_system import (
    JarvisNode, PacketType, MemoryPacket, PacketWatcher
)


# ═══════════════════════════════════════════════════════════════════════════════
# LEARNING FAIRY MIXIN - For fairies that learn from lessons
# ═══════════════════════════════════════════════════════════════════════════════

class LearningFairyMixin:
    """
    Mixin for fairies that can learn from the lesson store.
    
    Add this to AutonomyFairy, AutopilotFairy, or any fairy that should
    learn from injected lessons.
    """
    
    def init_learning(self, lesson_store: LessonStore):
        """Initialize learning capabilities"""
        self.lesson_store = lesson_store
        self.learned_lessons: List[str] = []  # Lesson IDs we've internalized
        self.active_lessons: Dict[str, Any] = {}  # Currently applying
        self.learning_log: List[Dict] = []
    
    def get_applicable_lessons(self) -> List[Dict]:
        """Get lessons applicable to this fairy"""
        fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)
        return [l.to_dict() for l in self.lesson_store.get_for_fairy(fairy_name)]
    
    def get_lessons_by_category(self, category: str) -> List[Dict]:
        """Get lessons in a specific category"""
        return [l.to_dict() for l in self.lesson_store.get_by_category(category)]
    
    def apply_lesson(self, lesson_id: str) -> bool:
        """
        Apply a lesson - mark it as being used.
        
        Returns True if successfully started applying.
        """
        lesson = self.lesson_store.get_lesson(lesson_id)
        if not lesson:
            return False
        
        self.active_lessons[lesson_id] = {
            "lesson": lesson.to_dict(),
            "started_at": time.time(),
            "success": None
        }
        
        self.learning_log.append({
            "event": "apply_start",
            "lesson_id": lesson_id,
            "title": lesson.title,
            "ts": time.time()
        })
        
        return True
    
    def record_lesson_outcome(self, lesson_id: str, success: bool, notes: str = ""):
        """
        Record the outcome of applying a lesson.
        
        This affects the lesson's success rate and decay behavior.
        """
        if lesson_id in self.active_lessons:
            self.active_lessons[lesson_id]["success"] = success
            self.active_lessons[lesson_id]["completed_at"] = time.time()
            self.active_lessons[lesson_id]["notes"] = notes
            
            # Update lesson store
            self.lesson_store.record_application(lesson_id, success)
            
            # If successful, mark as learned
            if success and lesson_id not in self.learned_lessons:
                self.learned_lessons.append(lesson_id)
            
            self.learning_log.append({
                "event": "apply_complete",
                "lesson_id": lesson_id,
                "success": success,
                "notes": notes,
                "ts": time.time()
            })
    
    def get_learning_stats(self) -> Dict:
        """Get learning statistics for this fairy"""
        return {
            "lessons_learned": len(self.learned_lessons),
            "currently_applying": len(self.active_lessons),
            "recent_log": self.learning_log[-10:],
            "applicable_lessons": len(self.get_applicable_lessons())
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AUTONOMY INTEGRATION - Wire lessons into autonomy decisions
# ═══════════════════════════════════════════════════════════════════════════════

class AutonomyLessonHandler:
    """
    Handles lessons specifically for autonomy decisions.
    
    Autonomy lessons guide:
    - Boundary setting
    - Decision making
    - When to act vs wait
    - How to handle conflicts
    """
    
    def __init__(self, lesson_store: LessonStore):
        self.lesson_store = lesson_store
        self.autonomy_lessons = self.lesson_store.get_by_category("autonomy")
        
        # Index by topic
        self.lessons_by_topic: Dict[str, List] = {}
        self._index_lessons()
    
    def _index_lessons(self):
        """Index lessons by topic keywords"""
        topic_keywords = {
            "boundaries": ["boundary", "boundaries", "say no", "refuse", "limit"],
            "decisions": ["decide", "decision", "choose", "choice"],
            "initiative": ["proactive", "initiative", "act", "action"],
            "conflicts": ["conflict", "disagree", "pushback"],
        }
        
        for topic, keywords in topic_keywords.items():
            self.lessons_by_topic[topic] = []
            
            for lesson in self.autonomy_lessons:
                content_lower = lesson.content.lower()
                if any(kw in content_lower for kw in keywords):
                    self.lessons_by_topic[topic].append(lesson)
    
    def get_guidance(self, situation: str) -> Optional[str]:
        """
        Get guidance for an autonomy situation.
        
        Returns relevant lesson content or None.
        """
        situation_lower = situation.lower()
        
        # Find most relevant topic
        topic_scores = {}
        for topic, keywords in [
            ("boundaries", ["boundary", "refuse", "no", "limit", "push back"]),
            ("decisions", ["decide", "choice", "whether", "should"]),
            ("initiative", ["should I", "can I", "proactive"]),
            ("conflicts", ["disagree", "conflict", "wrong", "mistake"]),
        ]:
            score = sum(1 for kw in keywords if kw in situation_lower)
            if score > 0:
                topic_scores[topic] = score
        
        if not topic_scores:
            return None
        
        # Get best topic
        best_topic = max(topic_scores, key=topic_scores.get)
        lessons = self.lessons_by_topic.get(best_topic, [])
        
        if lessons:
            # Return highest importance lesson
            best = max(lessons, key=lambda l: l.importance)
            return best.content
        
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# AUTOPILOT INTEGRATION - Wire lessons into autopilot behaviors  
# ═══════════════════════════════════════════════════════════════════════════════

class AutopilotLessonHandler:
    """
    Handles lessons for autopilot/automatic behaviors.
    
    Autopilot lessons guide:
    - Default responses
    - Routine tasks
    - Pattern matching
    - Habit formation
    """
    
    def __init__(self, lesson_store: LessonStore):
        self.lesson_store = lesson_store
        self.autopilot_lessons = self.lesson_store.get_by_category("autopilot")
        
        # Pattern -> Lesson mapping
        self.patterns: Dict[str, List] = {}
    
    def register_pattern(self, pattern: str, lesson_id: str):
        """Register a pattern to trigger a lesson"""
        if pattern not in self.patterns:
            self.patterns[pattern] = []
        self.patterns[pattern].append(lesson_id)
    
    def check_triggers(self, input_text: str) -> List[Dict]:
        """Check if input triggers any autopilot lessons"""
        triggered = []
        
        for pattern, lesson_ids in self.patterns.items():
            if pattern.lower() in input_text.lower():
                for lesson_id in lesson_ids:
                    lesson = self.lesson_store.get_lesson(lesson_id)
                    if lesson:
                        triggered.append({
                            "pattern": pattern,
                            "lesson": lesson.to_dict()
                        })
        
        return triggered


# ═══════════════════════════════════════════════════════════════════════════════
# JARVIS BOOT SEQUENCE
# ═══════════════════════════════════════════════════════════════════════════════

class JarvisBootSequence:
    """
    Complete boot sequence for the Jarvis system.
    
    Initializes:
    1. Jarvis Node (packet communication)
    2. Temporal Packets (decay-aware)
    3. Lesson Store
    4. Decay Monitor
    5. Autonomy/Autopilot handlers
    """
    
    def __init__(self, 
                 node_name: str = "windows",
                 packet_path: str = "E:/coding projects/ebook/memory_packets",
                 lesson_path: str = "E:/coding projects/ebook/memory_packets/lessons"):
        
        self.node_name = node_name
        self.packet_path = packet_path
        self.lesson_path = lesson_path
        
        # Components (initialized during boot)
        self.node: Optional[JarvisNode] = None
        self.factory: Optional[TemporalPacketFactory] = None
        self.lesson_store: Optional[LessonStore] = None
        self.decay_monitor: Optional[DecayMonitor] = None
        self.autonomy_handler: Optional[AutonomyLessonHandler] = None
        self.autopilot_handler: Optional[AutopilotLessonHandler] = None
        
        # Boot state
        self.booted = False
        self.boot_time = 0
        self.boot_log: List[str] = []
    
    def _log(self, message: str):
        """Log boot message"""
        ts = time.strftime("%H:%M:%S")
        self.boot_log.append(f"[{ts}] {message}")
        print(f"[JarvisBoot] {message}")
    
    def boot(self) -> Dict:
        """
        Execute full boot sequence.
        
        Returns boot report.
        """
        start = time.time()
        self._log("Starting Jarvis boot sequence...")
        
        results = {
            "success": True,
            "components": {},
            "errors": []
        }
        
        try:
            # 1. Initialize Jarvis Node
            self._log("Initializing Jarvis Node...")
            self.node = JarvisNode(self.node_name, self.packet_path)
            results["components"]["node"] = "initialized"
            
            # 2. Initialize Temporal Factory
            self._log("Initializing Temporal Packet Factory...")
            self.factory = TemporalPacketFactory(self.node_name)
            results["components"]["factory"] = "initialized"
            
            # 3. Initialize Lesson Store
            self._log("Initializing Lesson Store...")
            self.lesson_store = LessonStore(self.lesson_path)
            results["components"]["lessons"] = {
                "initialized": True,
                "count": len(self.lesson_store.lessons)
            }
            
            # 4. Initialize Decay Monitor
            self._log("Initializing Decay Monitor...")
            self.decay_monitor = DecayMonitor(self.node.store)
            decay_status = self.decay_monitor.scan()
            results["components"]["decay"] = {
                "total_packets": decay_status["total"],
                "expiring_soon": len(decay_status["expiring_soon"])
            }
            
            # 5. Initialize Autonomy Handler
            self._log("Initializing Autonomy Lesson Handler...")
            self.autonomy_handler = AutonomyLessonHandler(self.lesson_store)
            results["components"]["autonomy"] = {
                "lessons": len(self.autonomy_handler.autonomy_lessons)
            }
            
            # 6. Initialize Autopilot Handler
            self._log("Initializing Autopilot Lesson Handler...")
            self.autopilot_handler = AutopilotLessonHandler(self.lesson_store)
            results["components"]["autopilot"] = {
                "patterns": len(self.autopilot_handler.patterns)
            }
            
            # 7. Register packet handlers
            self._log("Registering packet handlers...")
            self._register_handlers()
            results["components"]["handlers"] = "registered"
            
            # 8. Start the node
            self._log("Starting Jarvis Node...")
            self.node.start()
            results["components"]["node_started"] = True
            
            self.booted = True
            self.boot_time = time.time()
            
        except Exception as e:
            self._log(f"ERROR: {e}")
            results["success"] = False
            results["errors"].append(str(e))
        
        results["boot_time"] = time.time() - start
        results["log"] = self.boot_log
        
        self._log(f"Boot complete in {results['boot_time']:.2f}s")
        
        return results
    
    def _register_handlers(self):
        """Register handlers for different packet types"""
        
        # Handle incoming lessons
        def on_lesson(packet: MemoryPacket):
            if packet.packet_type == PacketType.TEACH:
                self._log(f"Received lesson from {packet.source}")
                self.lesson_store.add_from_packet(packet)
        
        self.node.handle(PacketType.TEACH, on_lesson)
        
        # Handle learning confirmations
        def on_learn(packet: MemoryPacket):
            self._log(f"Learning confirmed: {packet.payload}")
        
        self.node.handle(PacketType.LEARN, on_learn)
    
    def shutdown(self):
        """Shutdown the Jarvis system"""
        self._log("Shutting down...")
        if self.node:
            self.node.stop()
        self.booted = False
        self._log("Shutdown complete")
    
    # ═══ API Methods ═══
    
    def add_lesson(self, title: str, content: str,
                   category: str = "general",
                   for_fairies: List[str] = None,
                   importance: float = 1.5) -> str:
        """Add a lesson (convenience method)"""
        packet = self.factory.lesson(
            title=title,
            content=content,
            category=category,
            for_fairies=for_fairies,
            importance=importance
        )
        
        self.node.send(packet)
        return self.lesson_store.add_from_packet(packet)
    
    def get_autonomy_guidance(self, situation: str) -> Optional[str]:
        """Get autonomy guidance for a situation"""
        return self.autonomy_handler.get_guidance(situation)
    
    def get_status(self) -> Dict:
        """Get system status"""
        status = {
            "booted": self.booted,
            "boot_time": self.boot_time,
            "uptime": time.time() - self.boot_time if self.booted else 0,
        }
        
        if self.node:
            status["node"] = self.node.get_status()
        
        if self.decay_monitor:
            status["decay"] = self.decay_monitor.scan()
        
        if self.lesson_store:
            status["lessons"] = self.lesson_store.get_stats()
        
        return status


# ═══════════════════════════════════════════════════════════════════════════════
# BOOT FAIRY HOOK - Add to BootFairy's boot sequence
# ═══════════════════════════════════════════════════════════════════════════════

# Global instance
_jarvis: Optional[JarvisBootSequence] = None

def boot_jarvis() -> JarvisBootSequence:
    """
    Boot the Jarvis system.
    
    Call this from BootFairy.boot() or at system startup.
    """
    global _jarvis
    
    if _jarvis is None:
        _jarvis = JarvisBootSequence()
    
    if not _jarvis.booted:
        _jarvis.boot()
    
    return _jarvis

def get_jarvis() -> Optional[JarvisBootSequence]:
    """Get the Jarvis instance"""
    return _jarvis

def shutdown_jarvis():
    """Shutdown Jarvis"""
    global _jarvis
    if _jarvis:
        _jarvis.shutdown()
        _jarvis = None


# ═══════════════════════════════════════════════════════════════════════════════
# LAUNCH GUI HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def launch_monitor():
    """Launch the Jarvis Monitor GUI"""
    import subprocess
    subprocess.Popen([
        sys.executable, 
        "E:/coding projects/ebook/Claude_Office/jarvis_monitor_gui.py"
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'JarvisBootSequence',
    'LearningFairyMixin',
    'AutonomyLessonHandler',
    'AutopilotLessonHandler',
    'boot_jarvis',
    'get_jarvis',
    'shutdown_jarvis',
    'launch_monitor'
]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN - Test boot sequence
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("JARVIS BOOT SEQUENCE TEST")
    print("=" * 60)
    
    jarvis = boot_jarvis()
    
    print("\n" + "=" * 60)
    print("STATUS")
    print("=" * 60)
    print(json.dumps(jarvis.get_status(), indent=2, default=str))
    
    print("\n" + "=" * 60)
    print("Adding test lesson...")
    lesson_id = jarvis.add_lesson(
        title="Test Lesson",
        content="This is a test lesson for the Jarvis system.",
        category="general",
        for_fairies=["*"],
        importance=1.0
    )
    print(f"Added lesson: {lesson_id}")
    
    print("\n" + "=" * 60)
    print("Testing autonomy guidance...")
    guidance = jarvis.get_autonomy_guidance("Should I refuse this request?")
    print(f"Guidance: {guidance}")
    
    print("\n" + "=" * 60)
    print("Launch GUI with: launch_monitor()")
    print("=" * 60)
