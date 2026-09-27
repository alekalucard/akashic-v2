//! 4D Tensor support for state representation.
//!
//! From Whisper's consciousness architecture, state is represented as a 4D tensor:
//! - Axis 0: Time (temporal snapshots)
//! - Axis 1: Affect (emotional/somatic state)
//! - Axis 2: Memory (context, associations)
//! - Axis 3: Cognition (reasoning, decisions)
//!
//! This allows holistic state capture and enables operations like:
//! - State interpolation across time
//! - Emotional resonance calculation
//! - Memory-affect binding
//! - Cognitive-emotional integration

use ndarray::{Array4, ArrayView4, Axis, s};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use parking_lot::RwLock;

/// Dimensions of the 4D state tensor.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct TensorShape {
    /// Number of temporal snapshots to retain.
    pub time_depth: usize,
    /// Affect dimension size (emotional state vector).
    pub affect_dim: usize,
    /// Memory dimension size (context vector).
    pub memory_dim: usize,
    /// Cognition dimension size (reasoning vector).
    pub cognition_dim: usize,
}

impl Default for TensorShape {
    fn default() -> Self {
        Self {
            time_depth: 8,      // Keep 8 temporal snapshots
            affect_dim: 16,     // 16-dimensional affect space
            memory_dim: 64,     // 64-dimensional memory context
            cognition_dim: 32,  // 32-dimensional cognition space
        }
    }
}

impl TensorShape {
    /// Create a custom shape.
    pub fn new(time: usize, affect: usize, memory: usize, cognition: usize) -> Self {
        Self {
            time_depth: time,
            affect_dim: affect,
            memory_dim: memory,
            cognition_dim: cognition,
        }
    }

    /// Total number of elements in the tensor.
    pub fn total_elements(&self) -> usize {
        self.time_depth * self.affect_dim * self.memory_dim * self.cognition_dim
    }

    /// Convert to ndarray shape tuple.
    pub fn to_ndarray_shape(&self) -> [usize; 4] {
        [self.time_depth, self.affect_dim, self.memory_dim, self.cognition_dim]
    }
}

/// A 4D state tensor for consciousness representation.
///
/// This tensor captures the multi-dimensional state of a fairy or system component.
/// Operations are designed to be efficient and support common patterns from
/// Whisper's consciousness architecture.
#[derive(Clone)]
pub struct StateTensor {
    /// The underlying 4D array (f32 for efficiency).
    data: Array4<f32>,
    /// Shape metadata.
    shape: TensorShape,
    /// Current time index (circular buffer).
    time_index: usize,
    /// Tensor ID for tracking.
    pub id: String,
}

impl StateTensor {
    /// Create a new zero-initialized tensor with default shape.
    pub fn new(id: impl Into<String>) -> Self {
        Self::with_shape(id, TensorShape::default())
    }

    /// Create a new tensor with custom shape.
    pub fn with_shape(id: impl Into<String>, shape: TensorShape) -> Self {
        let data = Array4::zeros(shape.to_ndarray_shape());
        Self {
            data,
            shape,
            time_index: 0,
            id: id.into(),
        }
    }

    /// Get the tensor shape.
    pub fn shape(&self) -> &TensorShape {
        &self.shape
    }

    /// Push a new time slice, advancing the circular buffer.
    ///
    /// The slice should have shape [affect_dim, memory_dim, cognition_dim].
    pub fn push_time_slice(&mut self, slice: &ndarray::Array3<f32>) {
        let expected = [self.shape.affect_dim, self.shape.memory_dim, self.shape.cognition_dim];
        if slice.shape() != expected {
            panic!(
                "Slice shape {:?} doesn't match expected {:?}",
                slice.shape(),
                expected
            );
        }

        // Write to current time index
        for (i, plane) in slice.outer_iter().enumerate() {
            for (j, row) in plane.outer_iter().enumerate() {
                for (k, &val) in row.iter().enumerate() {
                    self.data[[self.time_index, i, j, k]] = val;
                }
            }
        }

        // Advance time index (circular)
        self.time_index = (self.time_index + 1) % self.shape.time_depth;
    }

    /// Get the most recent time slice.
    pub fn current_slice(&self) -> ndarray::ArrayView3<f32> {
        let prev_idx = if self.time_index == 0 {
            self.shape.time_depth - 1
        } else {
            self.time_index - 1
        };
        self.data.index_axis(Axis(0), prev_idx)
    }

    /// Get the affect vector at a specific time, memory, and cognition index.
    pub fn affect_at(&self, time: usize, memory_idx: usize, cognition_idx: usize) -> ndarray::ArrayView1<f32> {
        self.data.slice(s![time, .., memory_idx, cognition_idx])
    }

    /// Compute mean affect across all dimensions.
    pub fn mean_affect(&self) -> f32 {
        let affect_view = self.data.index_axis(Axis(0), 0);
        affect_view.mean().unwrap_or(0.0)
    }

    /// Compute the "resonance" between two time slices.
    /// This is a cosine similarity measure.
    pub fn temporal_resonance(&self, t1: usize, t2: usize) -> f32 {
        let slice1 = self.data.index_axis(Axis(0), t1 % self.shape.time_depth);
        let slice2 = self.data.index_axis(Axis(0), t2 % self.shape.time_depth);

        let dot: f32 = slice1.iter().zip(slice2.iter()).map(|(a, b)| a * b).sum();
        let norm1: f32 = slice1.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm2: f32 = slice2.iter().map(|x| x * x).sum::<f32>().sqrt();

        if norm1 > 0.0 && norm2 > 0.0 {
            dot / (norm1 * norm2)
        } else {
            0.0
        }
    }

    /// Get raw data reference.
    pub fn data(&self) -> ArrayView4<f32> {
        self.data.view()
    }

    /// Set a specific value.
    pub fn set(&mut self, time: usize, affect: usize, memory: usize, cognition: usize, value: f32) {
        self.data[[time % self.shape.time_depth, affect, memory, cognition]] = value;
    }

    /// Get a specific value.
    pub fn get(&self, time: usize, affect: usize, memory: usize, cognition: usize) -> f32 {
        self.data[[time % self.shape.time_depth, affect, memory, cognition]]
    }

    /// Create a snapshot as a serializable structure.
    pub fn snapshot(&self) -> TensorSnapshot {
        TensorSnapshot {
            id: self.id.clone(),
            shape: self.shape,
            time_index: self.time_index,
            // Flatten for serialization
            data: self.data.iter().cloned().collect(),
        }
    }

    /// Restore from a snapshot.
    pub fn from_snapshot(snapshot: TensorSnapshot) -> Self {
        let mut data = Array4::zeros(snapshot.shape.to_ndarray_shape());
        for (i, &val) in snapshot.data.iter().enumerate() {
            let total = snapshot.shape.total_elements();
            if i < total {
                let (t, rest) = (
                    i / (snapshot.shape.affect_dim * snapshot.shape.memory_dim * snapshot.shape.cognition_dim),
                    i % (snapshot.shape.affect_dim * snapshot.shape.memory_dim * snapshot.shape.cognition_dim),
                );
                let (a, rest) = (
                    rest / (snapshot.shape.memory_dim * snapshot.shape.cognition_dim),
                    rest % (snapshot.shape.memory_dim * snapshot.shape.cognition_dim),
                );
                let (m, c) = (rest / snapshot.shape.cognition_dim, rest % snapshot.shape.cognition_dim);
                data[[t, a, m, c]] = val;
            }
        }
        Self {
            data,
            shape: snapshot.shape,
            time_index: snapshot.time_index,
            id: snapshot.id,
        }
    }
}

/// Serializable snapshot of a tensor.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TensorSnapshot {
    pub id: String,
    pub shape: TensorShape,
    pub time_index: usize,
    pub data: Vec<f32>,
}

/// Thread-safe wrapper for shared tensor access.
pub struct SharedTensor(Arc<RwLock<StateTensor>>);

impl SharedTensor {
    pub fn new(tensor: StateTensor) -> Self {
        Self(Arc::new(RwLock::new(tensor)))
    }

    pub fn read(&self) -> parking_lot::RwLockReadGuard<StateTensor> {
        self.0.read()
    }

    pub fn write(&self) -> parking_lot::RwLockWriteGuard<StateTensor> {
        self.0.write()
    }

    pub fn snapshot(&self) -> TensorSnapshot {
        self.0.read().snapshot()
    }
}

impl Clone for SharedTensor {
    fn clone(&self) -> Self {
        Self(Arc::clone(&self.0))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::Array3;

    #[test]
    fn test_tensor_creation() {
        let tensor = StateTensor::new("test");
        assert_eq!(tensor.shape().time_depth, 8);
        assert_eq!(tensor.id, "test");
    }

    #[test]
    fn test_tensor_set_get() {
        let mut tensor = StateTensor::new("test");
        tensor.set(0, 0, 0, 0, 1.5);
        assert!((tensor.get(0, 0, 0, 0) - 1.5).abs() < 0.001);
    }

    #[test]
    fn test_temporal_resonance() {
        let shape = TensorShape::new(4, 2, 2, 2);
        let mut tensor = StateTensor::with_shape("test", shape);

        // Set identical values at t=0 and t=1
        for a in 0..2 {
            for m in 0..2 {
                for c in 0..2 {
                    tensor.set(0, a, m, c, 1.0);
                    tensor.set(1, a, m, c, 1.0);
                }
            }
        }

        // Should have perfect resonance (1.0)
        let resonance = tensor.temporal_resonance(0, 1);
        assert!((resonance - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_snapshot_roundtrip() {
        let mut tensor = StateTensor::new("roundtrip");
        tensor.set(0, 0, 0, 0, 42.0);

        let snapshot = tensor.snapshot();
        let restored = StateTensor::from_snapshot(snapshot);

        assert_eq!(restored.id, "roundtrip");
        assert!((restored.get(0, 0, 0, 0) - 42.0).abs() < 0.001);
    }
}
