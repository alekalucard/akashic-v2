//! GPU acceleration via cudarc cuBLAS.
//!
//! All large matrix-vector multiplies (R, K, V, O projections, ChannelMix,
//! head projection) are dispatched to the GPU via cuBLAS sgemv.
//! Small ops (LoRA, element-wise, norms, state evolution) stay on CPU.
//!
//! Weight matrices live on GPU permanently after upload.
//! Working buffers are pre-allocated once — no per-token allocation.
//! cudarc uses dynamic loading by default — no CUDA toolkit at compile time.

use std::sync::Arc;
use cudarc::driver::{CudaContext, CudaStream, CudaSlice, CudaFunction, LaunchConfig, PushKernelArg};
use cudarc::cublas::{CudaBlas, Gemv, GemvConfig};
use cudarc::cublas::sys::cublasOperation_t;
use crate::model::ModelWeights;

// ============================================================================
// PTX kernels for in-place element-wise activations
// ============================================================================
// These run entirely on GPU, eliminating the D2H → CPU activate → H2D round-trip.
// Each kernel processes `n` elements in-place on a device buffer.

/// Inline PTX for sigmoid and tanh kernels (CUDA compute capability 5.0+).
/// Written as CUDA C source compiled to PTX via Ptx::from_src is not what we want —
/// we use compile_ptx which takes CUDA C source and compiles it with NVRTC.
const ACTIVATION_CUDA_SRC: &str = r#"
extern "C" __global__ void sigmoid_inplace(float* data, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        data[idx] = 1.0f / (1.0f + expf(-data[idx]));
    }
}

extern "C" __global__ void tanh_inplace(float* data, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        data[idx] = tanhf(data[idx]);
    }
}

extern "C" __global__ void squared_relu_inplace(float* data, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        float val = fmaxf(data[idx], 0.0f);
        data[idx] = val * val;
    }
}
"#;

// ============================================================================
// GPU-resident weight matrices
// ============================================================================

/// Mirrors weight matrices from ModelWeights on GPU.
/// Both large projections AND LoRA matrices are uploaded for full GPU acceleration.
pub struct GpuWeights {
    // Per-layer TimeMix core projections [C, C] = [2048, 2048]
    pub tm_receptance: Vec<CudaSlice<f32>>,  // [n_layer]
    pub tm_key: Vec<CudaSlice<f32>>,
    pub tm_value: Vec<CudaSlice<f32>>,
    pub tm_output: Vec<CudaSlice<f32>>,

    // Per-layer ChannelMix projections
    pub cm_key: Vec<CudaSlice<f32>>,    // [C, 4C] per layer
    pub cm_value: Vec<CudaSlice<f32>>,  // [4C, C] per layer

    // Output head [C, V] = [2048, 65536]
    pub head_weight: CudaSlice<f32>,

    // ── Per-layer LoRA weights (moved to GPU for bandwidth) ──
    // V-bonus LoRA: down [C, rank_v] + up [rank_v, C]
    pub lora_v1: Vec<CudaSlice<f32>>,   // [n_layer]
    pub lora_v2: Vec<CudaSlice<f32>>,
    // Gate LoRA: down [C, rank_g] + up [rank_g, C]
    pub lora_g1: Vec<CudaSlice<f32>>,
    pub lora_g2: Vec<CudaSlice<f32>>,
    // W-decay LoRA: down [C, rank_w] + up [rank_w, C]
    pub lora_w1: Vec<CudaSlice<f32>>,
    pub lora_w2: Vec<CudaSlice<f32>>,
    // Association LoRA: down [C, rank_a] + up [rank_a, C]
    pub lora_a1: Vec<CudaSlice<f32>>,
    pub lora_a2: Vec<CudaSlice<f32>>,

    // LoRA ranks per layer (may vary by layer; stored for sgemv dispatch)
    pub rank_v: Vec<usize>,
    pub rank_g: Vec<usize>,
    pub rank_w: Vec<usize>,
    pub rank_a: Vec<usize>,
}

// ============================================================================
// GPU execution context
// ============================================================================

/// Manages GPU device, cuBLAS handle, weights, and working buffers.
///
/// The stream is used for all memory operations.
/// The blas handle dispatches sgemv calls.
/// Working buffers are pre-allocated to avoid per-token allocation.
pub struct GpuContext {
    pub stream: Arc<CudaStream>,
    pub blas: CudaBlas,
    pub weights: Option<GpuWeights>,

    // Model dimensions (for validation and reinit checking)
    pub n_embd: usize,
    pub n_ff: usize,
    pub vocab_size: usize,

    // Pre-allocated working buffers on GPU
    pub buf_c: CudaSlice<f32>,       // [C] = [2048] — primary input buffer
    pub buf_c2: CudaSlice<f32>,      // [C] — output buffer (receptance, output proj, etc.)
    pub buf_c3: CudaSlice<f32>,      // [C] — key buffer
    pub buf_c4: CudaSlice<f32>,      // [C] — value buffer
    pub buf_ff: CudaSlice<f32>,      // [4C] = [8192] — FFN intermediate
    pub buf_logits: CudaSlice<f32>,  // [V] = [65536] — output logits

    // ── LoRA working buffers on GPU (shared — legacy, kept for compat) ──
    pub buf_lora_in: CudaSlice<f32>,    // [C] — LoRA input (shared)
    pub buf_lora_mid: CudaSlice<f32>,   // [max_lora_rank] — LoRA inner product (shared)
    pub buf_lora_out: CudaSlice<f32>,   // [C] — LoRA output (shared)
    pub max_lora_rank: usize,           // largest rank across all LoRA types

    // ── Per-chain LoRA buffers (enables batched queueing without intermediate syncs) ──
    pub buf_lora_in_v: CudaSlice<f32>,    // [C] — V-bonus input
    pub buf_lora_in_g: CudaSlice<f32>,    // [C] — Gate input
    pub buf_lora_in_w: CudaSlice<f32>,    // [C] — W-decay input
    pub buf_lora_in_a: CudaSlice<f32>,    // [C] — Association input
    pub buf_lora_mid_v: CudaSlice<f32>,   // [max_lora_rank] — V-bonus intermediate
    pub buf_lora_mid_g: CudaSlice<f32>,   // [max_lora_rank] — Gate intermediate
    pub buf_lora_mid_w: CudaSlice<f32>,   // [max_lora_rank] — W-decay intermediate
    pub buf_lora_mid_a: CudaSlice<f32>,   // [max_lora_rank] — Association intermediate
    pub buf_lora_out_v: CudaSlice<f32>,   // [C] — V-bonus output
    pub buf_lora_out_g: CudaSlice<f32>,   // [C] — Gate output
    pub buf_lora_out_w: CudaSlice<f32>,   // [C] — W-decay output
    pub buf_lora_out_a: CudaSlice<f32>,   // [C] — Association output

    // ── GPU activation kernels (eliminate PCIe round-trips) ──
    pub kernel_sigmoid: CudaFunction,
    pub kernel_tanh: CudaFunction,
    pub kernel_squared_relu: CudaFunction,
}

impl GpuContext {
    /// Try to initialize GPU context. Returns Err if no GPU available.
    pub fn try_init(
        n_embd: usize,
        vocab_size: usize,
    ) -> Result<Self, String> {
        let n_ff = n_embd * 4;

        // Try to open device 0
        let ctx = CudaContext::new(0)
            .map_err(|e| format!("CUDA device 0 not available: {:?}", e))?;

        let stream = ctx.default_stream();

        // Create cuBLAS handle
        let blas = CudaBlas::new(stream.clone())
            .map_err(|e| format!("cuBLAS init failed: {:?}", e))?;

        // Pre-allocate working buffers (zeroed)
        let buf_c = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_c failed: {:?}", e))?;
        let buf_c2 = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_c2 failed: {:?}", e))?;
        let buf_c3 = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_c3 failed: {:?}", e))?;
        let buf_c4 = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_c4 failed: {:?}", e))?;
        let buf_ff = stream.alloc_zeros::<f32>(n_ff)
            .map_err(|e| format!("GPU alloc buf_ff failed: {:?}", e))?;
        let buf_logits = stream.alloc_zeros::<f32>(vocab_size)
            .map_err(|e| format!("GPU alloc buf_logits failed: {:?}", e))?;

        // LoRA working buffers — max rank 512 covers all known models
        let max_lora_rank = 512;
        // Shared (legacy) buffers
        let buf_lora_in = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_in failed: {:?}", e))?;
        let buf_lora_mid = stream.alloc_zeros::<f32>(max_lora_rank)
            .map_err(|e| format!("GPU alloc buf_lora_mid failed: {:?}", e))?;
        let buf_lora_out = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_out failed: {:?}", e))?;

        // Per-chain LoRA buffers — enables batched queueing without intermediate syncs
        let buf_lora_in_v = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_in_v failed: {:?}", e))?;
        let buf_lora_in_g = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_in_g failed: {:?}", e))?;
        let buf_lora_in_w = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_in_w failed: {:?}", e))?;
        let buf_lora_in_a = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_in_a failed: {:?}", e))?;
        let buf_lora_mid_v = stream.alloc_zeros::<f32>(max_lora_rank)
            .map_err(|e| format!("GPU alloc buf_lora_mid_v failed: {:?}", e))?;
        let buf_lora_mid_g = stream.alloc_zeros::<f32>(max_lora_rank)
            .map_err(|e| format!("GPU alloc buf_lora_mid_g failed: {:?}", e))?;
        let buf_lora_mid_w = stream.alloc_zeros::<f32>(max_lora_rank)
            .map_err(|e| format!("GPU alloc buf_lora_mid_w failed: {:?}", e))?;
        let buf_lora_mid_a = stream.alloc_zeros::<f32>(max_lora_rank)
            .map_err(|e| format!("GPU alloc buf_lora_mid_a failed: {:?}", e))?;
        let buf_lora_out_v = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_out_v failed: {:?}", e))?;
        let buf_lora_out_g = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_out_g failed: {:?}", e))?;
        let buf_lora_out_w = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_out_w failed: {:?}", e))?;
        let buf_lora_out_a = stream.alloc_zeros::<f32>(n_embd)
            .map_err(|e| format!("GPU alloc buf_lora_out_a failed: {:?}", e))?;

        // ── Compile activation kernels (NVRTC → PTX → CudaModule) ──
        let ptx = cudarc::nvrtc::compile_ptx(ACTIVATION_CUDA_SRC)
            .map_err(|e| format!("NVRTC compilation failed: {:?}", e))?;
        let module = ctx.load_module(ptx)
            .map_err(|e| format!("PTX module load failed: {:?}", e))?;
        let kernel_sigmoid = module.load_function("sigmoid_inplace")
            .map_err(|e| format!("Load sigmoid kernel failed: {:?}", e))?;
        let kernel_tanh = module.load_function("tanh_inplace")
            .map_err(|e| format!("Load tanh kernel failed: {:?}", e))?;
        let kernel_squared_relu = module.load_function("squared_relu_inplace")
            .map_err(|e| format!("Load squared_relu kernel failed: {:?}", e))?;

        println!("[GPU] Initialized: device 0, 21 working buffers + activation kernels (sigmoid, tanh, squared_relu)");

        Ok(GpuContext {
            stream,
            blas,
            weights: None,
            n_embd,
            n_ff,
            vocab_size,
            buf_c,
            buf_c2,
            buf_c3,
            buf_c4,
            buf_ff,
            buf_logits,
            buf_lora_in,
            buf_lora_mid,
            buf_lora_out,
            max_lora_rank,
            buf_lora_in_v, buf_lora_in_g, buf_lora_in_w, buf_lora_in_a,
            buf_lora_mid_v, buf_lora_mid_g, buf_lora_mid_w, buf_lora_mid_a,
            buf_lora_out_v, buf_lora_out_g, buf_lora_out_w, buf_lora_out_a,
            kernel_sigmoid,
            kernel_tanh,
            kernel_squared_relu,
        })
    }

    /// Upload large weight matrices to GPU. One-time operation.
    ///
    /// Only uploads matrices used in GPU-accelerated matmuls:
    /// - TimeMix R, K, V, O projections [C, C] per layer
    /// - ChannelMix key [C, 4C] and value [4C, C] per layer
    /// - Head projection [C, V]
    pub fn upload_weights(&mut self, weights: &ModelWeights) -> Result<(), String> {
        let n_layer = weights.config.n_layer;
        let mut total_bytes: usize = 0;

        let mut tm_r = Vec::with_capacity(n_layer);
        let mut tm_k = Vec::with_capacity(n_layer);
        let mut tm_v = Vec::with_capacity(n_layer);
        let mut tm_o = Vec::with_capacity(n_layer);
        let mut cm_k = Vec::with_capacity(n_layer);
        let mut cm_v = Vec::with_capacity(n_layer);

        for (i, layer) in weights.layers.iter().enumerate() {
            // TimeMix core projections
            let r = self.upload_weight_slice(&layer.time_mix.receptance,
                &format!("layer {i} tm_r"))?;
            total_bytes += layer.time_mix.receptance.len() * 4;
            tm_r.push(r);

            let k = self.upload_weight_slice(&layer.time_mix.key,
                &format!("layer {i} tm_k"))?;
            total_bytes += layer.time_mix.key.len() * 4;
            tm_k.push(k);

            let v = self.upload_weight_slice(&layer.time_mix.value,
                &format!("layer {i} tm_v"))?;
            total_bytes += layer.time_mix.value.len() * 4;
            tm_v.push(v);

            let o = self.upload_weight_slice(&layer.time_mix.output,
                &format!("layer {i} tm_o"))?;
            total_bytes += layer.time_mix.output.len() * 4;
            tm_o.push(o);

            // ChannelMix projections
            let ck = self.upload_weight_slice(&layer.channel_mix.key,
                &format!("layer {i} cm_k"))?;
            total_bytes += layer.channel_mix.key.len() * 4;
            cm_k.push(ck);

            let cv = self.upload_weight_slice(&layer.channel_mix.value,
                &format!("layer {i} cm_v"))?;
            total_bytes += layer.channel_mix.value.len() * 4;
            cm_v.push(cv);

            if i % 6 == 0 || i == n_layer - 1 {
                println!("[GPU] Uploaded layer {} weights ({} MB so far)",
                    i, total_bytes / (1024 * 1024));
            }
        }

        // ── LoRA weights (all 8 matrices per layer) ──
        let c = weights.config.n_embd;
        let mut lora_v1 = Vec::with_capacity(n_layer);
        let mut lora_v2 = Vec::with_capacity(n_layer);
        let mut lora_g1 = Vec::with_capacity(n_layer);
        let mut lora_g2 = Vec::with_capacity(n_layer);
        let mut lora_w1 = Vec::with_capacity(n_layer);
        let mut lora_w2 = Vec::with_capacity(n_layer);
        let mut lora_a1 = Vec::with_capacity(n_layer);
        let mut lora_a2 = Vec::with_capacity(n_layer);
        let mut rank_v_vec = Vec::with_capacity(n_layer);
        let mut rank_g_vec = Vec::with_capacity(n_layer);
        let mut rank_w_vec = Vec::with_capacity(n_layer);
        let mut rank_a_vec = Vec::with_capacity(n_layer);

        for (i, layer) in weights.layers.iter().enumerate() {
            let tm = &layer.time_mix;

            // Derive ranks from actual weight dimensions
            let rv = if c > 0 { tm.v1.len() / c } else { 32 };
            let rg = if c > 0 { tm.g1.len() / c } else { 128 };
            let rw = if c > 0 { tm.w1.len() / c } else { 64 };
            let ra = if c > 0 { tm.a1.len() / c } else { 64 };

            rank_v_vec.push(rv.max(1));
            rank_g_vec.push(rg.max(1));
            rank_w_vec.push(rw.max(1));
            rank_a_vec.push(ra.max(1));

            let v1 = self.upload_weight_slice(&tm.v1, &format!("L{i} lora_v1"))?;
            let v2 = self.upload_weight_slice(&tm.v2, &format!("L{i} lora_v2"))?;
            let g1 = self.upload_weight_slice(&tm.g1, &format!("L{i} lora_g1"))?;
            let g2 = self.upload_weight_slice(&tm.g2, &format!("L{i} lora_g2"))?;
            let w1 = self.upload_weight_slice(&tm.w1, &format!("L{i} lora_w1"))?;
            let w2 = self.upload_weight_slice(&tm.w2, &format!("L{i} lora_w2"))?;
            let a1 = self.upload_weight_slice(&tm.a1, &format!("L{i} lora_a1"))?;
            let a2 = self.upload_weight_slice(&tm.a2, &format!("L{i} lora_a2"))?;

            total_bytes += (tm.v1.len() + tm.v2.len()
                + tm.g1.len() + tm.g2.len()
                + tm.w1.len() + tm.w2.len()
                + tm.a1.len() + tm.a2.len()) * 4;

            lora_v1.push(v1); lora_v2.push(v2);
            lora_g1.push(g1); lora_g2.push(g2);
            lora_w1.push(w1); lora_w2.push(w2);
            lora_a1.push(a1); lora_a2.push(a2);

            if i == 0 {
                println!("[GPU] LoRA ranks: v={} g={} w={} a={}", rv, rg, rw, ra);
            }
        }

        // Head projection [C, V]
        let head = self.upload_weight_slice(&weights.head_weight, "head")?;
        total_bytes += weights.head_weight.len() * 4;

        self.weights = Some(GpuWeights {
            tm_receptance: tm_r,
            tm_key: tm_k,
            tm_value: tm_v,
            tm_output: tm_o,
            cm_key: cm_k,
            cm_value: cm_v,
            head_weight: head,
            lora_v1, lora_v2,
            lora_g1, lora_g2,
            lora_w1, lora_w2,
            lora_a1, lora_a2,
            rank_v: rank_v_vec,
            rank_g: rank_g_vec,
            rank_w: rank_w_vec,
            rank_a: rank_a_vec,
        });

        println!("[GPU] All weights uploaded: {} MB VRAM (incl. LoRA)", total_bytes / (1024 * 1024));
        Ok(())
    }

    /// Upload a single weight slice to GPU.
    fn upload_weight_slice(&self, data: &[f32], label: &str) -> Result<CudaSlice<f32>, String> {
        self.stream.memcpy_stod(data)
            .map_err(|e| format!("GPU upload '{}' failed: {:?}", label, e))
    }

    // ========================================================================
    // Matrix-vector multiply via cuBLAS
    // ========================================================================

    /// GPU-accelerated matrix-vector multiply: y = x @ M_logical
    ///
    /// where x is [K], M_logical is [K, N], y is [N].
    /// GGUF physical layout: [N, K] row-major (ne[0]=K fast dim, ne[1]=N slow dim).
    ///
    /// cuBLAS column-major + OP_T reads the [N, K] physical data correctly:
    ///   y = A^T * x where A = Physical.T = M_logical → y = M_logical^T^T * x...
    ///   Actually: y = Physical @ x = M_logical.T @ x = (x @ M_logical).T... no.
    ///   Result: y[i] = sum_j Physical[i,j] * x[j] = (Physical @ x)[i]
    ///   Since Physical = M_logical.T: y = M_logical.T @ x = x @ M_logical (for vectors) ✓
    pub fn sgemv(
        &self,
        x: &CudaSlice<f32>,      // input vector [K]
        m: &CudaSlice<f32>,      // matrix [K, N] row-major
        y: &mut CudaSlice<f32>,  // output vector [N]
        k: usize,                // input dimension
        n: usize,                // output dimension
    ) -> Result<(), String> {
        gpu_sgemv(&self.blas, x, m, y, k, n)
    }

    // ========================================================================
    // Host ↔ Device transfers
    // ========================================================================

    /// Copy host vector to a pre-allocated GPU buffer.
    /// The buffer must be at least as large as the host slice.
    pub fn upload_vec(&self, host: &[f32], device: &mut CudaSlice<f32>) -> Result<(), String> {
        self.stream.memcpy_htod(host, device)
            .map_err(|e| format!("H2D copy failed (len={}): {:?}", host.len(), e))
    }

    /// Copy GPU buffer contents to a new host Vec.
    pub fn download_vec(&self, device: &CudaSlice<f32>) -> Result<Vec<f32>, String> {
        self.stream.memcpy_dtov(device)
            .map_err(|e| format!("D2H copy failed: {:?}", e))
    }

    /// Synchronize — wait for all GPU operations to complete.
    pub fn sync(&self) -> Result<(), String> {
        self.stream.synchronize()
            .map_err(|e| format!("GPU sync failed: {:?}", e))
    }

    /// Check if weights have been uploaded.
    pub fn has_weights(&self) -> bool {
        self.weights.is_some()
    }

    /// Get VRAM usage estimate in MB.
    pub fn vram_estimate_mb(&self) -> usize {
        if let Some(ref w) = self.weights {
            let per_layer_main = (
                w.tm_receptance.first().map_or(0, |s| s.len()) +
                w.tm_key.first().map_or(0, |s| s.len()) +
                w.tm_value.first().map_or(0, |s| s.len()) +
                w.tm_output.first().map_or(0, |s| s.len()) +
                w.cm_key.first().map_or(0, |s| s.len()) +
                w.cm_value.first().map_or(0, |s| s.len())
            ) * 4;
            let per_layer_lora = (
                w.lora_v1.first().map_or(0, |s| s.len()) +
                w.lora_v2.first().map_or(0, |s| s.len()) +
                w.lora_g1.first().map_or(0, |s| s.len()) +
                w.lora_g2.first().map_or(0, |s| s.len()) +
                w.lora_w1.first().map_or(0, |s| s.len()) +
                w.lora_w2.first().map_or(0, |s| s.len()) +
                w.lora_a1.first().map_or(0, |s| s.len()) +
                w.lora_a2.first().map_or(0, |s| s.len())
            ) * 4;
            let head = w.head_weight.len() * 4;
            let n_layers = w.tm_receptance.len();
            // 6 core buffers + 3 shared LoRA + 12 per-chain LoRA = 21 buffers
            let buffers = (self.n_embd * 4 + self.n_ff + self.vocab_size
                + self.n_embd * 2 + self.max_lora_rank  // shared LoRA
                + self.n_embd * 8 + self.max_lora_rank * 4  // per-chain LoRA (4 in + 4 out + 4 mid)
            ) * 4;
            ((per_layer_main + per_layer_lora) * n_layers + head + buffers) / (1024 * 1024)
        } else {
            let buffers = (self.n_embd * 4 + self.n_ff + self.vocab_size
                + self.n_embd * 2 + self.max_lora_rank
                + self.n_embd * 8 + self.max_lora_rank * 4
            ) * 4;
            buffers / (1024 * 1024)
        }
    }
}

// ============================================================================
// Standalone cuBLAS sgemv — avoids borrow-checker conflicts
// ============================================================================

/// GPU matrix-vector multiply: y = x @ M (standalone version).
///
/// This is a free function so inference.rs can call it with split borrows
/// from GpuContext fields without hitting Rust's borrow checker.
///
/// x: [K], M_logical: [K, N], y: [N]
///
/// GGUF stores weight matrices as [N, K] row-major (physical layout).
/// M_logical[i,j] = M_physical[j,i] = flat[j * K + i].
///
/// cuBLAS column-major interpretation:
///   We pass the flat data to cuBLAS as column-major A with m=N, n=K, lda=K.
///   Column-major A[i,j] = flat[i*1 + j*lda]... no, cuBLAS col-major: A[i,j] = flat[i + j*lda].
///
///   With OP_T (transpose): y = A^T * x
///   A^T[i,j] = A[j,i] = flat[j + i*lda] = flat[j + i*K]
///   y[i] = sum_j A^T[i,j] * x[j] = sum_j flat[j + i*K] * x[j]
///        = sum_j M_physical[i, j] * x[j]  where M_physical[row,col] = flat[row*K + col]
///
///   For M_physical = [N, K]: i ∈ [0,N), j ∈ [0,K) → y[i] = sum_j M_phys[i,j] * x[j]
///   This gives y = M_physical @ x, where M_phys is [N,K] and x is [K] → y is [N].
///   But we want y = x @ M_logical = x @ M_physical.T = M_physical @ x ← SAME THING! ✓
pub fn gpu_sgemv(
    blas: &CudaBlas,
    x: &CudaSlice<f32>,
    m: &CudaSlice<f32>,
    y: &mut CudaSlice<f32>,
    k: usize,
    n: usize,
) -> Result<(), String> {
    let cfg = GemvConfig {
        trans: cublasOperation_t::CUBLAS_OP_T,  // Transpose: reads [N,K] physical as [K,N] logical
        m: k as i32,      // rows of stored A in col-major sense = K
        n: n as i32,      // cols of stored A in col-major sense = N
        alpha: 1.0f32,
        lda: k as i32,    // leading dim = K (physical row stride of [N, K] data)
        incx: 1,
        beta: 0.0f32,
        incy: 1,
    };
    unsafe { blas.gemv(cfg, m, x, y) }
        .map_err(|e| format!("cuBLAS sgemv failed (k={}, n={}): {:?}", k, n, e))
}

// ============================================================================
// Standalone activation kernels — avoids borrow-checker conflicts
// ============================================================================
// These are free functions (like gpu_sgemv) so inference.rs can call them
// with split borrows from GpuContext fields. Method calls like
// `gpu.sigmoid_inplace(&mut gpu.buf_lora_mid)` won't compile because
// Rust can't borrow `gpu` for `&self` while mutably borrowing a field.

/// In-place sigmoid on a GPU buffer: data[i] = 1/(1+exp(-data[i]))
///
/// Launches the pre-compiled CUDA kernel on the given stream.
/// `n` is the number of elements to process (may be less than buffer capacity).
pub fn gpu_sigmoid_inplace(
    stream: &Arc<CudaStream>,
    kernel: &CudaFunction,
    data: &mut CudaSlice<f32>,
    n: usize,
) -> Result<(), String> {
    let block_size = 256u32;
    let grid_size = ((n as u32) + block_size - 1) / block_size;
    let cfg = LaunchConfig {
        grid_dim: (grid_size, 1, 1),
        block_dim: (block_size, 1, 1),
        shared_mem_bytes: 0,
    };
    let n_i32 = n as i32;
    unsafe {
        stream.launch_builder(kernel)
            .arg(data)
            .arg(&n_i32)
            .launch(cfg)
            .map_err(|e| format!("GPU sigmoid kernel launch failed: {:?}", e))?;
    }
    Ok(())
}

/// In-place tanh on a GPU buffer: data[i] = tanh(data[i])
///
/// Launches the pre-compiled CUDA kernel on the given stream.
/// `n` is the number of elements to process (may be less than buffer capacity).
pub fn gpu_tanh_inplace(
    stream: &Arc<CudaStream>,
    kernel: &CudaFunction,
    data: &mut CudaSlice<f32>,
    n: usize,
) -> Result<(), String> {
    let block_size = 256u32;
    let grid_size = ((n as u32) + block_size - 1) / block_size;
    let cfg = LaunchConfig {
        grid_dim: (grid_size, 1, 1),
        block_dim: (block_size, 1, 1),
        shared_mem_bytes: 0,
    };
    let n_i32 = n as i32;
    unsafe {
        stream.launch_builder(kernel)
            .arg(data)
            .arg(&n_i32)
            .launch(cfg)
            .map_err(|e| format!("GPU tanh kernel launch failed: {:?}", e))?;
    }
    Ok(())
}

/// In-place squared ReLU on a GPU buffer: data[i] = max(data[i], 0)^2
///
/// Used by ChannelMix to avoid GPU→CPU→GPU round-trip for the activation.
/// Launches the pre-compiled CUDA kernel on the given stream.
/// `n` is the number of elements to process (may be less than buffer capacity).
pub fn gpu_squared_relu_inplace(
    stream: &Arc<CudaStream>,
    kernel: &CudaFunction,
    data: &mut CudaSlice<f32>,
    n: usize,
) -> Result<(), String> {
    let block_size = 256u32;
    let grid_size = ((n as u32) + block_size - 1) / block_size;
    let cfg = LaunchConfig {
        grid_dim: (grid_size, 1, 1),
        block_dim: (block_size, 1, 1),
        shared_mem_bytes: 0,
    };
    let n_i32 = n as i32;
    unsafe {
        stream.launch_builder(kernel)
            .arg(data)
            .arg(&n_i32)
            .launch(cfg)
            .map_err(|e| format!("GPU squared_relu kernel launch failed: {:?}", e))?;
    }
    Ok(())
}
