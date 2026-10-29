//! Postal Core - Lock-free messaging infrastructure for Akashic consciousness.
//!
//! A Rust-native implementation of the postal/pub-sub system with:
//! - Lock-free channels (crossbeam) instead of Python's queue.Queue
//! - Per-topic worker pools with autoscaling
//! - Three priority lanes (HIGH, NORMAL, LOW)
//! - Backpressure policies for graceful degradation
//! - P95 latency tracking with HDR histograms
//!
//! Updated 2026-03-26 (Nous) for PyO3 0.28 + Python 3.14 free-threaded.

pub mod backpressure;
pub mod envelope;
pub mod metrics;
pub mod priority;
pub mod return_office;
pub mod tensor;
pub mod topic_bus;
pub mod worker;

// Re-exports for convenience
pub use backpressure::{BackpressurePolicy, EnqueueResult};
pub use envelope::{now_ms, Envelope};
pub use metrics::{MetricsSnapshot, PostalMetrics};
pub use priority::Priority;
pub use tensor::{SharedTensor, StateTensor, TensorShape, TensorSnapshot};
pub use topic_bus::{TopicBus, TopicBusConfig, TopicConfig, TopicStats};
pub use worker::{WorkerPool, WorkerPoolConfig};

// ============================================================================
// Python Bindings (PyO3 0.28 — Python 3.14 free-threaded support)
// ============================================================================

use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::sync::Arc;

/// Python-friendly envelope wrapper.
#[pyclass(name = "Envelope")]
#[derive(Clone)]
pub struct PyEnvelope {
    inner: Envelope,
}

#[pymethods]
impl PyEnvelope {
    #[new]
    #[pyo3(signature = (intent, payload=None))]
    fn new(py: Python<'_>, intent: String, payload: Option<Bound<'_, PyDict>>) -> PyResult<Self> {
        let payload_json = if let Some(dict) = payload {
            let json = py.import("json")?;
            let dumps = json.getattr("dumps")?;
            let json_str: String = dumps.call1((&dict,))?.extract()?;
            serde_json::from_str(&json_str).unwrap_or(serde_json::Value::Null)
        } else {
            serde_json::Value::Null
        };

        Ok(Self {
            inner: Envelope::new(intent, payload_json),
        })
    }

    #[getter]
    fn intent(&self) -> &str {
        &self.inner.intent
    }

    #[getter]
    fn t(&self) -> u64 {
        self.inner.t
    }

    #[getter]
    fn trace_id(&self) -> &str {
        &self.inner.trace_id
    }

    #[getter]
    fn source(&self) -> &str {
        &self.inner.source
    }

    #[getter]
    fn payload<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, pyo3::types::PyAny>> {
        let json = py.import("json")?;
        let loads = json.getattr("loads")?;
        let json_str = serde_json::to_string(&self.inner.payload)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        loads.call1((json_str,))
    }

    fn with_source(&self, source: String) -> Self {
        Self {
            inner: self.inner.clone().with_source(source),
        }
    }

    fn with_priority(&self, priority: u8) -> Self {
        Self {
            inner: self.inner.clone().with_priority(Priority::from_u8(priority)),
        }
    }
}

/// Python-friendly TopicBus wrapper.
#[pyclass(name = "PostalCore")]
pub struct PyPostalCore {
    bus: Arc<TopicBus>,
}

#[pymethods]
impl PyPostalCore {
    #[new]
    fn new() -> Self {
        Self {
            bus: Arc::new(TopicBus::new()),
        }
    }

    /// Subscribe to a topic with a Python callback.
    #[pyo3(signature = (topic, callback, name=None, intent=None))]
    fn subscribe(&self, _py: Python<'_>, topic: String, callback: Py<pyo3::types::PyAny>, name: Option<String>, intent: Option<String>) -> PyResult<usize> {
        // `topic` is the POOL (base topic). `intent` is what this subscriber actually
        // wants; None keeps the old wildcard behaviour so existing callers are unaffected.
        let name = name.unwrap_or_else(|| "python-handler".to_string());

        let callback = Arc::new(callback);

        let handler_id = self.bus.subscribe_filtered(
            topic,
            move |envelope| {
                let cb: Arc<Py<pyo3::types::PyAny>> = Arc::clone(&callback);
                // PyO3 0.28: Use try_attach instead of with_gil
                if let Some(()) = Python::try_attach(|py| {
                    let py_env = PyEnvelope { inner: envelope };
                    if let Err(e) = cb.call1(py, (py_env,)) {
                        eprintln!("Python handler error: {:?}", e);
                    }
                }) {
                    // Handler ran successfully
                }
            },
            name,
            0,
            1,
            intent,
        );

        Ok(handler_id)
    }

    /// Publish a message.
    #[pyo3(signature = (intent, payload=None, priority=1, pool=None))]
    fn publish(&self, py: Python<'_>, intent: String, payload: Option<Bound<'_, PyDict>>, priority: u8, pool: Option<String>) -> PyResult<()> {
        // `pool` routes into the base-topic pool while `intent` stays the REAL intent, so
        // subscribers can be matched. Omitted => pool derived from intent (old behaviour).
        let payload_json = if let Some(dict) = payload {
            let json = py.import("json")?;
            let dumps = json.getattr("dumps")?;
            let json_str: String = dumps.call1((&dict,))?.extract()?;
            serde_json::from_str(&json_str).unwrap_or(serde_json::Value::Null)
        } else {
            serde_json::Value::Null
        };

        let envelope = Envelope::new(intent, payload_json)
            .with_priority(Priority::from_u8(priority));

        // Route into the POOL named by `pool` (the base topic) while the envelope keeps its
        // REAL intent for subscriber matching. Without this, Envelope::topic() -- which just
        // returns &self.intent -- would create one pool PER INTENT (hundreds of pools, each
        // an autoscaling 16-worker pool). Omitting `pool` preserves the old behaviour.
        match pool {
            Some(p) => self.bus.publish_routed(&p, envelope),
            None => self.bus.publish(envelope),
        }
        Ok(())
    }

    /// Get metrics snapshot.
    fn metrics<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, pyo3::types::PyAny>> {
        let snapshot = self.bus.metrics();
        let json = py.import("json")?;
        let loads = json.getattr("loads")?;
        let json_str = serde_json::to_string(&snapshot)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        loads.call1((json_str,))
    }

    /// W2: return-to-sender counters and the last N returns ({"enabled": false} when off).
    fn returns<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, pyo3::types::PyAny>> {
        let snap = self.bus.returns_snapshot();
        let json = py.import("json")?;
        let loads = json.getattr("loads")?;
        let json_str = serde_json::to_string(&snap)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        loads.call1((json_str,))
    }

    /// Get per-topic stats.
    fn topic_stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, pyo3::types::PyAny>> {
        let stats = self.bus.topic_stats();
        let json = py.import("json")?;
        let loads = json.getattr("loads")?;
        let json_str = serde_json::to_string(&stats)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        loads.call1((json_str,))
    }

    /// Shutdown the postal system.
    fn shutdown(&self) {
        self.bus.shutdown();
    }
}

/// Python module definition.
#[pymodule]
fn postal_core(m: &Bound<'_, pyo3::types::PyModule>) -> PyResult<()> {
    m.add_class::<PyEnvelope>()?;
    m.add_class::<PyPostalCore>()?;
    Ok(())
}

// ============================================================================
// Global convenience (like Whisper's GLOBAL_BUS)
// ============================================================================

use once_cell::sync::Lazy;
use parking_lot::RwLock;

static GLOBAL_BUS: Lazy<RwLock<Option<Arc<TopicBus>>>> = Lazy::new(|| RwLock::new(None));

/// Initialize the global postal bus.
pub fn init_global() -> Arc<TopicBus> {
    let mut guard = GLOBAL_BUS.write();
    if guard.is_none() {
        *guard = Some(Arc::new(TopicBus::new()));
    }
    Arc::clone(guard.as_ref().unwrap())
}

/// Get the global postal bus, initializing if necessary.
pub fn global_bus() -> Arc<TopicBus> {
    let guard = GLOBAL_BUS.read();
    if let Some(bus) = guard.as_ref() {
        return Arc::clone(bus);
    }
    drop(guard);
    init_global()
}

/// Publish to the global bus.
pub fn publish(envelope: Envelope) {
    global_bus().publish(envelope);
}

/// Subscribe to the global bus.
pub fn subscribe<F>(topic: impl Into<String>, handler: F, name: impl Into<String>) -> usize
where
    F: Fn(Envelope) + Send + Sync + 'static,
{
    global_bus().subscribe(topic, handler, name, 0, 1)
}

/// Shutdown the global bus.
pub fn shutdown_global() {
    if let Some(bus) = GLOBAL_BUS.write().take() {
        bus.shutdown();
    }
}
