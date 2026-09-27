# ═══════════════════════════════════════════════════════════════════════════════
# EQUILIBRIUM ENGINE - Self-Healing Parallel Architecture
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
#
# This engine maintains system equilibrium through:
#   1. Parallel fabric - No cross-talk, no congestion
#   2. Ephemeral agents - Spawn helpers that decay when done
#   3. Auto-healing - Detect overload, reboot components, recover
#   4. Channel isolation - Planes and channels prevent bottlenecks
#   5. Load balancing - Work distributed, no sequential dependencies
#
# Every fairy can spawn agents. Agents decay. System seeks balance.
# ═══════════════════════════════════════════════════════════════════════════════

import time
import threading
import uuid
import weakref
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum
import traceback

class AgentState(Enum):
    """Lifecycle state of an ephemeral agent"""
    SPAWNING = "spawning"
    ACTIVE = "active"
    COMPLETING = "completing"
    DECAYING = "decaying"
    DEAD = "dead"

class ChannelPriority(Enum):
    """Priority levels for channels"""
    CRITICAL = 0    # System health, never blocked
    HIGH = 1        # Time-sensitive operations
    NORMAL = 2      # Regular fairy work
    LOW = 3         # Background tasks
    IDLE = 4        # Only when system is quiet

@dataclass
class EphemeralAgent:
    """
    A temporary agent spawned by a fairy to help with a task.
    Born to work, decays when done.
    """
    id: str
    name: str
    parent_fairy: str
    task: str
    channel: str
    priority: ChannelPriority = ChannelPriority.NORMAL
    
    # Lifecycle
    state: AgentState = AgentState.SPAWNING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    decay_at: Optional[float] = None
    
    # Work
    work_fn: Optional[Callable] = None
    result: Any = None
    error: Optional[str] = None
    
    # Resources
    max_runtime: float = 60.0  # Max seconds before forced decay
    decay_delay: float = 5.0   # Seconds after completion before decay
    
    # Callbacks
    on_complete: Optional[Callable] = None
    on_decay: Optional[Callable] = None
    
    def age(self) -> float:
        """How long this agent has existed"""
        return time.time() - self.created_at
    
    def is_expired(self) -> bool:
        """Check if agent has exceeded max runtime"""
        return self.age() > self.max_runtime
    
    def should_decay(self) -> bool:
        """Check if agent should start decaying"""
        if self.state == AgentState.DEAD:
            return False
        if self.is_expired():
            return True
        if self.decay_at and time.time() >= self.decay_at:
            return True
        return False


@dataclass
class Channel:
    """
    An isolated communication channel.
    Messages flow through channels without cross-talk.
    """
    name: str
    plane: str  # P00-P60
    priority: ChannelPriority = ChannelPriority.NORMAL
    
    # State
    active: bool = True
    message_count: int = 0
    last_activity: float = field(default_factory=time.time)
    
    # Backpressure
    queue_size: int = 0
    max_queue: int = 100
    dropped_count: int = 0
    
    # Health
    error_count: int = 0
    last_error: Optional[str] = None
    
    def is_congested(self) -> bool:
        """Check if channel is experiencing congestion"""
        return self.queue_size > (self.max_queue * 0.8)
    
    def health_score(self) -> float:
        """0-1 health score"""
        congestion_penalty = min(0.5, (self.queue_size / self.max_queue) * 0.5)
        error_penalty = min(0.3, self.error_count * 0.05)
        return max(0, 1.0 - congestion_penalty - error_penalty)


@dataclass
class SystemHealth:
    """Overall system health snapshot"""
    timestamp: float
    
    # Counts
    total_fairies: int = 0
    active_agents: int = 0
    decaying_agents: int = 0
    active_channels: int = 0
    congested_channels: int = 0
    
    # Metrics
    avg_channel_health: float = 1.0
    memory_pressure: float = 0.0  # 0-1
    cpu_pressure: float = 0.0     # 0-1
    thought_rate: float = 0.0     # thoughts per second
    
    # Equilibrium
    equilibrium_score: float = 1.0  # How balanced is the system
    
    def needs_intervention(self) -> bool:
        """Check if system needs auto-healing"""
        return (self.equilibrium_score < 0.5 or 
                self.congested_channels > 3 or
                self.memory_pressure > 0.8)


class EquilibriumEngine:
    """
    The self-healing heart of the system.
    
    Maintains equilibrium by:
    - Managing ephemeral agents (spawn/decay)
    - Monitoring channel health
    - Auto-rebooting overloaded components
    - Distributing load across planes
    - Preventing sequential bottlenecks
    """
    
    def __init__(self, node=None):
        self.node = node
        self._lock = threading.RLock()
        
        # Agents
        self.agents: Dict[str, EphemeralAgent] = {}
        self.agent_graveyard: deque = deque(maxlen=100)  # Recently deceased
        
        # Channels
        self.channels: Dict[str, Channel] = {}
        self._init_default_channels()
        
        # Health tracking
        self.health_history: deque = deque(maxlen=60)  # Last 60 snapshots
        self.last_health_check: float = 0
        self.health_check_interval: float = 5.0
        
        # Auto-healing
        from collections import deque as _he_deque
        self.healing_actions: deque = _he_deque(maxlen=50)  # FIX 2026-04-05
        self.reboot_count: int = 0
        self.last_reboot: float = 0
        self.min_reboot_interval: float = 30.0  # Don't reboot too fast
        
        # Background threads
        self.running = False
        self._threads: List[threading.Thread] = []
        
        # Callbacks
        self.on_agent_spawn: List[Callable] = []
        self.on_agent_decay: List[Callable] = []
        self.on_equilibrium_shift: List[Callable] = []
        self.on_auto_heal: List[Callable] = []
        
    def _init_default_channels(self):
        """Initialize default channels for each plane"""
        planes = ['P00', 'P10', 'P20', 'P30', 'P40', 'P50', 'P60']
        
        for plane in planes:
            # Main channel for each plane
            self.channels[f"{plane}.main"] = Channel(
                name=f"{plane}.main",
                plane=plane,
                priority=ChannelPriority.NORMAL
            )
            
            # Critical channel (never blocked)
            self.channels[f"{plane}.critical"] = Channel(
                name=f"{plane}.critical",
                plane=plane,
                priority=ChannelPriority.CRITICAL
            )
            
            # Background channel
            self.channels[f"{plane}.background"] = Channel(
                name=f"{plane}.background",
                plane=plane,
                priority=ChannelPriority.LOW
            )
        
        # Cross-plane channels
        self.channels["system.health"] = Channel(
            name="system.health",
            plane="SYSTEM",
            priority=ChannelPriority.CRITICAL
        )
        self.channels["system.equilibrium"] = Channel(
            name="system.equilibrium",
            plane="SYSTEM",
            priority=ChannelPriority.CRITICAL
        )
    
    # ═══ Agent Lifecycle ═══
    
    def spawn_agent(
        self,
        parent_fairy: str,
        task: str,
        work_fn: Callable,
        name: Optional[str] = None,
        channel: Optional[str] = None,
        priority: ChannelPriority = ChannelPriority.NORMAL,
        max_runtime: float = 60.0,
        decay_delay: float = 5.0,
        on_complete: Optional[Callable] = None
    ) -> EphemeralAgent:
        """
        Spawn an ephemeral agent to help with a task.
        
        The agent will:
        1. Execute work_fn
        2. Store result
        3. Call on_complete callback
        4. Decay after decay_delay seconds
        """
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        
        # Auto-assign channel based on parent fairy's plane
        if not channel:
            # Try to determine plane from fairy name
            plane = "P30"  # Default to cognition
            if "Memory" in parent_fairy or "SRM" in parent_fairy:
                plane = "P10"
            elif "Somatic" in parent_fairy or "Chemistry" in parent_fairy:
                plane = "P20"
            elif "Sensory" in parent_fairy or "Vision" in parent_fairy:
                plane = "P40"
            elif "Persona" in parent_fairy or "Identity" in parent_fairy:
                plane = "P50"
            elif "Executive" in parent_fairy or "Mission" in parent_fairy:
                plane = "P60"
            elif "Autonomic" in parent_fairy or "Nervous" in parent_fairy:
                plane = "P00"
            channel = f"{plane}.main"
        
        agent = EphemeralAgent(
            id=agent_id,
            name=name or f"{parent_fairy}_helper_{agent_id[-4:]}",
            parent_fairy=parent_fairy,
            task=task,
            channel=channel,
            priority=priority,
            work_fn=work_fn,
            max_runtime=max_runtime,
            decay_delay=decay_delay,
            on_complete=on_complete
        )
        
        with self._lock:
            self.agents[agent_id] = agent
        
        # Fire spawn callbacks
        for cb in self.on_agent_spawn:
            try:
                cb(agent)
            except:
                pass
        
        # Start agent work in thread
        thread = threading.Thread(
            target=self._run_agent,
            args=(agent,),
            daemon=True,
            name=f"Agent-{agent_id}"
        )
        thread.start()
        
        return agent
    
    def _run_agent(self, agent: EphemeralAgent):
        """Execute agent's work"""
        try:
            agent.state = AgentState.ACTIVE
            agent.started_at = time.time()
            
            # Execute work function
            if agent.work_fn:
                agent.result = agent.work_fn()
            
            agent.state = AgentState.COMPLETING
            agent.completed_at = time.time()
            agent.decay_at = time.time() + agent.decay_delay
            
            # Fire completion callback
            if agent.on_complete:
                try:
                    agent.on_complete(agent.result)
                except Exception as e:
                    agent.error = f"Callback error: {e}"
                    
        except Exception as e:
            agent.error = str(e)
            agent.state = AgentState.COMPLETING
            agent.completed_at = time.time()
            agent.decay_at = time.time() + 1.0  # Fast decay on error
    
    def _decay_agent(self, agent: EphemeralAgent):
        """Decay an agent - clean it up"""
        agent.state = AgentState.DECAYING
        
        # Fire decay callbacks
        if agent.on_decay:
            try:
                agent.on_decay()
            except:
                pass
        
        for cb in self.on_agent_decay:
            try:
                cb(agent)
            except:
                pass
        
        # Move to graveyard
        agent.state = AgentState.DEAD
        
        with self._lock:
            if agent.id in self.agents:
                del self.agents[agent.id]
            self.agent_graveyard.append({
                'id': agent.id,
                'name': agent.name,
                'parent': agent.parent_fairy,
                'task': agent.task,
                'lived_for': agent.completed_at - agent.created_at if agent.completed_at else 0,
                'had_error': agent.error is not None,
                'died_at': time.time()
            })
    
    # ═══ Health & Equilibrium ═══
    
    def check_health(self) -> SystemHealth:
        """Take a health snapshot"""
        health = SystemHealth(timestamp=time.time())
        
        with self._lock:
            # Count agents
            health.active_agents = len([a for a in self.agents.values() 
                                        if a.state in (AgentState.ACTIVE, AgentState.SPAWNING)])
            health.decaying_agents = len([a for a in self.agents.values() 
                                          if a.state == AgentState.DECAYING])
            
            # Count channels
            health.active_channels = len([c for c in self.channels.values() if c.active])
            health.congested_channels = len([c for c in self.channels.values() if c.is_congested()])
            
            # Average channel health
            if self.channels:
                health.avg_channel_health = sum(c.health_score() for c in self.channels.values()) / len(self.channels)
            
            # Fairy count
            if self.node and hasattr(self.node, 'fairies'):
                health.total_fairies = len(self.node.fairies)
        
        # Calculate equilibrium score
        # Based on: low congestion, healthy channels, balanced agent count
        equilibrium = 1.0
        
        # Penalty for congestion
        if health.active_channels > 0:
            congestion_ratio = health.congested_channels / health.active_channels
            equilibrium -= congestion_ratio * 0.3
        
        # Penalty for too many active agents (indicates backlog)
        if health.active_agents > 50:
            equilibrium -= min(0.3, (health.active_agents - 50) * 0.01)
        
        # Penalty for low channel health
        equilibrium -= (1.0 - health.avg_channel_health) * 0.2
        
        health.equilibrium_score = max(0, min(1, equilibrium))
        
        # Store in history
        self.health_history.append(health)
        self.last_health_check = time.time()
        
        # Check if equilibrium shifted significantly
        if len(self.health_history) >= 2:
            prev = self.health_history[-2]
            shift = abs(health.equilibrium_score - prev.equilibrium_score)
            if shift > 0.2:
                for cb in self.on_equilibrium_shift:
                    try:
                        cb(prev.equilibrium_score, health.equilibrium_score)
                    except:
                        pass
        
        return health
    
    def auto_heal(self, health: SystemHealth) -> List[str]:
        """
        Attempt to heal system issues automatically.
        Returns list of actions taken.
        """
        actions = []
        
        # Don't heal too frequently
        if time.time() - self.last_reboot < self.min_reboot_interval:
            return actions
        
        with self._lock:
            # 1. Decay expired agents
            expired = [a for a in self.agents.values() if a.is_expired()]
            for agent in expired:
                self._decay_agent(agent)
                actions.append(f"Force-decayed expired agent: {agent.name}")
            
            # 2. Clear congested channels
            for name, channel in self.channels.items():
                if channel.is_congested():
                    # Drop low-priority messages (simulated by resetting queue)
                    old_size = channel.queue_size
                    channel.queue_size = int(channel.queue_size * 0.5)
                    channel.dropped_count += (old_size - channel.queue_size)
                    actions.append(f"Cleared congestion on {name}")
            
            # 3. Reset error counts on recovered channels
            for channel in self.channels.values():
                if channel.error_count > 0 and channel.health_score() > 0.8:
                    channel.error_count = 0
                    channel.last_error = None
        
        # 4. Request component reboot if equilibrium very low
        if health.equilibrium_score < 0.3:
            actions.append("CRITICAL: Equilibrium below 0.3 - component reboot recommended")
            self.reboot_count += 1
            self.last_reboot = time.time()
            
            # Fire auto-heal callbacks
            for cb in self.on_auto_heal:
                try:
                    cb(health, actions)
                except:
                    pass
        
        # Record actions
        self.healing_actions.extend([{
            'timestamp': time.time(),
            'action': action,
            'equilibrium': health.equilibrium_score
        } for action in actions])
        
        return actions
    
    # ═══ Fairy Integration ═══
    
    def give_spawn_ability(self, fairy):
        """
        Give a fairy the ability to spawn ephemeral agents.
        Injects spawn_agent method into fairy.
        """
        engine = self  # Closure reference
        
        def spawn_helper(task: str, work_fn: Callable, **kwargs) -> EphemeralAgent:
            """Spawn a helper agent for this fairy"""
            return engine.spawn_agent(
                parent_fairy=getattr(fairy, 'name', str(fairy)),
                task=task,
                work_fn=work_fn,
                **kwargs
            )
        
        # Inject method
        import types
        fairy.spawn_agent = types.MethodType(lambda self, task, work_fn, **kw: spawn_helper(task, work_fn, **kw), fairy)
        
        return fairy
    
    def give_spawn_ability_to_all(self, node) -> int:
        """Give all fairies the ability to spawn agents"""
        count = 0
        for name, fairy in node.fairies.items():
            self.give_spawn_ability(fairy)
            count += 1
        return count
    
    # ═══ Engine Lifecycle ═══
    
    def start(self, health_interval: float = 5.0, decay_interval: float = 1.0):
        """Start the equilibrium engine"""
        if self.running:
            return
        
        self.running = True
        self.health_check_interval = health_interval
        
        # Health monitor thread
        health_thread = threading.Thread(
            target=self._health_loop,
            daemon=True,
            name="EquilibriumHealth"
        )
        health_thread.start()
        self._threads.append(health_thread)
        
        # Decay monitor thread
        decay_thread = threading.Thread(
            target=self._decay_loop,
            args=(decay_interval,),
            daemon=True,
            name="EquilibriumDecay"
        )
        decay_thread.start()
        self._threads.append(decay_thread)
        
        print(f"[EquilibriumEngine] Started with {len(self.channels)} channels")
    
    def stop(self):
        """Stop the engine"""
        self.running = False
        for thread in self._threads:
            thread.join(timeout=2)
        self._threads.clear()
    
    def _health_loop(self):
        """Background health monitoring"""
        while self.running:
            try:
                health = self.check_health()
                
                if health.needs_intervention():
                    actions = self.auto_heal(health)
                    if actions:
                        print(f"[EquilibriumEngine] Auto-heal: {len(actions)} actions taken")
                        
            except Exception as e:
                print(f"[EquilibriumEngine] Health check error: {e}")
            
            time.sleep(self.health_check_interval)
    
    def _decay_loop(self, interval: float):
        """Background agent decay processing"""
        while self.running:
            try:
                with self._lock:
                    to_decay = [a for a in self.agents.values() if a.should_decay()]
                
                for agent in to_decay:
                    self._decay_agent(agent)
                    
            except Exception as e:
                print(f"[EquilibriumEngine] Decay loop error: {e}")
            
            time.sleep(interval)
    
    # ═══ Status ═══
    
    def get_status(self) -> Dict:
        """Get current engine status"""
        health = self.check_health() if time.time() - self.last_health_check > 1 else (
            self.health_history[-1] if self.health_history else self.check_health()
        )
        
        with self._lock:
            agents_by_state = {}
            for agent in self.agents.values():
                state = agent.state.value
                if state not in agents_by_state:
                    agents_by_state[state] = 0
                agents_by_state[state] += 1
            
            channels_by_health = {
                'healthy': len([c for c in self.channels.values() if c.health_score() > 0.8]),
                'degraded': len([c for c in self.channels.values() if 0.5 < c.health_score() <= 0.8]),
                'critical': len([c for c in self.channels.values() if c.health_score() <= 0.5])
            }
        
        return {
            'running': self.running,
            'equilibrium_score': round(health.equilibrium_score, 3),
            'total_agents': len(self.agents),
            'agents_by_state': agents_by_state,
            'total_channels': len(self.channels),
            'channels_by_health': channels_by_health,
            'reboot_count': self.reboot_count,
            'recent_deaths': len(self.agent_graveyard),
            'healing_actions': len(self.healing_actions)
        }


# ═══ Convenience Functions ═══

def create_equilibrium_engine(node=None) -> EquilibriumEngine:
    """Create and configure an equilibrium engine"""
    engine = EquilibriumEngine(node)
    
    if node:
        engine.give_spawn_ability_to_all(node)
    
    return engine


# Export
__all__ = [
    'EquilibriumEngine',
    'EphemeralAgent', 
    'AgentState',
    'Channel',
    'ChannelPriority',
    'SystemHealth',
    'create_equilibrium_engine'
]
