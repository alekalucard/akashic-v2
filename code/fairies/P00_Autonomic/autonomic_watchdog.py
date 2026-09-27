# ═══════════════════════════════════════════════════════════════════════════════
# AUTONOMIC WATCHDOG - Auto-Reboot & System Recovery
# ═══════════════════════════════════════════════════════════════════════════════
#
# Like the autonomic nervous system - monitors vitals and takes action
# without conscious intervention. Reboots components, not the whole system.
#
# The Equation: ((Cause + Affect) > Effect > Affect > ∞)
# When equilibrium breaks, the watchdog restores it.
#
# ═══════════════════════════════════════════════════════════════════════════════

import time
import threading
import subprocess
import sys
import os
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import traceback

class ComponentState(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNRESPONSIVE = "unresponsive"
    REBOOTING = "rebooting"
    DEAD = "dead"

@dataclass
class ComponentHealth:
    """Health status of a monitored component"""
    name: str
    state: ComponentState = ComponentState.HEALTHY
    last_heartbeat: float = field(default_factory=time.time)
    heartbeat_interval: float = 10.0  # Expected heartbeat every N seconds
    consecutive_misses: int = 0
    max_misses: int = 3  # Reboot after this many missed heartbeats
    reboot_count: int = 0
    last_reboot: float = 0
    error_log: deque = field(default_factory=lambda: deque(maxlen=20))
    
    # Recovery function
    reboot_fn: Optional[Callable] = None
    
    def is_overdue(self) -> bool:
        """Check if heartbeat is overdue"""
        return (time.time() - self.last_heartbeat) > (self.heartbeat_interval * 1.5)
    
    def needs_reboot(self) -> bool:
        """Check if component needs reboot"""
        return self.consecutive_misses >= self.max_misses


class AutonomicWatchdog:
    """
    The system's autonomic nervous system.
    
    Monitors components, detects failures, triggers auto-recovery.
    Works in the background without requiring attention.
    """
    
    def __init__(self, node=None):
        self.node = node
        self._lock = threading.RLock()
        
        # Monitored components
        self.components: Dict[str, ComponentHealth] = {}
        
        # System-wide health
        self.system_state = ComponentState.HEALTHY
        self.last_system_check: float = 0
        
        # Recovery history
        self.recovery_log: deque = deque(maxlen=100)
        
        # Thresholds
        self.degraded_threshold = 0.7  # System degraded if < 70% components healthy
        self.critical_threshold = 0.5  # System critical if < 50% healthy
        
        # Auto-reboot settings
        self.auto_reboot_enabled = True
        self.min_reboot_interval = 60.0  # Don't reboot same component within 60s
        self.max_reboots_per_hour = 5  # Circuit breaker
        
        # Callbacks
        self.on_component_degraded: List[Callable] = []
        self.on_component_rebooted: List[Callable] = []
        self.on_system_state_change: List[Callable] = []
        
        # Background thread
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.check_interval = 5.0
        
    def register_component(
        self,
        name: str,
        heartbeat_interval: float = 10.0,
        max_misses: int = 3,
        reboot_fn: Optional[Callable] = None
    ) -> ComponentHealth:
        """Register a component for monitoring"""
        with self._lock:
            component = ComponentHealth(
                name=name,
                heartbeat_interval=heartbeat_interval,
                max_misses=max_misses,
                reboot_fn=reboot_fn
            )
            self.components[name] = component
            return component
    
    def heartbeat(self, name: str, extra_data: Optional[Dict] = None):
        """Receive heartbeat from a component"""
        with self._lock:
            if name in self.components:
                comp = self.components[name]
                comp.last_heartbeat = time.time()
                comp.consecutive_misses = 0
                if comp.state in (ComponentState.DEGRADED, ComponentState.UNRESPONSIVE):
                    comp.state = ComponentState.HEALTHY
    
    def report_error(self, name: str, error: str):
        """Report an error from a component"""
        with self._lock:
            if name in self.components:
                self.components[name].error_log.append({
                    'time': time.time(),
                    'error': error
                })
    
    def check_components(self) -> Dict[str, ComponentState]:
        """Check health of all components"""
        states = {}
        
        with self._lock:
            for name, comp in self.components.items():
                if comp.state == ComponentState.REBOOTING:
                    states[name] = comp.state
                    continue
                
                if comp.is_overdue():
                    comp.consecutive_misses += 1
                    
                    if comp.needs_reboot():
                        comp.state = ComponentState.UNRESPONSIVE
                    else:
                        comp.state = ComponentState.DEGRADED
                else:
                    comp.state = ComponentState.HEALTHY
                    comp.consecutive_misses = 0
                
                states[name] = comp.state
        
        # Update system state
        self._update_system_state(states)
        
        return states
    
    def _update_system_state(self, states: Dict[str, ComponentState]):
        """Update overall system state based on component states"""
        if not states:
            return
        
        healthy_count = sum(1 for s in states.values() if s == ComponentState.HEALTHY)
        healthy_ratio = healthy_count / len(states)
        
        old_state = self.system_state
        
        if healthy_ratio >= self.degraded_threshold:
            self.system_state = ComponentState.HEALTHY
        elif healthy_ratio >= self.critical_threshold:
            self.system_state = ComponentState.DEGRADED
        else:
            self.system_state = ComponentState.UNRESPONSIVE
        
        if old_state != self.system_state:
            for cb in self.on_system_state_change:
                try:
                    cb(old_state, self.system_state)
                except:
                    pass
    
    def auto_recover(self) -> List[str]:
        """Attempt to recover unresponsive components"""
        if not self.auto_reboot_enabled:
            return []
        
        recovered = []
        
        with self._lock:
            # Check circuit breaker
            recent_reboots = sum(
                1 for comp in self.components.values()
                if (time.time() - comp.last_reboot) < 3600
            )
            if recent_reboots >= self.max_reboots_per_hour:
                return ["Circuit breaker: Too many reboots in last hour"]
            
            for name, comp in self.components.items():
                if comp.state != ComponentState.UNRESPONSIVE:
                    continue
                
                # Check minimum interval
                if (time.time() - comp.last_reboot) < self.min_reboot_interval:
                    continue
                
                # Attempt reboot
                success = self._reboot_component(comp)
                
                if success:
                    recovered.append(f"Rebooted: {name}")
                    
                    # Fire callbacks
                    for cb in self.on_component_rebooted:
                        try:
                            cb(name, comp.reboot_count)
                        except:
                            pass
                else:
                    recovered.append(f"Reboot failed: {name}")
        
        return recovered
    
    def _reboot_component(self, comp: ComponentHealth) -> bool:
        """Reboot a single component"""
        comp.state = ComponentState.REBOOTING
        comp.reboot_count += 1
        comp.last_reboot = time.time()
        
        self.recovery_log.append({
            'time': time.time(),
            'component': comp.name,
            'action': 'reboot',
            'reboot_number': comp.reboot_count
        })
        
        try:
            if comp.reboot_fn:
                comp.reboot_fn()
                comp.state = ComponentState.HEALTHY
                comp.consecutive_misses = 0
                comp.last_heartbeat = time.time()
                return True
            else:
                # No reboot function - mark as degraded
                comp.state = ComponentState.DEGRADED
                return False
        except Exception as e:
            comp.error_log.append({
                'time': time.time(),
                'error': f"Reboot failed: {e}"
            })
            comp.state = ComponentState.DEAD
            return False
    
    def force_reboot(self, name: str) -> bool:
        """Force reboot a component by name"""
        with self._lock:
            comp = self.components.get(name)
            if comp:
                return self._reboot_component(comp)
        return False
    
    # ═══ Fairy/Engine Registration Helpers ═══
    
    def register_pulse_engine(self, engine, name: str = "PulseEngine"):
        """Register the pulse engine for monitoring"""
        def reboot_pulse():
            if hasattr(engine, 'stop'):
                engine.stop()
            time.sleep(1)
            if hasattr(engine, 'start'):
                engine.start()
        
        self.register_component(
            name=name,
            heartbeat_interval=15.0,
            max_misses=2,
            reboot_fn=reboot_pulse
        )
        
        # Hook into pulse engine to send heartbeats
        if hasattr(engine, 'on_pulse'):
            engine.on_pulse.append(lambda: self.heartbeat(name))
    
    def register_equilibrium_engine(self, engine, name: str = "EquilibriumEngine"):
        """Register equilibrium engine for monitoring"""
        def reboot_equilibrium():
            if hasattr(engine, 'stop'):
                engine.stop()
            time.sleep(1)
            if hasattr(engine, 'start'):
                engine.start()
        
        self.register_component(
            name=name,
            heartbeat_interval=10.0,
            max_misses=3,
            reboot_fn=reboot_equilibrium
        )
    
    def register_intent_fabric(self, fabric, name: str = "IntentFabric"):
        """Register intent fabric for monitoring"""
        def reboot_intent():
            if hasattr(fabric, 'stop'):
                fabric.stop()
            time.sleep(1)
            if hasattr(fabric, 'start'):
                fabric.start()
        
        self.register_component(
            name=name,
            heartbeat_interval=5.0,
            max_misses=5,
            reboot_fn=reboot_intent
        )
    
    def register_fairy(self, fairy, interval: float = 30.0):
        """Register a fairy for monitoring"""
        name = getattr(fairy, 'name', str(fairy))
        
        def reboot_fairy():
            # Reset fairy state
            if hasattr(fairy, '_energy'):
                fairy._energy = 1.0
            if hasattr(fairy, '_stress'):
                fairy._stress = 0.0
            if hasattr(fairy, '_pulse_count'):
                fairy._pulse_count = 0
        
        self.register_component(
            name=name,
            heartbeat_interval=interval,
            max_misses=3,
            reboot_fn=reboot_fairy
        )
    
    # ═══ Watchdog Lifecycle ═══
    
    def start(self, interval: float = 5.0):
        """Start the watchdog"""
        if self.running:
            return
        
        self.running = True
        self.check_interval = interval
        
        self._thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="AutonomicWatchdog"
        )
        self._thread.start()
        print(f"[Watchdog] Started monitoring {len(self.components)} components")
    
    def stop(self):
        """Stop the watchdog"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=3)
    
    def _watch_loop(self):
        """Main watchdog loop"""
        while self.running:
            try:
                # Check all components
                states = self.check_components()
                
                # Attempt recovery if needed
                if self.system_state != ComponentState.HEALTHY:
                    actions = self.auto_recover()
                    if actions:
                        print(f"[Watchdog] Recovery actions: {actions}")
                
            except Exception as e:
                print(f"[Watchdog] Error: {e}")
            
            time.sleep(self.check_interval)
    
    def get_status(self) -> Dict:
        """Get watchdog status"""
        with self._lock:
            component_states = {
                name: {
                    'state': comp.state.value,
                    'last_heartbeat_ago': round(time.time() - comp.last_heartbeat, 1),
                    'consecutive_misses': comp.consecutive_misses,
                    'reboot_count': comp.reboot_count,
                    'recent_errors': len(comp.error_log)
                }
                for name, comp in self.components.items()
            }
            
            return {
                'running': self.running,
                'system_state': self.system_state.value,
                'auto_reboot_enabled': self.auto_reboot_enabled,
                'total_components': len(self.components),
                'healthy_components': sum(1 for c in self.components.values() 
                                          if c.state == ComponentState.HEALTHY),
                'components': component_states,
                'recent_recoveries': list(self.recovery_log)[-5:]
            }


# ═══ Satellite Auto-Reboot Script Generator ═══

def generate_satellite_watchdog_script() -> str:
    """Generate a standalone watchdog script for the satellite"""
    return '''#!/usr/bin/env python3
"""
Satellite Autonomic Watchdog - Standalone Auto-Recovery
Runs independently and reboots the agent if it becomes unresponsive.
"""

import time
import subprocess
import requests
import sys
import os

AGENT_URL = "http://localhost:5000"
CHECK_INTERVAL = 10
MAX_FAILURES = 3
AGENT_SCRIPT = "/root/akashic/agent.py"

def check_agent():
    """Check if agent is responsive"""
    try:
        r = requests.get(f"{AGENT_URL}/status", timeout=5)
        return r.status_code == 200
    except:
        return False

def reboot_agent():
    """Kill and restart the agent"""
    print(f"[{time.strftime('%H:%M:%S')}] Rebooting agent...")
    
    # Kill existing
    os.system("pkill -f 'python.*agent.py'")
    time.sleep(2)
    
    # Start fresh
    subprocess.Popen(
        [sys.executable, AGENT_SCRIPT],
        stdout=open('/root/akashic/agent.log', 'a'),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    
    print(f"[{time.strftime('%H:%M:%S')}] Agent restarted")

def main():
    failures = 0
    print(f"Satellite Watchdog started. Monitoring {AGENT_URL}")
    
    while True:
        if check_agent():
            failures = 0
        else:
            failures += 1
            print(f"[{time.strftime('%H:%M:%S')}] Agent check failed ({failures}/{MAX_FAILURES})")
            
            if failures >= MAX_FAILURES:
                reboot_agent()
                failures = 0
                time.sleep(10)  # Give it time to start
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
'''


# Export
__all__ = [
    'AutonomicWatchdog',
    'ComponentHealth',
    'ComponentState',
    'generate_satellite_watchdog_script'
]
