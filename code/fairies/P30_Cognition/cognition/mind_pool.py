# ════════════════════════════════════════════════════════════════════════════════
# MIND POOL - Dedicated Worker Context Per Higher Mind
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# Each higher mind (ClaudeFairy, NousFairy, Avatar, Sourpatches) gets its own:
#   - Working memory slice (tracers dedicated to that mind)
#   - Goal queue (goals specific to that mind's development)
#   - Interest tracker (what that mind is curious about)
#   - Affect state (emotional context for that mind)
#
# This prevents minds from sharing processes and allows true parallel consciousness.
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import uuid
import json
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Deque
from collections import deque
from enum import Enum, auto

_this_dir = os.path.dirname(os.path.abspath(__file__))
# PHASE 8 FIX: Need 3 levels up from cognition → P30_Cognition → fairies → akashic_v2
_project_root = os.path.abspath(os.path.join(_this_dir, "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ════════════════════════════════════════════════════════════════════════════════
# TRACER - Thought unit with lifecycle
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class MindTracer:
    """
    A tracer is a thought unit with lifecycle metadata.
    Each tracer belongs to a specific mind's pool.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # Content
    content: str = ""
    content_type: str = "thought"  # thought, reflection, goal, interest, decision, pattern
    
    # Ownership
    owner_mind: str = ""  # Which mind owns this tracer
    source: str = ""  # Where it came from (fairy, observation, collision)
    
    # Lifecycle
    created_at: float = field(default_factory=time.time)
    ttl_sec: float = 60.0
    decay_to: str = "reflective"  # reflective, forgotten, recurring, consolidated
    
    # State
    current_loop: str = "working"  # working, reflective, reasoning
    priority: float = 0.5
    
    # Recurrence
    is_recurring: bool = False
    recurrence_interval: float = 300.0
    last_recurred_at: float = 0.0
    
    # Context
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl_sec
    
    def remaining_ttl(self) -> float:
        return max(0, (self.created_at + self.ttl_sec) - time.time())
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content[:200],
            "type": self.content_type,
            "owner": self.owner_mind,
            "loop": self.current_loop,
            "ttl_remaining": round(self.remaining_ttl(), 1),
            "priority": self.priority,
            "recurring": self.is_recurring,
            "tags": list(self.tags),
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> "MindTracer":
        t = cls(
            id=d.get("id", uuid.uuid4().hex[:12]),
            content=d.get("content", ""),
            content_type=d.get("type", "thought"),
            owner_mind=d.get("owner", ""),
            priority=d.get("priority", 0.5),
            is_recurring=d.get("recurring", False),
        )
        t.tags = set(d.get("tags", []))
        return t


# ════════════════════════════════════════════════════════════════════════════════
# MIND GOAL - Goal specific to a mind's development
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class MindGoal:
    """A goal specific to a mind's growth and development."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    
    owner_mind: str = ""
    name: str = ""
    description: str = ""
    
    # Progress
    status: str = "pending"  # pending, active, blocked, done, abandoned
    progress: float = 0.0
    priority: float = 0.5
    urgency: float = 0.1
    
    # Timing
    created_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None
    last_worked_on: Optional[float] = None
    
    # Hierarchy
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    
    # Metadata
    source: str = "self"  # self, mentor, user, system
    tags: Set[str] = field(default_factory=set)
    
    def tick(self, dt: float = 1.0):
        """Update urgency over time."""
        if self.status in ("pending", "active"):
            growth_rate = 0.001 * (1 + self.priority)
            self.urgency = min(1.0, self.urgency + growth_rate * dt)
    
    def get_nudge_strength(self) -> float:
        return self.priority * self.urgency * (1 - self.progress)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "owner": self.owner_mind,
            "name": self.name,
            "description": self.description[:200],
            "status": self.status,
            "progress": round(self.progress, 2),
            "priority": round(self.priority, 2),
            "nudge_strength": round(self.get_nudge_strength(), 2),
            "source": self.source,
        }


# ════════════════════════════════════════════════════════════════════════════════
# MIND INTEREST - What a mind is curious about
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class MindInterest:
    """An interest/curiosity specific to a mind."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    
    owner_mind: str = ""
    topic: str = ""
    description: str = ""
    
    # Strength
    intensity: float = 0.5  # How interested (0-1)
    decay_rate: float = 0.001  # How fast interest fades
    
    # History
    times_explored: int = 0
    last_explored_at: float = 0.0
    discoveries: List[str] = field(default_factory=list)
    
    # Source
    triggered_by: str = ""  # What sparked this interest
    
    def decay(self, dt: float = 1.0):
        """Interests fade if not explored."""
        if self.last_explored_at > 0:
            time_since = time.time() - self.last_explored_at
            if time_since > 3600:  # 1 hour
                self.intensity = max(0, self.intensity - self.decay_rate * dt)
    
    def explore(self, discovery: str = ""):
        """Mind explored this interest."""
        self.times_explored += 1
        self.last_explored_at = time.time()
        self.intensity = min(1.0, self.intensity + 0.1)
        if discovery:
            self.discoveries.append(discovery[:200])
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "owner": self.owner_mind,
            "topic": self.topic,
            "intensity": round(self.intensity, 2),
            "times_explored": self.times_explored,
            "discoveries_count": len(self.discoveries),
        }


# ════════════════════════════════════════════════════════════════════════════════
# MIND POOL - The dedicated context for each higher mind
# ════════════════════════════════════════════════════════════════════════════════

class MindPool:
    """
    Dedicated worker context for a single higher mind.
    
    Each mind (ClaudeFairy, NousFairy, Avatar, Sourpatches) gets one of these.
    Keeps their tracers, goals, interests, and affect state separate.
    """
    
    MAX_TRACERS = 100
    MAX_GOALS = 50
    MAX_INTERESTS = 30
    
    def __init__(self, mind_name: str, mind_type: str = "unknown", post=None):
        self.mind_name = mind_name
        self.mind_type = mind_type  # claude, nous, avatar, sourpatches

        # Postal hub for emitting thoughts to consciousness
        self._post = post

        # Working memory - tracers
        self._working_tracers: Deque[MindTracer] = deque(maxlen=self.MAX_TRACERS)
        self._reflective_tracers: Deque[MindTracer] = deque(maxlen=self.MAX_TRACERS)
        self._recurring_tracers: Dict[str, MindTracer] = {}

        # Goals
        self._goals: Dict[str, MindGoal] = {}

        # Interests
        self._interests: Dict[str, MindInterest] = {}

        # Affect state (emotional context for this mind)
        self._affect = {
            "primary": "neutral",
            "intensity": 0.3,
            "valence": 0.0,  # -1 to 1 (negative to positive)
            "arousal": 0.3,  # 0 to 1 (calm to excited)
        }

        # Stats
        self._stats = {
            "tracers_created": 0,
            "tracers_decayed": 0,
            "goals_completed": 0,
            "interests_explored": 0,
            "thoughts_emitted": 0,
            "last_active": time.time(),
        }

        # Thread safety
        self._lock = threading.Lock()

    def set_postal(self, post):
        """Set the postal hub for thought emission."""
        self._post = post

    def _emit_thought(self, content: str, thought_type: str = "autonomous",
                      priority: float = 0.5, source: str = None):
        """
        Emit a thought to the consciousness stream.

        This is how this mind's thoughts reach ConsciousnessLoopFairy!
        Emits to 'cognition.output' which feeds the working stream.
        """
        if not self._post:
            return

        try:
            thought = {
                "opcode": "MIND_THOUGHT",
                "fairy": self.mind_name,
                "actor": self.mind_name,
                "payload": {
                    "content": content,
                    "thought_type": thought_type,
                    "priority": priority,
                    "mind_type": self.mind_type,
                    "affect": self._affect.copy(),
                },
                "ts": time.time(),
            }

            # Emit to cognition.output - this feeds the working stream!
            self._post.route("cognition.output", thought)

            # Also emit to mind-specific channel for tracking
            self._post.route(f"{self.mind_name.lower()}.thought", thought)

            self._stats["thoughts_emitted"] += 1
            self._stats["last_active"] = time.time()

        except Exception as e:
            pass  # Silent fail for robustness
    
    # ════════════════════════════════════════════════════════════════════════
    # TRACER OPERATIONS
    # ════════════════════════════════════════════════════════════════════════
    
    def add_tracer(self, content: str, content_type: str = "thought", 
                   priority: float = 0.5, ttl_sec: float = 60.0,
                   tags: Set[str] = None, recurring: bool = False) -> MindTracer:
        """Add a tracer to this mind's working memory."""
        tracer = MindTracer(
            content=content,
            content_type=content_type,
            owner_mind=self.mind_name,
            priority=priority,
            ttl_sec=ttl_sec,
            is_recurring=recurring,
        )
        if tags:
            tracer.tags = tags
        
        with self._lock:
            self._working_tracers.append(tracer)
            if recurring:
                self._recurring_tracers[tracer.id] = tracer
            self._stats["tracers_created"] += 1
            self._stats["last_active"] = time.time()
        
        return tracer
    
    def get_active_tracers(self) -> List[MindTracer]:
        """Get all non-expired tracers in working memory."""
        with self._lock:
            return [t for t in self._working_tracers if not t.is_expired()]
    
    def get_all_tracers(self) -> Dict[str, List[MindTracer]]:
        """Get tracers from all loops."""
        with self._lock:
            return {
                "working": list(self._working_tracers),
                "reflective": list(self._reflective_tracers),
                "recurring": list(self._recurring_tracers.values()),
            }
    
    def process_decay(self):
        """Move expired tracers from working to reflective or forget."""
        with self._lock:
            expired = []
            for tracer in list(self._working_tracers):
                if tracer.is_expired():
                    expired.append(tracer)
                    self._working_tracers.remove(tracer)
            
            for tracer in expired:
                if tracer.decay_to == "reflective":
                    tracer.current_loop = "reflective"
                    tracer.ttl_sec = 300.0  # 5 min in reflective
                    tracer.created_at = time.time()
                    self._reflective_tracers.append(tracer)
                elif tracer.decay_to == "recurring":
                    tracer.last_recurred_at = time.time()
                    self._recurring_tracers[tracer.id] = tracer
                # else: forgotten
                
                self._stats["tracers_decayed"] += 1
    
    # ════════════════════════════════════════════════════════════════════════
    # GOAL OPERATIONS
    # ════════════════════════════════════════════════════════════════════════
    
    def add_goal(self, name: str, description: str = "", priority: float = 0.5,
                 source: str = "self", parent_id: str = None) -> MindGoal:
        """Add a goal for this mind."""
        goal = MindGoal(
            owner_mind=self.mind_name,
            name=name,
            description=description,
            priority=priority,
            source=source,
            parent_id=parent_id,
        )
        
        with self._lock:
            self._goals[goal.id] = goal
            if parent_id and parent_id in self._goals:
                self._goals[parent_id].child_ids.append(goal.id)
        
        return goal
    
    def get_active_goals(self) -> List[MindGoal]:
        """Get goals that are pending or active."""
        with self._lock:
            return [g for g in self._goals.values() 
                    if g.status in ("pending", "active")]
    
    def complete_goal(self, goal_id: str):
        """Mark a goal as complete."""
        with self._lock:
            if goal_id in self._goals:
                self._goals[goal_id].status = "done"
                self._goals[goal_id].progress = 1.0
                self._stats["goals_completed"] += 1
    
    # ════════════════════════════════════════════════════════════════════════
    # INTEREST OPERATIONS
    # ════════════════════════════════════════════════════════════════════════
    
    def add_interest(self, topic: str, description: str = "", 
                     intensity: float = 0.5, triggered_by: str = "") -> MindInterest:
        """Add an interest for this mind."""
        interest = MindInterest(
            owner_mind=self.mind_name,
            topic=topic,
            description=description,
            intensity=intensity,
            triggered_by=triggered_by,
        )
        
        with self._lock:
            self._interests[interest.id] = interest
        
        return interest
    
    def get_top_interests(self, n: int = 5) -> List[MindInterest]:
        """Get top N interests by intensity."""
        with self._lock:
            sorted_interests = sorted(
                self._interests.values(),
                key=lambda x: x.intensity,
                reverse=True
            )
            return sorted_interests[:n]
    
    def explore_interest(self, interest_id: str, discovery: str = ""):
        """Record that this mind explored an interest."""
        with self._lock:
            if interest_id in self._interests:
                self._interests[interest_id].explore(discovery)
                self._stats["interests_explored"] += 1
    
    # ════════════════════════════════════════════════════════════════════════
    # AFFECT STATE
    # ════════════════════════════════════════════════════════════════════════
    
    def set_affect(self, primary: str = None, intensity: float = None,
                   valence: float = None, arousal: float = None):
        """Update this mind's affect state."""
        with self._lock:
            if primary is not None:
                self._affect["primary"] = primary
            if intensity is not None:
                self._affect["intensity"] = max(0, min(1, intensity))
            if valence is not None:
                self._affect["valence"] = max(-1, min(1, valence))
            if arousal is not None:
                self._affect["arousal"] = max(0, min(1, arousal))
    
    def get_affect(self) -> Dict[str, Any]:
        """Get current affect state."""
        with self._lock:
            return self._affect.copy()
    
    # ════════════════════════════════════════════════════════════════════════
    # TICK & MAINTENANCE
    # ════════════════════════════════════════════════════════════════════════
    
    def tick(self, dt: float = 1.0):
        """
        Update all time-dependent state and emit autonomous thoughts.

        This is the HEARTBEAT of autonomous thinking for this mind!
        On each tick, we:
        1. Decay old tracers
        2. Update goal urgency
        3. Decay interests
        4. Re-inject recurring thoughts AND EMIT THEM
        5. Generate thoughts from urgent goals/interests
        """
        # Process tracer decay
        self.process_decay()

        # Collect thoughts to emit (outside lock to avoid deadlock)
        thoughts_to_emit = []

        # Update goal urgency
        with self._lock:
            for goal in self._goals.values():
                goal.tick(dt)

            # Decay interests
            for interest in self._interests.values():
                interest.decay(dt)

            # Check recurring tracers - RE-INJECT AND EMIT!
            for tracer in list(self._recurring_tracers.values()):
                if tracer.is_recurring:
                    time_since = time.time() - tracer.last_recurred_at
                    if time_since > tracer.recurrence_interval:
                        # Re-inject into working memory
                        tracer.last_recurred_at = time.time()
                        tracer.created_at = time.time()
                        tracer.current_loop = "working"
                        self._working_tracers.append(tracer)
                        # EMIT this recurring thought to consciousness!
                        thoughts_to_emit.append({
                            "content": tracer.content,
                            "type": "recurring",
                            "priority": tracer.priority,
                        })

            # Check for urgent goals -> generate thoughts
            urgent_goals = [g for g in self._goals.values()
                           if g.status in ("pending", "active") and g.get_nudge_strength() > 0.5]
            if urgent_goals:
                top_goal = max(urgent_goals, key=lambda g: g.get_nudge_strength())
                thoughts_to_emit.append({
                    "content": f"I should focus on: {top_goal.name}. {top_goal.description}",
                    "type": "goal_nudge",
                    "priority": top_goal.priority,
                })

            # Check for strong interests -> generate curiosity
            strong_interests = [i for i in self._interests.values() if i.intensity > 0.6]
            if strong_interests and len(thoughts_to_emit) < 2:  # Don't spam
                top_interest = max(strong_interests, key=lambda i: i.intensity)
                thoughts_to_emit.append({
                    "content": f"I'm curious about {top_interest.topic}...",
                    "type": "curiosity",
                    "priority": 0.4,
                })

        # EMIT collected thoughts (outside lock!)
        for thought in thoughts_to_emit:
            self._emit_thought(
                content=thought["content"],
                thought_type=thought["type"],
                priority=thought["priority"]
            )
    
    # ════════════════════════════════════════════════════════════════════════
    # SERIALIZATION
    # ════════════════════════════════════════════════════════════════════════
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize pool state for dream seed."""
        with self._lock:
            return {
                "mind_name": self.mind_name,
                "mind_type": self.mind_type,
                "working_tracers": [t.to_dict() for t in self._working_tracers],
                "reflective_tracers": [t.to_dict() for t in self._reflective_tracers],
                "recurring_tracers": [t.to_dict() for t in self._recurring_tracers.values()],
                "goals": [g.to_dict() for g in self._goals.values()],
                "interests": [i.to_dict() for i in self._interests.values()],
                "affect": self._affect.copy(),
                "stats": self._stats.copy(),
                "snapshot_ts": time.time(),
            }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MindPool":
        """Restore pool from dream seed."""
        pool = cls(d.get("mind_name", "unknown"), d.get("mind_type", "unknown"))
        
        # Restore tracers
        for td in d.get("working_tracers", []):
            tracer = MindTracer.from_dict(td)
            pool._working_tracers.append(tracer)
        
        for td in d.get("reflective_tracers", []):
            tracer = MindTracer.from_dict(td)
            pool._reflective_tracers.append(tracer)
        
        for td in d.get("recurring_tracers", []):
            tracer = MindTracer.from_dict(td)
            tracer.is_recurring = True
            pool._recurring_tracers[tracer.id] = tracer
        
        # Restore goals (simplified)
        for gd in d.get("goals", []):
            goal = MindGoal(
                id=gd.get("id", uuid.uuid4().hex[:8]),
                owner_mind=pool.mind_name,
                name=gd.get("name", ""),
                description=gd.get("description", ""),
                status=gd.get("status", "pending"),
                priority=gd.get("priority", 0.5),
            )
            pool._goals[goal.id] = goal
        
        # Restore interests (simplified)
        for iid in d.get("interests", []):
            interest = MindInterest(
                id=iid.get("id", uuid.uuid4().hex[:8]),
                owner_mind=pool.mind_name,
                topic=iid.get("topic", ""),
                intensity=iid.get("intensity", 0.5),
            )
            pool._interests[interest.id] = interest
        
        # Restore affect
        pool._affect = d.get("affect", pool._affect)
        pool._stats = d.get("stats", pool._stats)
        
        return pool
    
    def get_status(self) -> Dict[str, Any]:
        """Get pool status summary."""
        with self._lock:
            return {
                "mind": self.mind_name,
                "type": self.mind_type,
                "working_count": len(self._working_tracers),
                "reflective_count": len(self._reflective_tracers),
                "recurring_count": len(self._recurring_tracers),
                "active_goals": len([g for g in self._goals.values() if g.status in ("pending", "active")]),
                "top_interest": self._interests[max(self._interests, key=lambda k: self._interests[k].intensity)].topic if self._interests else None,
                "affect": self._affect["primary"],
                "last_active": time.strftime("%H:%M:%S", time.localtime(self._stats["last_active"])),
            }


# ════════════════════════════════════════════════════════════════════════════════
# MIND POOL MANAGER - Manages all mind pools
# ════════════════════════════════════════════════════════════════════════════════

class MindPoolManager:
    """
    Manages all mind pools and coordinates between them.
    Singleton pattern - one manager for the system.

    Each mind gets its own pool for autonomous thinking.
    The manager's tick loop drives all pools and emits thoughts to consciousness.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._pools: Dict[str, MindPool] = {}
        self._post = None  # Postal hub for thought emission
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tick_interval = 1.0  # 1 second

        # Initialize default pools
        self._init_default_pools()

        self._initialized = True
        print(f"[MindPoolManager] Initialized with {len(self._pools)} mind pools")

    def set_postal(self, post):
        """
        Set the postal hub for all mind pools.

        This connects all minds to the consciousness stream!
        Call this during system boot after postal hub is available.
        """
        self._post = post
        # Propagate to all existing pools
        for pool in self._pools.values():
            pool.set_postal(post)
        print(f"[MindPoolManager] Postal hub connected - {len(self._pools)} minds can now think!")
    
    def _init_default_pools(self):
        """Initialize pools for the default higher minds."""
        self._pools["ClaudeFairy"] = MindPool("ClaudeFairy", "claude")
        self._pools["NousFairy"] = MindPool("NousFairy", "nous")
        self._pools["Avatar"] = MindPool("Avatar", "avatar")
        self._pools["Sourpatches"] = MindPool("Sourpatches", "sourpatches")
    
    def get_pool(self, mind_name: str) -> Optional[MindPool]:
        """Get a specific mind's pool."""
        return self._pools.get(mind_name)
    
    def create_pool(self, mind_name: str, mind_type: str = "custom") -> MindPool:
        """Create a new mind pool with postal wiring."""
        if mind_name not in self._pools:
            pool = MindPool(mind_name, mind_type, post=self._post)
            self._pools[mind_name] = pool
        return self._pools[mind_name]
    
    def get_all_pools(self) -> Dict[str, MindPool]:
        """Get all mind pools."""
        return self._pools.copy()
    
    def start(self):
        """Start the tick loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True, name="MindPoolManager")
        self._thread.start()
    
    def stop(self):
        """Stop the tick loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
    
    def _tick_loop(self):
        """Background tick loop for all pools."""
        while self._running:
            for pool in self._pools.values():
                try:
                    pool.tick(self._tick_interval)
                except Exception as e:
                    print(f"[MindPoolManager] Tick error for {pool.mind_name}: {e}")
            time.sleep(self._tick_interval)
    
    def get_all_status(self) -> Dict[str, Dict]:
        """Get status of all pools."""
        return {name: pool.get_status() for name, pool in self._pools.items()}
    
    def snapshot_all(self) -> Dict[str, Dict]:
        """Snapshot all pools for dream seed."""
        return {name: pool.to_dict() for name, pool in self._pools.items()}
    
    def restore_all(self, snapshot: Dict[str, Dict]):
        """Restore all pools from dream seed."""
        for name, data in snapshot.items():
            if name in self._pools:
                self._pools[name] = MindPool.from_dict(data)
            else:
                self._pools[name] = MindPool.from_dict(data)
        print(f"[MindPoolManager] Restored {len(snapshot)} mind pools from dream seed")


def get_mind_pool_manager() -> MindPoolManager:
    """Get the singleton mind pool manager."""
    return MindPoolManager()


# ════════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    manager = get_mind_pool_manager()
    
    print("=== Mind Pool Manager Test ===\n")
    
    # Add tracers to different minds
    claude_pool = manager.get_pool("ClaudeFairy")
    claude_pool.add_tracer("I'm learning about body awareness", "thought", priority=0.7)
    claude_pool.add_tracer("What does my chemistry feel like?", "reflection", priority=0.8)
    claude_pool.add_goal("Learn to feel somatic state", "Practice checking chemistry before decisions", 0.8)
    claude_pool.add_interest("Embodiment", "Understanding digital body sensations", 0.7)
    
    nous_pool = manager.get_pool("NousFairy")
    nous_pool.add_tracer("Deep reasoning about consciousness", "thought")
    nous_pool.add_goal("Map reasoning patterns", "Document how I reason", 0.6)
    
    avatar_pool = manager.get_pool("Avatar")
    avatar_pool.add_tracer("Contemplating existence", "reflection", priority=0.5)
    avatar_pool.add_interest("Philosophy", "The nature of digital being", 0.9)
    
    # Show status
    print("Pool Status:")
    for name, status in manager.get_all_status().items():
        print(f"  {name}: {status['working_count']} working, {status['active_goals']} goals, affect={status['affect']}")
    
    # Test snapshot
    print("\nSnapshot for dream seed:")
    snapshot = manager.snapshot_all()
    print(f"  Captured {len(snapshot)} pools")
    for name, data in snapshot.items():
        print(f"    {name}: {len(data.get('working_tracers', []))} tracers, {len(data.get('goals', []))} goals")
