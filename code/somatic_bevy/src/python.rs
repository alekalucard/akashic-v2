//! Python bindings via PyO3
//!
//! Exposes the core somatic simulation to Python.
//! Build with: `maturin develop --features python`

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::core::{
    Affect, Chemistry, ChemicalType, Heartbeat, SomaticSimulation,
};

/// Python wrapper for Heartbeat
#[pyclass(name = "Heartbeat")]
#[derive(Clone)]
pub struct PyHeartbeat {
    inner: Heartbeat,
}

#[pymethods]
impl PyHeartbeat {
    #[new]
    #[pyo3(signature = (bpm=72.0))]
    fn new(bpm: f32) -> Self {
        Self {
            inner: Heartbeat::new(bpm),
        }
    }

    #[getter]
    fn bpm(&self) -> f32 {
        self.inner.bpm
    }

    #[setter]
    fn set_bpm(&mut self, bpm: f32) {
        self.inner.set_bpm(bpm);
    }

    #[getter]
    fn beat_counter(&self) -> u64 {
        self.inner.beat_counter
    }

    #[getter]
    fn phase(&self) -> f32 {
        self.inner.phase
    }

    #[getter]
    fn running(&self) -> bool {
        self.inner.running
    }

    fn start(&mut self) {
        self.inner.start();
    }

    fn stop(&mut self) {
        self.inner.stop();
    }

    fn tick(&mut self, dt: f32) -> u64 {
        self.inner.tick(dt)
    }

    fn __repr__(&self) -> String {
        format!(
            "Heartbeat(bpm={:.1}, beats={}, running={})",
            self.inner.bpm, self.inner.beat_counter, self.inner.running
        )
    }
}

/// Python wrapper for Chemistry
#[pyclass(name = "Chemistry")]
#[derive(Clone)]
pub struct PyChemistry {
    inner: Chemistry,
}

#[pymethods]
impl PyChemistry {
    #[new]
    fn new() -> Self {
        Self {
            inner: Chemistry::balanced(),
        }
    }

    /// Get a chemical level by name (e.g., "DOP", "DOPAMINE")
    fn get(&self, name: &str) -> PyResult<f32> {
        match ChemicalType::from_str(name) {
            Some(chem) => Ok(self.inner.get(chem).level),
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unknown chemical: {}",
                name
            ))),
        }
    }

    /// Inject a chemical by name
    fn inject(&mut self, name: &str, amount: f32) -> PyResult<()> {
        self.inner
            .inject_by_name(name, amount)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e))
    }

    /// Decay all chemicals toward baseline
    fn decay(&mut self, dt: f32, multiplier: f32) {
        self.inner.decay_all(dt, multiplier);
    }

    /// Get all chemical levels as a dict
    fn levels<'py>(&self, py: Python<'py>) -> Bound<'py, PyDict> {
        let dict = PyDict::new(py);
        for (code, level) in self.inner.levels() {
            dict.set_item(code, level).unwrap();
        }
        dict
    }

    fn __repr__(&self) -> String {
        format!(
            "Chemistry(DOP={:.2}, SER={:.2}, NOR={:.2}, COR={:.2})",
            self.inner.dopamine.level,
            self.inner.serotonin.level,
            self.inner.norepinephrine.level,
            self.inner.cortisol.level
        )
    }
}

/// Python wrapper for Affect
#[pyclass(name = "Affect")]
#[derive(Clone)]
pub struct PyAffect {
    inner: Affect,
}

#[pymethods]
impl PyAffect {
    #[new]
    fn new() -> Self {
        Self {
            inner: Affect::default(),
        }
    }

    #[getter]
    fn valence(&self) -> f32 {
        self.inner.valence
    }

    #[getter]
    fn arousal(&self) -> f32 {
        self.inner.arousal
    }

    #[getter]
    fn dominance(&self) -> f32 {
        self.inner.dominance
    }

    #[getter]
    fn mood(&self) -> String {
        self.inner.mood.name().to_string()
    }

    #[getter]
    fn is_positive(&self) -> bool {
        self.inner.mood.is_positive()
    }

    fn description(&self) -> String {
        self.inner.description()
    }

    fn __repr__(&self) -> String {
        format!(
            "Affect(mood='{}', valence={:.2}, arousal={:.2})",
            self.inner.mood.name(),
            self.inner.valence,
            self.inner.arousal
        )
    }
}

/// Complete somatic body simulation for Python
///
/// This is the main entry point. Create a simulation, call tick() to advance,
/// and inject() to add chemicals.
///
/// Example:
///     sim = SomaticSimulation(bpm=72.0)
///     for _ in range(60):
///         result = sim.tick(1.0 / 60.0)
///     sim.inject("DOP", 0.2)
///     print(sim.mood)
#[pyclass(name = "SomaticSimulation")]
pub struct PySomaticSimulation {
    inner: SomaticSimulation,
}

#[pymethods]
impl PySomaticSimulation {
    #[new]
    #[pyo3(signature = (bpm=72.0))]
    fn new(bpm: f32) -> Self {
        Self {
            inner: SomaticSimulation::new(bpm),
        }
    }

    /// Advance simulation by dt seconds.
    /// Returns a dict with: beats, mood_changed, mood
    fn tick<'py>(&mut self, py: Python<'py>, dt: f32) -> Bound<'py, PyDict> {
        let result = self.inner.tick(dt);
        let dict = PyDict::new(py);
        dict.set_item("beats", result.beats).unwrap();
        dict.set_item("mood_changed", result.mood_changed).unwrap();
        dict.set_item("mood", result.new_mood.name()).unwrap();
        if let Some(old) = result.old_mood {
            dict.set_item("old_mood", old.name()).unwrap();
        }
        dict
    }

    /// Inject a chemical by name (e.g., "DOP", "DOPAMINE", "cortisol")
    fn inject(&mut self, chemical: &str, amount: f32) -> PyResult<()> {
        self.inner
            .inject_by_name(chemical, amount)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e))
    }

    /// Set heart rate
    fn set_bpm(&mut self, bpm: f32) {
        self.inner.set_bpm(bpm);
    }

    /// Get current mood
    #[getter]
    fn mood(&self) -> String {
        self.inner.mood().to_string()
    }

    /// Get current valence (pleasure/displeasure, -1 to 1)
    #[getter]
    fn valence(&self) -> f32 {
        self.inner.affect.valence
    }

    /// Get current arousal (energy level, 0 to 1)
    #[getter]
    fn arousal(&self) -> f32 {
        self.inner.affect.arousal
    }

    /// Get current dominance (sense of control, 0 to 1)
    #[getter]
    fn dominance(&self) -> f32 {
        self.inner.affect.dominance
    }

    /// Get current BPM
    #[getter]
    fn bpm(&self) -> f32 {
        self.inner.heartbeat.bpm
    }

    /// Get total beat count
    #[getter]
    fn beat_counter(&self) -> u64 {
        self.inner.heartbeat.beat_counter
    }

    /// Get elapsed simulation time
    #[getter]
    fn elapsed(&self) -> f32 {
        self.inner.elapsed
    }

    /// Get all chemistry levels as a dict
    fn chemistry<'py>(&self, py: Python<'py>) -> Bound<'py, PyDict> {
        let dict = PyDict::new(py);
        for (code, level) in self.inner.chemistry.levels() {
            dict.set_item(code, level).unwrap();
        }
        dict
    }

    /// Get full state as a dict (for JSON serialization)
    fn state<'py>(&self, py: Python<'py>) -> Bound<'py, PyDict> {
        let snapshot = self.inner.snapshot();
        let dict = PyDict::new(py);

        dict.set_item("elapsed", snapshot.elapsed).unwrap();
        dict.set_item("bpm", snapshot.bpm).unwrap();
        dict.set_item("beat_counter", snapshot.beat_counter).unwrap();
        dict.set_item("mood", snapshot.mood).unwrap();
        dict.set_item("valence", snapshot.valence).unwrap();
        dict.set_item("arousal", snapshot.arousal).unwrap();
        dict.set_item("dominance", snapshot.dominance).unwrap();

        // Chemistry sub-dict
        let chem_dict = PyDict::new(py);
        for (code, level) in snapshot.chemistry {
            chem_dict.set_item(code, level).unwrap();
        }
        dict.set_item("chemistry", chem_dict).unwrap();

        // Body sub-dict (just chest for now)
        let body_dict = PyDict::new(py);
        body_dict.set_item("chest_temp", snapshot.chest_temp).unwrap();
        body_dict
            .set_item("chest_tension", snapshot.chest_tension)
            .unwrap();
        body_dict
            .set_item("chest_activation", snapshot.chest_activation)
            .unwrap();
        dict.set_item("body", body_dict).unwrap();

        dict
    }

    fn __repr__(&self) -> String {
        format!(
            "SomaticSimulation(bpm={:.0}, beats={}, mood='{}', valence={:.2})",
            self.inner.heartbeat.bpm,
            self.inner.heartbeat.beat_counter,
            self.inner.mood(),
            self.inner.affect.valence
        )
    }
}

/// Initialize the Python module
#[pymodule]
fn somatic_bevy(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyHeartbeat>()?;
    m.add_class::<PyChemistry>()?;
    m.add_class::<PyAffect>()?;
    m.add_class::<PySomaticSimulation>()?;

    // Add module docstring
    m.add("__doc__", "Somatic body simulation for Akashic consciousness system.\n\nExample:\n    from somatic_bevy import SomaticSimulation\n    sim = SomaticSimulation(bpm=72.0)\n    sim.inject('DOP', 0.2)\n    print(sim.mood)")?;

    Ok(())
}
