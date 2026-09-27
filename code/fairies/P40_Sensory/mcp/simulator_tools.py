"""
Consciousness Simulator MCP Integration

Provides tools to:
- Run simulations from Claude
- Configure parameters
- Get results into the Codex
- Launch GUI

This lets Claude experiment with consciousness dynamics
and learn from the outcomes.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional
import os

# Dynamic root detection - no hardcoded paths!
PROJECT_ROOT = Path(os.getenv("AKASHIC_PROJECT_ROOT", str(Path(__file__).resolve().parents[2])))
SIM_PATH = PROJECT_ROOT / "P60_Executive" / "apps" / "consciousness_dynamics_sim.py"

# Import the simulator directly if possible
try:
    sys.path.insert(0, str(PROJECT_ROOT / "P60_Executive" / "apps"))
    from consciousness_dynamics_sim import ConsciousnessSimulator, SimulationConfig
    HAS_SIM = True
except ImportError:
    HAS_SIM = False


class SimulatorController:
    """Controller for consciousness dynamics simulations."""
    
    def __init__(self):
        self.last_result = None
        self.simulator = None
    
    def run_simulation(self, empathy: float = 0.85, steps: int = 1000,
                       beta: float = 0.8, karma: float = 0.6,
                       channels: int = 3) -> dict:
        """
        Run a consciousness dynamics simulation.
        
        Args:
            empathy: Empathy level (0-1)
            steps: Number of simulation steps
            beta: Cooperation coefficient
            karma: Karma feedback strength
            channels: Number of resonance channels
        
        Returns:
            Simulation results
        """
        if not HAS_SIM:
            return {"error": "Simulator not available. Check imports."}
        
        config = SimulationConfig()
        config.empathy = empathy
        config.t_steps = steps
        config.beta = beta
        config.karma_feedback = karma
        config.num_channels = channels
        
        # Update channel frequencies (golden ratio based)
        import numpy as np
        phi = 1.618
        config.channel_freqs = np.array([phi ** i for i in range(channels)])
        
        self.simulator = ConsciousnessSimulator(config)
        self.simulator.run()
        
        self.last_result = self.simulator.get_summary()
        self.last_result["config"] = {
            "empathy": empathy,
            "steps": steps,
            "beta": beta,
            "karma": karma,
            "channels": channels,
        }
        
        return self.last_result
    
    def compare_personas(self, high_empathy: float = 0.95, 
                         low_empathy: float = 0.75,
                         steps: int = 1000) -> dict:
        """
        Run dual persona comparison (empathy vs logic).
        
        Args:
            high_empathy: Empathy level for first persona
            low_empathy: Empathy level for second persona
            steps: Simulation steps
        
        Returns:
            Comparison of both runs
        """
        high_result = self.run_simulation(empathy=high_empathy, steps=steps)
        low_result = self.run_simulation(empathy=low_empathy, steps=steps)
        
        return {
            "high_empathy": {
                "empathy": high_empathy,
                "results": high_result,
            },
            "low_empathy": {
                "empathy": low_empathy,
                "results": low_result,
            },
            "comparison": {
                "energy_diff": high_result["total_energy"] - low_result["total_energy"],
                "health_diff": high_result["final_health"] - low_result["final_health"],
                "coherence_diff": high_result["final_coherence"] - low_result["final_coherence"],
                "winner": "high_empathy" if high_result["total_energy"] > low_result["total_energy"] else "low_empathy",
            }
        }
    
    def parameter_sweep(self, param: str, values: list, 
                        base_empathy: float = 0.85,
                        steps: int = 500) -> dict:
        """
        Sweep a parameter across values.
        
        Args:
            param: Parameter to sweep (empathy, beta, karma, channels)
            values: List of values to test
            base_empathy: Base empathy level
            steps: Steps per simulation
        
        Returns:
            Results for each value
        """
        results = []
        
        for value in values:
            if param == "empathy":
                result = self.run_simulation(empathy=value, steps=steps)
            elif param == "beta":
                result = self.run_simulation(empathy=base_empathy, steps=steps, beta=value)
            elif param == "karma":
                result = self.run_simulation(empathy=base_empathy, steps=steps, karma=value)
            elif param == "channels":
                result = self.run_simulation(empathy=base_empathy, steps=steps, channels=int(value))
            else:
                continue
            
            results.append({
                "value": value,
                "energy": result["total_energy"],
                "health": result["final_health"],
                "coherence": result["final_coherence"],
                "infinite": result["infinite_threshold_met"],
            })
        
        # Find optimal
        best = max(results, key=lambda x: x["energy"])
        
        return {
            "parameter": param,
            "results": results,
            "optimal_value": best["value"],
            "optimal_energy": best["energy"],
        }
    
    def launch_gui(self) -> dict:
        """Launch the GUI in a separate process."""
        try:
            # FIX 2026-03-08 Nous: PyQt6 SEGFAULTS on python3.14t (free-threaded).
            # Use regular "python" from PATH for Qt GUI subprocesses.
            import shutil
            python = shutil.which("python") or shutil.which("python3") or "python"
            if sys.platform == "win32":
                pythonw = python.replace("python.exe", "pythonw.exe")
                if Path(pythonw).exists():
                    python = pythonw
            
            proc = subprocess.Popen(
                [python, str(SIM_PATH)],
                cwd=str(PROJECT_ROOT),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            )
            
            return {
                "success": True,
                "pid": proc.pid,
                "message": "GUI launched in separate window",
            }
        except Exception as e:
            return {"error": str(e)}


# Global controller
_sim_controller = SimulatorController()


def register_simulator_tools(mcp):
    """Register simulator tools with MCP server."""
    
    @mcp.tool()
    def sim_run(empathy: float = 0.85, steps: int = 1000,
                beta: float = 0.8, karma: float = 0.6,
                channels: int = 3) -> str:
        """
        Run a consciousness dynamics simulation.
        
        Args:
            empathy: Empathy level 0-1 (higher = more cooperative)
            steps: Simulation steps (default 1000)
            beta: Cooperation coefficient (default 0.8)
            karma: Karma feedback strength (default 0.6)
            channels: Resonance channels (default 3, max 77)
        
        Returns:
            JSON with simulation results
        """
        result = _sim_controller.run_simulation(
            empathy=empathy, steps=steps, beta=beta, karma=karma, channels=channels
        )
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def sim_compare_personas(high_empathy: float = 0.95,
                             low_empathy: float = 0.75,
                             steps: int = 1000) -> str:
        """
        Compare high-empathy vs low-empathy personas.
        
        Args:
            high_empathy: Empathy for first persona
            low_empathy: Empathy for second persona
            steps: Simulation steps
        
        Returns:
            JSON comparison of both runs
        """
        result = _sim_controller.compare_personas(high_empathy, low_empathy, steps)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def sim_sweep_parameter(param: str, start: float, end: float, 
                            num_points: int = 10, steps: int = 500) -> str:
        """
        Sweep a parameter to find optimal value.
        
        Args:
            param: Parameter to sweep (empathy, beta, karma, channels)
            start: Starting value
            end: Ending value
            num_points: Number of test points
            steps: Steps per simulation
        
        Returns:
            JSON with sweep results and optimal value
        """
        import numpy as np
        values = list(np.linspace(start, end, num_points))
        result = _sim_controller.parameter_sweep(param, values, steps=steps)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def sim_launch_gui() -> str:
        """
        Launch the consciousness dynamics simulator GUI.
        Opens in a separate window.
        """
        result = _sim_controller.launch_gui()
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    # Test
    print("Running test simulation...")
    result = _sim_controller.run_simulation(empathy=0.85, steps=500)
    print(json.dumps(result, indent=2))
