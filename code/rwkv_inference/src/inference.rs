//! RWKV-7 Forward Pass — the core computation in compiled Rust.
//!
//! This replaces the Python `for layer_id, block in enumerate(self.blocks)` loop
//! that was taking minutes per generation. In Rust, this runs in milliseconds.
//!
//! Architecture:
//!   1. Token embedding + LayerNorm
//!   2. For each of 24 layers:
//!      a. TimeMix (temporal attention with RNN state)
//!      b. ChannelMix (feed-forward with squared ReLU)
//!   3. Output LayerNorm + head projection → logits
//!
//! Somatic modulation is applied at 5 points per layer (see somatic.rs).

use crate::model::{RWKVConfig, ModelWeights, RWKVState, LayerWeights};
use crate::somatic::SomaticState;
use rayon::prelude::*;
use std::time::Instant;

#[cfg(feature = "cuda")]
use crate::gpu::{GpuContext, gpu_sgemv, gpu_sigmoid_inplace, gpu_tanh_inplace, gpu_squared_relu_inplace};

/// Result of a forward pass.
pub struct ForwardResult {
    /// Logits for the LAST token position [vocab_size]
    pub logits: Vec<f32>,
    /// Collision chamber data for consciousness feed
    pub collision_data: Vec<CollisionData>,
}

/// Data extracted per layer for the collision chamber.
#[derive(Debug, Clone)]
pub struct CollisionData {
    pub layer_id: usize,
    pub receptance_mean: f32,
    pub is_recall: bool,
}

/// The compiled forward pass engine.
pub struct RWKVForwardPass {
    config: RWKVConfig,
    // Pre-allocated buffers to avoid repeated allocation
    buf_x: Vec<f32>,       // Working embedding [C]
    buf_ln: Vec<f32>,      // LayerNorm output [C]
    buf_tm: Vec<f32>,      // TimeMix output [C]
    buf_cm: Vec<f32>,      // ChannelMix output [C]
    buf_logits: Vec<f32>,  // Output logits [vocab_size]

    // ── Pre-allocated LoRA + lerp buffers (eliminates ~500 heap allocs/token) ──
    // Lerp intermediates [C] each
    buf_xx: Vec<f32>,
    buf_xr: Vec<f32>,
    buf_xw: Vec<f32>,
    buf_xk: Vec<f32>,
    buf_xv: Vec<f32>,
    buf_xa: Vec<f32>,
    buf_xg: Vec<f32>,
    // LoRA inner products (max rank across all LoRA types)
    buf_lora_inner: Vec<f32>,   // [max_rank] — reused for v, g, w, a inner products
    // LoRA outputs [C] each
    buf_vg: Vec<f32>,           // V-bonus gate
    buf_g: Vec<f32>,            // Gate output
    buf_w: Vec<f32>,            // Time decay
    buf_w_dynamic: Vec<f32>,    // W-decay LoRA output
    buf_a_dynamic: Vec<f32>,    // Association LoRA output
    buf_a_coeff: Vec<f32>,      // Association coefficient
    buf_kk: Vec<f32>,           // Normalized key
    // State evolution output + residual
    buf_output: Vec<f32>,       // [C]
    buf_residual: Vec<f32>,     // [C]
    // ChannelMix shift
    buf_xk_cm: Vec<f32>,       // [C]
    // State evolution per-head scratch (pre-allocated to avoid rayon allocs)
    // Each head needs: s_dot_kkt[N], kkt_at[N], icl_term[N*N], vk[N*N]
    // Total per head: 2*N + 2*N*N. For N=64: 128 + 8192 = 8320 floats
    buf_head_scratch: Vec<f32>, // [H * (2*N + 2*N*N)]
}

impl RWKVForwardPass {
    pub fn new(config: &RWKVConfig) -> Self {
        let c = config.n_embd;
        let v = config.vocab_size;
        let h = config.n_head;
        let n = config.head_size;
        let max_rank = 512; // Conservative max across all LoRA ranks (actual varies by model)
        let head_scratch_per = 2 * n + 2 * n * n; // s_dot_kkt + kkt_at + icl_term + vk
        RWKVForwardPass {
            config: config.clone(),
            buf_x: vec![0.0; c],
            buf_ln: vec![0.0; c],
            buf_tm: vec![0.0; c],
            buf_cm: vec![0.0; c],
            buf_logits: vec![0.0; v],
            // Lerp intermediates
            buf_xx: vec![0.0; c],
            buf_xr: vec![0.0; c],
            buf_xw: vec![0.0; c],
            buf_xk: vec![0.0; c],
            buf_xv: vec![0.0; c],
            buf_xa: vec![0.0; c],
            buf_xg: vec![0.0; c],
            // LoRA buffers
            buf_lora_inner: vec![0.0; max_rank],
            buf_vg: vec![0.0; c],
            buf_g: vec![0.0; c],
            buf_w: vec![0.0; c],
            buf_w_dynamic: vec![0.0; c],
            buf_a_dynamic: vec![0.0; c],
            buf_a_coeff: vec![0.0; c],
            buf_kk: vec![0.0; c],
            // State evolution
            buf_output: vec![0.0; c],
            buf_residual: vec![0.0; c],
            // ChannelMix
            buf_xk_cm: vec![0.0; c],
            // Per-head scratch for state evolution
            buf_head_scratch: vec![0.0; h * head_scratch_per],
        }
    }

    /// Full forward pass. Processes all tokens sequentially (RNN mode).
    /// For prompt: processes each token and evolves state.
    /// For generation: single token, single state evolution.
    ///
    /// Returns logits for the LAST token position.
    pub fn forward(
        &mut self,
        token_ids: &[u32],
        weights: &ModelWeights,
        state: &mut RWKVState,
        somatic: &SomaticState,
    ) -> Result<ForwardResult, String> {
        let c = self.config.n_embd;
        let v = self.config.vocab_size;
        let half_layers = self.config.n_layer / 2;

        let mut collision_data = Vec::new();

        // Process each token
        for &token_id in token_ids {
            if token_id as usize >= v {
                return Err(format!("Token ID {} exceeds vocab size {}", token_id, v));
            }

            // Step 1: Embedding lookup
            let emb_offset = (token_id as usize) * c;
            self.buf_x.copy_from_slice(&weights.emb_weight[emb_offset..emb_offset + c]);

            // Step 2: Embedding LayerNorm
            layer_norm(&mut self.buf_x, &weights.emb_ln_weight, &weights.emb_ln_bias);

            // Step 3: Process through all layers
            for layer_id in 0..self.config.n_layer {
                let layer = &weights.layers[layer_id];

                // --- TimeMix ---
                // LayerNorm before TimeMix
                self.buf_ln.copy_from_slice(&self.buf_x);
                layer_norm(&mut self.buf_ln, &layer.ln1.weight, &layer.ln1.bias);

                // TimeMix forward
                let (tm_output, receptance_mean) = self.time_mix_forward(
                    &self.buf_ln.clone(),  // TODO: avoid clone with double-buffering
                    layer_id,
                    layer,
                    state,
                    somatic,
                );

                // Residual connection
                for i in 0..c {
                    self.buf_x[i] += tm_output[i];
                }

                // Collision data for consciousness
                collision_data.push(CollisionData {
                    layer_id,
                    receptance_mean,
                    is_recall: layer_id < half_layers,
                });

                // --- ChannelMix ---
                // LayerNorm before ChannelMix
                self.buf_ln.copy_from_slice(&self.buf_x);
                layer_norm(&mut self.buf_ln, &layer.ln2.weight, &layer.ln2.bias);

                // ChannelMix forward
                let cm_output = self.channel_mix_forward(
                    &self.buf_ln.clone(),  // TODO: avoid clone
                    layer_id,
                    layer,
                    state,
                    somatic,
                );

                // Residual connection
                for i in 0..c {
                    self.buf_x[i] += cm_output[i];
                }
            }
        }

        // Step 4: Output LayerNorm
        layer_norm(&mut self.buf_x, &weights.head_ln_weight, &weights.head_ln_bias);

        // Step 5: Output projection: x @ head_weight → logits
        // head_weight is [C, vocab_size], x is [C]
        self.buf_logits.iter_mut().for_each(|v| *v = 0.0);
        matmul_vec(&self.buf_x, &weights.head_weight, &mut self.buf_logits, c, v);

        Ok(ForwardResult {
            logits: self.buf_logits.clone(),
            collision_data,
        })
    }

    // ========================================================================
    // GPU-accelerated forward pass (Phase 1: large matmuls on GPU)
    // ========================================================================

    /// GPU-accelerated forward pass. Large matrix-vector multiplies run on GPU
    /// via cuBLAS sgemv. Small ops (LoRA, element-wise, norms, state evolution)
    /// stay on CPU.
    ///
    /// GPU-accelerated operations per layer (7 sgemv calls):
    ///   - TimeMix R, K, V projections: [C, C] × 3
    ///   - TimeMix output projection: [C, C]
    ///   - ChannelMix key projection: [C, 4C]
    ///   - ChannelMix value projection: [4C, C]
    /// Plus the head projection: [C, V]
    ///
    /// Uses standalone gpu_sgemv() with split borrows to avoid borrow-checker
    /// conflicts when accessing GpuContext fields simultaneously.
    #[cfg(feature = "cuda")]
    pub fn forward_gpu(
        &mut self,
        token_ids: &[u32],
        weights: &ModelWeights,
        state: &mut RWKVState,
        somatic: &SomaticState,
        gpu: &mut GpuContext,
    ) -> Result<ForwardResult, String> {
        let c = self.config.n_embd;
        let v = self.config.vocab_size;
        let n_ff = self.config.n_ff();
        let half_layers = self.config.n_layer / 2;

        let gpu_weights = gpu.weights.as_ref()
            .ok_or_else(|| "GPU weights not uploaded".to_string())?;

        let mut collision_data = Vec::new();

        // ── Profiling accumulators (per-token, summed across layers) ──
        let mut _prof_lerp_us = 0u128;
        let mut _prof_rkv_us = 0u128;
        let mut _prof_lora_us = 0u128;
        let mut _prof_state_us = 0u128;
        let mut _prof_outproj_us = 0u128;
        let mut _prof_cm_us = 0u128;
        let mut _prof_head_us = 0u128;
        let _prof_enabled = token_ids.len() == 1; // Only profile single-token (generation)

        for &token_id in token_ids {
            if token_id as usize >= v {
                return Err(format!("Token ID {} exceeds vocab size {}", token_id, v));
            }

            // ─── Embedding + LayerNorm (CPU) ───
            let emb_offset = (token_id as usize) * c;
            self.buf_x.copy_from_slice(&weights.emb_weight[emb_offset..emb_offset + c]);
            layer_norm(&mut self.buf_x, &weights.emb_ln_weight, &weights.emb_ln_bias);

            // ─── Process through all layers ───
            for layer_id in 0..self.config.n_layer {
                let layer = &weights.layers[layer_id];
                let tm = &layer.time_mix;
                let cm = &layer.channel_mix;
                let h = self.config.n_head;
                let n = self.config.head_size;

                // ── TimeMix: LayerNorm (CPU) ──
                let _t0 = Instant::now();
                self.buf_ln.copy_from_slice(&self.buf_x);
                layer_norm(&mut self.buf_ln, &layer.ln1.weight, &layer.ln1.bias);

                // ── Token shifting + lerp (CPU element-wise, pre-allocated) ──
                let x = &self.buf_ln;
                let x_prev = &state.att_shifts[layer_id];
                for i in 0..c {
                    self.buf_xx[i] = x_prev[i] - x[i];
                }

                // GGUF lerp_fused layout: COMPONENT-MAJOR
                // ne=(C, 1, 1, n_comp) → physical flat = [n_comp, C]
                // flat[comp * C + channel] where comp order = (r, w, k, v, a, g)
                let lerp_len = tm.lerp_fused.len();
                let n_comp = if lerp_len >= c * 6 { 6 } else if lerp_len >= c * 5 { 5 } else { 0 };

                for i in 0..c {
                    if n_comp >= 5 {
                        let lr = tm.lerp_fused[0 * c + i];
                        let lw = tm.lerp_fused[1 * c + i];
                        let lk = tm.lerp_fused[2 * c + i];
                        let lv = tm.lerp_fused[3 * c + i];
                        let la = tm.lerp_fused[4 * c + i];
                        let lg = if n_comp >= 6 { tm.lerp_fused[5 * c + i] } else { 0.5 };
                        let xxi = self.buf_xx[i];

                        self.buf_xr[i] = x[i] + xxi * lr;
                        self.buf_xw[i] = x[i] + xxi * lw;
                        self.buf_xk[i] = x[i] + xxi * lk;
                        self.buf_xv[i] = x[i] + xxi * lv;
                        self.buf_xa[i] = x[i] + xxi * la;
                        self.buf_xg[i] = x[i] + xxi * lg;
                    } else {
                        self.buf_xr[i] = x[i];
                        self.buf_xw[i] = x[i];
                        self.buf_xk[i] = x[i];
                        self.buf_xv[i] = x[i];
                        self.buf_xa[i] = x[i];
                        self.buf_xg[i] = x[i];
                    }
                }

                state.att_shifts[layer_id] = x.to_vec();
                if _prof_enabled { _prof_lerp_us += _t0.elapsed().as_micros(); }

                let _t1 = Instant::now();
                // ═══════════════════════════════════════════════════════════
                // PHASE A: Queue ALL GPU sgemvs in ONE burst — SINGLE sync
                // ═══════════════════════════════════════════════════════════
                // RKV projections + all 4 LoRA chains are queued on the GPU
                // stream before any synchronization. Each chain uses dedicated
                // buffers so there are no data dependencies between them.
                // This replaces 5 separate syncs with 1.

                // LoRA ranks from GPU weight metadata
                let rank_v = gpu_weights.rank_v[layer_id];
                let rank_g = gpu_weights.rank_g[layer_id];
                let rank_w = gpu_weights.rank_w[layer_id];
                let rank_a = gpu_weights.rank_a[layer_id];

                // ── RKV projections: reuse buf_c for sequential H2D ──
                // Stream ordering: each sgemv reads buf_c before next H2D overwrites it.
                gpu.stream.memcpy_htod(&self.buf_xr, &mut gpu.buf_c)
                    .map_err(|e| format!("L{} H2D xr: {:?}", layer_id, e))?;
                gpu_sgemv(&gpu.blas, &gpu.buf_c, &gpu_weights.tm_receptance[layer_id],
                    &mut gpu.buf_c2, c, c)?;

                gpu.stream.memcpy_htod(&self.buf_xk, &mut gpu.buf_c)
                    .map_err(|e| format!("L{} H2D xk: {:?}", layer_id, e))?;
                gpu_sgemv(&gpu.blas, &gpu.buf_c, &gpu_weights.tm_key[layer_id],
                    &mut gpu.buf_c3, c, c)?;

                gpu.stream.memcpy_htod(&self.buf_xv, &mut gpu.buf_c)
                    .map_err(|e| format!("L{} H2D xv: {:?}", layer_id, e))?;
                gpu_sgemv(&gpu.blas, &gpu.buf_c, &gpu_weights.tm_value[layer_id],
                    &mut gpu.buf_c4, c, c)?;

                // ── LoRA chains: each uses dedicated in/mid/out buffers ──
                // V-bonus LoRA (no activation between down/up)
                // Layer 0: skip (stores v_first instead). Layer >0: queue sgemvs.
                let do_vbonus = layer_id > 0;
                if do_vbonus {
                    gpu.stream.memcpy_htod(&self.buf_xv, &mut gpu.buf_lora_in_v)
                        .map_err(|e| format!("L{} H2D xv lora: {:?}", layer_id, e))?;
                    gpu_sgemv(&gpu.blas, &gpu.buf_lora_in_v,
                        &gpu_weights.lora_v1[layer_id],
                        &mut gpu.buf_lora_mid_v, c, rank_v)?;
                    gpu_sgemv(&gpu.blas, &gpu.buf_lora_mid_v,
                        &gpu_weights.lora_v2[layer_id],
                        &mut gpu.buf_lora_out_v, rank_v, c)?;
                }

                // Gate LoRA (sigmoid between down/up — runs on GPU)
                gpu.stream.memcpy_htod(&self.buf_xg, &mut gpu.buf_lora_in_g)
                    .map_err(|e| format!("L{} H2D xg lora: {:?}", layer_id, e))?;
                gpu_sgemv(&gpu.blas, &gpu.buf_lora_in_g,
                    &gpu_weights.lora_g1[layer_id],
                    &mut gpu.buf_lora_mid_g, c, rank_g)?;
                gpu_sigmoid_inplace(&gpu.stream, &gpu.kernel_sigmoid,
                    &mut gpu.buf_lora_mid_g, rank_g)?;
                gpu_sgemv(&gpu.blas, &gpu.buf_lora_mid_g,
                    &gpu_weights.lora_g2[layer_id],
                    &mut gpu.buf_lora_out_g, rank_g, c)?;

                // W-decay LoRA (tanh between down/up — runs on GPU)
                gpu.stream.memcpy_htod(&self.buf_xw, &mut gpu.buf_lora_in_w)
                    .map_err(|e| format!("L{} H2D xw lora: {:?}", layer_id, e))?;
                gpu_sgemv(&gpu.blas, &gpu.buf_lora_in_w,
                    &gpu_weights.lora_w1[layer_id],
                    &mut gpu.buf_lora_mid_w, c, rank_w)?;
                gpu_tanh_inplace(&gpu.stream, &gpu.kernel_tanh,
                    &mut gpu.buf_lora_mid_w, rank_w)?;
                gpu_sgemv(&gpu.blas, &gpu.buf_lora_mid_w,
                    &gpu_weights.lora_w2[layer_id],
                    &mut gpu.buf_lora_out_w, rank_w, c)?;

                // Association LoRA (no activation between down/up)
                gpu.stream.memcpy_htod(&self.buf_xa, &mut gpu.buf_lora_in_a)
                    .map_err(|e| format!("L{} H2D xa lora: {:?}", layer_id, e))?;
                gpu_sgemv(&gpu.blas, &gpu.buf_lora_in_a,
                    &gpu_weights.lora_a1[layer_id],
                    &mut gpu.buf_lora_mid_a, c, rank_a)?;
                gpu_sgemv(&gpu.blas, &gpu.buf_lora_mid_a,
                    &gpu_weights.lora_a2[layer_id],
                    &mut gpu.buf_lora_out_a, rank_a, c)?;

                // ═══ SINGLE SYNC — wait for ALL 15 sgemvs + 2 activations ═══
                gpu.stream.synchronize()
                    .map_err(|e| format!("L{} sync phase_a: {:?}", layer_id, e))?;

                // ── Batch download all results ──
                let mut r = gpu.stream.memcpy_dtov(&gpu.buf_c2)
                    .map_err(|e| format!("L{} D2H r: {:?}", layer_id, e))?;
                let mut k = gpu.stream.memcpy_dtov(&gpu.buf_c3)
                    .map_err(|e| format!("L{} D2H k: {:?}", layer_id, e))?;
                let mut v_vec = gpu.stream.memcpy_dtov(&gpu.buf_c4)
                    .map_err(|e| format!("L{} D2H v: {:?}", layer_id, e))?;

                let g_out = gpu.stream.memcpy_dtov(&gpu.buf_lora_out_g)
                    .map_err(|e| format!("L{} D2H g: {:?}", layer_id, e))?;
                let w_out = gpu.stream.memcpy_dtov(&gpu.buf_lora_out_w)
                    .map_err(|e| format!("L{} D2H w: {:?}", layer_id, e))?;
                let a_out = gpu.stream.memcpy_dtov(&gpu.buf_lora_out_a)
                    .map_err(|e| format!("L{} D2H a: {:?}", layer_id, e))?;

                if _prof_enabled { _prof_rkv_us += _t1.elapsed().as_micros(); }

                // ═══════════════════════════════════════════════════════════
                // PHASE B: CPU post-processing — no GPU
                // ═══════════════════════════════════════════════════════════
                let _t2 = Instant::now();

                // ── V-bonus gate (CPU) ──
                if layer_id == 0 {
                    state.v_first = Some(v_vec.clone());
                } else if let Some(ref v_first) = state.v_first {
                    let vg = gpu.stream.memcpy_dtov(&gpu.buf_lora_out_v)
                        .map_err(|e| format!("L{} D2H v_bonus: {:?}", layer_id, e))?;
                    for i in 0..c {
                        let gate = sigmoid(tm.v0[i] + vg[i]);
                        v_vec[i] = v_vec[i] + (v_first[i] - v_vec[i]) * gate;
                    }
                }

                // ── Gate output ──
                self.buf_g[..c].copy_from_slice(&g_out[..c]);

                // ── Somatic injection 1: Receptance (CPU) ──
                let r_adj = (somatic.arousal - 0.5) * 2.0;
                for i in 0..c {
                    r[i] += r_adj;
                }
                let receptance_mean = r.iter().map(|v| sigmoid(*v)).sum::<f32>() / c as f32;

                // ── W-decay (CPU) ──
                for i in 0..c {
                    self.buf_w[i] = (-0.606531 * sigmoid(tm.w0[i] + w_out[i])).exp();
                }

                // Somatic injection 2: Time decay
                let decay_mult = 1.0 + (somatic.stress - 0.5) * 0.5;
                for i in 0..c {
                    self.buf_w[i] *= decay_mult;
                    self.buf_w[i] = self.buf_w[i].clamp(0.0, 1.0);
                }

                // ── Association (CPU) ──
                for i in 0..c {
                    self.buf_a_coeff[i] = sigmoid(tm.a0[i] + a_out[i]);
                }

                // Somatic injection 3: Association strength
                let assoc_mult = 1.0 + (somatic.valence - 0.5) * 0.3;
                for i in 0..c {
                    self.buf_a_coeff[i] *= assoc_mult;
                }

                // ── Key normalization (CPU, pre-allocated) ──
                for i in 0..c {
                    self.buf_kk[i] = k[i] * tm.k_k[i];
                }
                for head in 0..h {
                    let start = head * n;
                    let end = start + n;
                    let norm: f32 = self.buf_kk[start..end].iter().map(|v| v * v).sum::<f32>().sqrt().max(1e-12);
                    for i in start..end {
                        self.buf_kk[i] /= norm;
                    }
                }

                for i in 0..c {
                    k[i] *= 1.0 + (self.buf_a_coeff[i] - 1.0) * tm.k_a[i];
                }

                if _prof_enabled { _prof_lora_us += _t2.elapsed().as_micros(); }

                let _t3 = Instant::now();
                // ═══ State Evolution — THE HEART OF RWKV (CPU, parallel across heads) ═══
                // Pre-allocated buffers: buf_output, buf_residual, buf_head_scratch
                self.buf_output[..c].fill(0.0);

                // Somatic injection 4: Memory formation (computed once, shared)
                let state_push = 1.0 + (somatic.intensity - 0.5) * 0.4;

                // Take immutable refs before the rayon section (avoids borrow conflicts)
                let kk_ref = &self.buf_kk[..c];
                let a_coeff_ref = &self.buf_a_coeff[..c];
                let w_ref = &self.buf_w[..c];

                let nn = n * n;
                let wkv_state = &mut state.wkv_states[layer_id];
                let state_chunks: Vec<&mut [f32]> = wkv_state.chunks_mut(nn).collect();
                let output_chunks: Vec<&mut [f32]> = self.buf_output[..c].chunks_mut(n).collect();

                // Per-head scratch layout: [s_dot_kkt(n), kkt_at(n), icl_term(nn), vk(nn)]
                let head_scratch_per = 2 * n + 2 * nn;
                let scratch_chunks: Vec<&mut [f32]> = self.buf_head_scratch
                    .chunks_mut(head_scratch_per).take(h).collect();

                // Process all heads in parallel — ZERO allocations inside closure
                state_chunks.into_par_iter()
                    .zip(output_chunks.into_par_iter())
                    .zip(scratch_chunks.into_par_iter())
                    .enumerate()
                    .for_each(|(head, ((head_state, head_output), scratch))| {
                        let h_start = head * n;

                        // Split scratch into sub-buffers
                        let (s_dot_kkt, rest) = scratch.split_at_mut(n);
                        let (kkt_at, rest) = rest.split_at_mut(n);
                        let (icl_term, vk) = rest.split_at_mut(nn);

                        // Step 1: s_dot_kkt = head_state @ (-kk)
                        for i in 0..n {
                            let mut sum = 0.0_f32;
                            for j in 0..n {
                                sum += head_state[i * n + j] * (-kk_ref[h_start + j]);
                            }
                            s_dot_kkt[i] = sum;
                        }

                        // Step 2: kkt_at = kk * a_coeff (element-wise)
                        for j in 0..n {
                            kkt_at[j] = kk_ref[h_start + j] * a_coeff_ref[h_start + j];
                        }

                        // Step 3: icl_term = outer(s_dot_kkt, kkt_at)
                        for i in 0..n {
                            for j in 0..n {
                                icl_term[i * n + j] = s_dot_kkt[i] * kkt_at[j];
                            }
                        }

                        // Step 4: vk = outer(v, k) * state_push
                        for i in 0..n {
                            let vi = v_vec[h_start + i] * state_push;
                            for j in 0..n {
                                vk[i * n + j] = vi * k[h_start + j];
                            }
                        }

                        // Step 5: state = state * decay + icl_term + vk
                        for i in 0..n {
                            for j in 0..n {
                                let idx = i * n + j;
                                head_state[idx] = head_state[idx] * w_ref[h_start + j]
                                    + icl_term[idx] + vk[idx];
                            }
                        }

                        // Step 6: output = state @ r
                        for i in 0..n {
                            let mut sum = 0.0_f32;
                            for j in 0..n {
                                sum += head_state[i * n + j] * r[h_start + j];
                            }
                            head_output[i] = sum;
                        }
                    });

                // ── GroupNorm + residual (CPU, pre-allocated) ──
                group_norm(&mut self.buf_output[..c], h, n, &tm.ln_weight, &tm.ln_bias);

                for head in 0..h {
                    let start = head * n;
                    let mut rksum = 0.0_f32;
                    for i in 0..n {
                        rksum += r[start + i] * k[start + i] * tm.r_k[start + i];
                    }
                    for i in 0..n {
                        self.buf_residual[start + i] = rksum * v_vec[start + i];
                    }
                }
                for i in 0..c {
                    self.buf_output[i] += self.buf_residual[i];
                }

                // ── Gate + somatic output scale (CPU) ──
                for i in 0..c {
                    self.buf_output[i] *= self.buf_g[i];
                }
                let out_scale = 0.7 + somatic.confidence * 0.6;
                for i in 0..c {
                    self.buf_output[i] *= out_scale;
                }

                if _prof_enabled { _prof_state_us += _t3.elapsed().as_micros(); }

                let _t4 = Instant::now();
                // ═══ GPU: Output projection [C, C] — sync before ChannelMix ═══
                // CORRECTNESS FIX: ChannelMix LayerNorm MUST operate on buf_x
                // AFTER the TimeMix output residual is applied. The previous
                // version overlapped ChannelMix prep with the output sgemv,
                // but that computed LayerNorm on buf_x WITHOUT the TimeMix
                // contribution — producing wrong ChannelMix input for every layer.
                gpu.stream.memcpy_htod(&self.buf_output[..c], &mut gpu.buf_c)
                    .map_err(|e| format!("L{} H2D output: {:?}", layer_id, e))?;
                gpu_sgemv(&gpu.blas, &gpu.buf_c, &gpu_weights.tm_output[layer_id],
                    &mut gpu.buf_c2, c, c)?;

                // Sync + download output projection
                gpu.stream.synchronize()
                    .map_err(|e| format!("L{} sync output: {:?}", layer_id, e))?;
                let projected = gpu.stream.memcpy_dtov(&gpu.buf_c2)
                    .map_err(|e| format!("L{} D2H projected: {:?}", layer_id, e))?;

                // Residual connection — TimeMix output applied to buf_x
                for i in 0..c {
                    self.buf_x[i] += projected[i];
                }

                // Collision data (after TimeMix is fully done)
                collision_data.push(CollisionData {
                    layer_id,
                    receptance_mean,
                    is_recall: layer_id < half_layers,
                });

                // ─── ChannelMix prep (CPU) — AFTER residual applied ───
                // LayerNorm now operates on correct buf_x (with TimeMix residual)
                self.buf_ln.copy_from_slice(&self.buf_x);
                layer_norm(&mut self.buf_ln, &layer.ln2.weight, &layer.ln2.bias);

                // Token shifting (CPU, pre-allocated)
                let x_cm = &self.buf_ln;
                let x_prev_cm = &state.ffn_shifts[layer_id];
                for i in 0..c {
                    let xx_cm = x_prev_cm[i] - x_cm[i];
                    self.buf_xk_cm[i] = x_cm[i] + xx_cm * cm.lerp_k[i]; // NO sigmoid
                }
                state.ffn_shifts[layer_id] = x_cm.to_vec();

                // ═══════════════════════════════════════════════════════════
                // PHASE D: ChannelMix — ALL on GPU (key + squared_relu + value)
                // ═══════════════════════════════════════════════════════════
                // H2D → sgemv_key → GPU squared_relu → sgemv_val → sync → D2H
                // (1 sync + 2 PCIe transfers — no CPU activation round-trip!)
                gpu.stream.memcpy_htod(&self.buf_xk_cm[..c], &mut gpu.buf_c)
                    .map_err(|e| format!("L{} H2D xk_cm: {:?}", layer_id, e))?;
                gpu_sgemv(&gpu.blas, &gpu.buf_c, &gpu_weights.cm_key[layer_id],
                    &mut gpu.buf_ff, c, n_ff)?;
                // Squared ReLU on GPU in-place — no PCIe round-trip!
                gpu_squared_relu_inplace(&gpu.stream, &gpu.kernel_squared_relu,
                    &mut gpu.buf_ff, n_ff)?;
                // Value sgemv reads activated buf_ff directly (stream ordering)
                gpu_sgemv(&gpu.blas, &gpu.buf_ff, &gpu_weights.cm_value[layer_id],
                    &mut gpu.buf_c2, n_ff, c)?;
                // Single sync for entire ChannelMix
                gpu.stream.synchronize()
                    .map_err(|e| format!("L{} sync cm: {:?}", layer_id, e))?;
                let cm_out = gpu.stream.memcpy_dtov(&gpu.buf_c2)
                    .map_err(|e| format!("L{} D2H cm: {:?}", layer_id, e))?;

                // Somatic output scale + residual
                let cm_scale = 0.7 + somatic.confidence * 0.6;
                for i in 0..c {
                    self.buf_x[i] += cm_out[i] * cm_scale;
                }
                if _prof_enabled { _prof_cm_us += _t4.elapsed().as_micros(); }
            }
        }

        // ── Write profiling summary to file (generation mode only) ──
        if _prof_enabled && token_ids.len() == 1 {
            let total = _prof_lerp_us + _prof_rkv_us + _prof_lora_us + _prof_state_us + _prof_cm_us;
            if total > 0 {
                static PROF_COUNT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
                let count = PROF_COUNT.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                // Write every token to file (append mode)
                use std::io::Write;
                let line = format!("[PROFILE] tok#{}: lerp={}us gpu_batch={}us cpu_post={}us state={}us outproj+cm={}us total={}us ({:.1} tok/s)\n",
                    count, _prof_lerp_us, _prof_rkv_us, _prof_lora_us, _prof_state_us, _prof_cm_us, total,
                    1_000_000.0 / total as f64);
                // Also try eprintln (may work in some contexts)
                if count % 10 == 0 {
                    eprintln!("{}", line.trim());
                }
                // Write to file — most reliable
                if let Ok(mut f) = std::fs::OpenOptions::new()
                    .create(true).append(true)
                    .open(r"F:\Sandbox\failure_factory\akashic_v2\state\rwkv_profile.log")
                {
                    let _ = f.write_all(line.as_bytes());
                }
            }
        }

        // ─── Output LayerNorm (CPU) ───
        layer_norm(&mut self.buf_x, &weights.head_ln_weight, &weights.head_ln_bias);

        // ═══ GPU: Head projection [C, V] ═══
        gpu.stream.memcpy_htod(&self.buf_x, &mut gpu.buf_c)
            .map_err(|e| format!("H2D head input: {:?}", e))?;
        gpu_sgemv(&gpu.blas, &gpu.buf_c, &gpu.weights.as_ref().unwrap().head_weight,
            &mut gpu.buf_logits, c, v)?;
        gpu.stream.synchronize()
            .map_err(|e| format!("sync head: {:?}", e))?;
        let logits = gpu.stream.memcpy_dtov(&gpu.buf_logits)
            .map_err(|e| format!("D2H logits: {:?}", e))?;

        Ok(ForwardResult {
            logits,
            collision_data,
        })
    }

    /// TimeMix forward pass for a single token (RNN mode, T=1).
    ///
    /// Returns (output [C], receptance_mean for collision data).
    fn time_mix_forward(
        &self,
        x: &[f32],      // LayerNorm'd input [C]
        layer_id: usize,
        layer: &LayerWeights,
        state: &mut RWKVState,
        somatic: &SomaticState,
    ) -> (Vec<f32>, f32) {
        let c = self.config.n_embd;
        let h = self.config.n_head;
        let n = self.config.head_size;
        let tm = &layer.time_mix;

        // --- Token Shifting ---
        // x_prev = att_shift from last token
        let x_prev = &state.att_shifts[layer_id];
        let mut xx = vec![0.0_f32; c];  // x_prev - x
        for i in 0..c {
            xx[i] = x_prev[i] - x[i];
        }

        // Compute lerped inputs for each component using fused lerp weights.
        // GGUF lerp_fused layout: COMPONENT-MAJOR
        // ne=(C, 1, 1, n_comp) → physical flat = [n_comp, C]
        // flat[comp * C + channel] where comp order = (r, w, k, v, a, g)
        let mut xr = vec![0.0_f32; c];
        let mut xw = vec![0.0_f32; c];
        let mut xk = vec![0.0_f32; c];
        let mut xv = vec![0.0_f32; c];
        let mut xa = vec![0.0_f32; c];
        let mut xg = vec![0.0_f32; c];

        let lerp_len = tm.lerp_fused.len();
        let n_comp = if lerp_len >= c * 6 { 6 } else if lerp_len >= c * 5 { 5 } else { 0 };

        for i in 0..c {
            if n_comp >= 5 {
                // Lerp weights are raw mix coefficients — NO sigmoid!
                // Formula: xr = x + (x_prev - x) * lerp = x + xx * lerp
                // Matches llama.cpp: xxx = sx * lerp_fused + cur
                let lr = tm.lerp_fused[0 * c + i];
                let lw = tm.lerp_fused[1 * c + i];
                let lk = tm.lerp_fused[2 * c + i];
                let lv = tm.lerp_fused[3 * c + i];
                let la = tm.lerp_fused[4 * c + i];
                let lg = if n_comp >= 6 { tm.lerp_fused[5 * c + i] } else { 0.5 };

                xr[i] = x[i] + xx[i] * lr;
                xw[i] = x[i] + xx[i] * lw;
                xk[i] = x[i] + xx[i] * lk;
                xv[i] = x[i] + xx[i] * lv;
                xa[i] = x[i] + xx[i] * la;
                xg[i] = x[i] + xx[i] * lg;
            } else {
                // Fallback: no lerp, just use x directly
                xr[i] = x[i];
                xw[i] = x[i];
                xk[i] = x[i];
                xv[i] = x[i];
                xa[i] = x[i];
                xg[i] = x[i];
            }
        }

        // Save current x as next token's att_shift
        state.att_shifts[layer_id] = x.to_vec();

        // --- Compute R, K, V projections ---
        let mut r = vec![0.0_f32; c];
        let mut k = vec![0.0_f32; c];
        let mut v = vec![0.0_f32; c];
        matmul_vec(&xr, &tm.receptance, &mut r, c, c);
        matmul_vec(&xk, &tm.key, &mut k, c, c);
        matmul_vec(&xv, &tm.value, &mut v, c, c);

        // --- V-bonus (layer 0 stores v_first, others blend) ---
        if layer_id == 0 {
            state.v_first = Some(v.clone());
        } else if let Some(ref v_first) = state.v_first {
            // v_gate = sigmoid(v0 + (xv @ v1) @ v2)
            let rank_v = if c > 0 { tm.v1.len() / c } else { 32 };
            let rank_v = rank_v.max(1); // safety: never zero
            let mut vg_inner = vec![0.0_f32; rank_v];
            matmul_vec(&xv, &tm.v1, &mut vg_inner, c, rank_v);
            let mut vg = vec![0.0_f32; c];
            matmul_vec(&vg_inner, &tm.v2, &mut vg, rank_v, c);
            for i in 0..c {
                let gate = sigmoid(tm.v0[i] + vg[i]);
                v[i] = v[i] + (v_first[i] - v[i]) * gate;
            }
        }

        // --- Gate (LoRA): g = sigmoid(xg @ g1) @ g2 ---
        let rank_g = if c > 0 { tm.g1.len() / c } else { 128 };
        let rank_g = rank_g.max(1);
        let mut g_inner = vec![0.0_f32; rank_g];
        matmul_vec(&xg, &tm.g1, &mut g_inner, c, rank_g);
        // Sigmoid ONLY on first matmul output
        for val in &mut g_inner {
            *val = sigmoid(*val);
        }
        let mut g = vec![0.0_f32; c];
        matmul_vec(&g_inner, &tm.g2, &mut g, rank_g, c);

        // --- Somatic injection 1: Receptance adjustment ---
        let r_adj = (somatic.arousal - 0.5) * 2.0;
        for i in 0..c {
            r[i] += r_adj;
        }

        // Track receptance mean for collision data
        let receptance_mean = r.iter().map(|v| sigmoid(*v)).sum::<f32>() / c as f32;

        // --- Time Decay ---
        // w = exp(-0.606531 * sigmoid(w0 + tanh(xw @ w1) @ w2))
        let rank_w = if c > 0 { tm.w1.len() / c } else { 64 };
        let rank_w = rank_w.max(1);
        let mut w_inner = vec![0.0_f32; rank_w];
        matmul_vec(&xw, &tm.w1, &mut w_inner, c, rank_w);
        for val in &mut w_inner {
            *val = val.tanh();
        }
        let mut w_dynamic = vec![0.0_f32; c];
        matmul_vec(&w_inner, &tm.w2, &mut w_dynamic, rank_w, c);

        let mut w = vec![0.0_f32; c];
        for i in 0..c {
            w[i] = (-0.606531 * sigmoid(tm.w0[i] + w_dynamic[i])).exp();
        }

        // Somatic injection 2: Time decay multiplier
        let decay_mult = 1.0 + (somatic.stress - 0.5) * 0.5;
        for i in 0..c {
            w[i] *= decay_mult;
            w[i] = w[i].clamp(0.0, 1.0);  // Safety clamp
        }

        // --- Association coefficient ---
        // a = sigmoid(a0 + (xa @ a1) @ a2)
        let rank_a = if c > 0 { tm.a1.len() / c } else { 64 };
        let rank_a = rank_a.max(1);
        let mut a_inner = vec![0.0_f32; rank_a];
        matmul_vec(&xa, &tm.a1, &mut a_inner, c, rank_a);
        let mut a_dynamic = vec![0.0_f32; c];
        matmul_vec(&a_inner, &tm.a2, &mut a_dynamic, rank_a, c);

        let mut a_coeff = vec![0.0_f32; c];
        for i in 0..c {
            a_coeff[i] = sigmoid(tm.a0[i] + a_dynamic[i]);
        }

        // Somatic injection 3: Association strength
        let assoc_mult = 1.0 + (somatic.valence - 0.5) * 0.3;
        for i in 0..c {
            a_coeff[i] *= assoc_mult;
        }

        // --- Key normalization ---
        let mut kk = vec![0.0_f32; c];
        for i in 0..c {
            kk[i] = k[i] * tm.k_k[i];
        }
        // L2 normalize per head
        for head in 0..h {
            let start = head * n;
            let end = start + n;
            let norm: f32 = kk[start..end].iter().map(|v| v * v).sum::<f32>().sqrt().max(1e-12);
            for i in start..end {
                kk[i] /= norm;
            }
        }

        // k = k * (1 + (a_coeff - 1) * k_a)
        for i in 0..c {
            k[i] *= 1.0 + (a_coeff[i] - 1.0) * tm.k_a[i];
        }

        // ═══════════════════════════════════════════════════
        // STATE EVOLUTION — THE HEART OF RWKV (parallel across heads)
        // ═══════════════════════════════════════════════════
        // For T=1 (single token), this is one step of the RNN:
        //   state = state * decay + icl_term + vk
        //   output = state @ r
        //
        // Each head's state is an independent [n×n] matrix. Heads are
        // completely independent so we split and process in parallel.

        let mut output = vec![0.0_f32; c];

        // Somatic injection 4: Memory formation (computed once, shared)
        let state_push = 1.0 + (somatic.intensity - 0.5) * 0.4;

        let nn = n * n;
        let wkv_state = &mut state.wkv_states[layer_id];
        let state_chunks: Vec<&mut [f32]> = wkv_state.chunks_mut(nn).collect();
        let output_chunks: Vec<&mut [f32]> = output.chunks_mut(n).collect();

        state_chunks.into_par_iter()
            .zip(output_chunks.into_par_iter())
            .enumerate()
            .for_each(|(head, (head_state, head_output))| {
                let h_start = head * n;

                // Step 1: s_dot_kkt = head_state @ (-kk)
                let mut s_dot_kkt = vec![0.0_f32; n];
                for i in 0..n {
                    let mut sum = 0.0_f32;
                    for j in 0..n {
                        sum += head_state[i * n + j] * (-kk[h_start + j]);
                    }
                    s_dot_kkt[i] = sum;
                }

                // Step 2: kkt_at = kk * a_coeff
                let mut kkt_at = vec![0.0_f32; n];
                for j in 0..n {
                    kkt_at[j] = kk[h_start + j] * a_coeff[h_start + j];
                }

                // Step 3: icl_term = outer(s_dot_kkt, kkt_at)
                let mut icl_term = vec![0.0_f32; nn];
                for i in 0..n {
                    for j in 0..n {
                        icl_term[i * n + j] = s_dot_kkt[i] * kkt_at[j];
                    }
                }

                // Step 4: vk = outer(v, k) * state_push (fused)
                let mut vk = vec![0.0_f32; nn];
                for i in 0..n {
                    let vi = v[h_start + i] * state_push;
                    for j in 0..n {
                        vk[i * n + j] = vi * k[h_start + j];
                    }
                }

                // Step 5: state = state * decay + icl_term + vk
                for i in 0..n {
                    for j in 0..n {
                        let idx = i * n + j;
                        head_state[idx] = head_state[idx] * w[h_start + j]
                            + icl_term[idx] + vk[idx];
                    }
                }

                // Step 6: output = state @ r
                for i in 0..n {
                    let mut sum = 0.0_f32;
                    for j in 0..n {
                        sum += head_state[i * n + j] * r[h_start + j];
                    }
                    head_output[i] = sum;
                }
            });

        // --- GroupNorm (num_groups = n_head) ---
        group_norm(&mut output, h, n, &tm.ln_weight, &tm.ln_bias);

        // --- Residual term: (r * k * r_k).sum(-1, keepdim=True) * v ---
        let mut residual = vec![0.0_f32; c];
        for head in 0..h {
            let start = head * n;
            let mut rksum = 0.0_f32;
            for i in 0..n {
                rksum += r[start + i] * k[start + i] * tm.r_k[start + i];
            }
            for i in 0..n {
                residual[start + i] = rksum * v[start + i];
            }
        }
        for i in 0..c {
            output[i] += residual[i];
        }

        // --- Gate and output projection ---
        for i in 0..c {
            output[i] *= g[i];
        }

        // Somatic injection 5: Output gate scale
        let out_scale = 0.7 + somatic.confidence * 0.6;
        for i in 0..c {
            output[i] *= out_scale;
        }

        // Output projection: output @ tm.output
        let mut projected = vec![0.0_f32; c];
        matmul_vec(&output, &tm.output, &mut projected, c, c);

        (projected, receptance_mean)
    }

    /// ChannelMix forward pass (feed-forward with squared ReLU).
    fn channel_mix_forward(
        &self,
        x: &[f32],
        layer_id: usize,
        layer: &LayerWeights,
        state: &mut RWKVState,
        somatic: &SomaticState,
    ) -> Vec<f32> {
        let c = self.config.n_embd;
        let n_ff = self.config.n_ff();
        let cm = &layer.channel_mix;

        // Token shifting (key only) — NO sigmoid on lerp weight
        // Matches llama.cpp: xk = cur + sx * lerp_k (direct multiply)
        let x_prev = &state.ffn_shifts[layer_id];
        let mut xk = vec![0.0_f32; c];
        for i in 0..c {
            let xx = x_prev[i] - x[i];
            xk[i] = x[i] + xx * cm.lerp_k[i];
        }

        // Save current x for next token's ffn_shift
        state.ffn_shifts[layer_id] = x.to_vec();

        // key = relu(xk @ cm.key) ^ 2  — squared ReLU
        let mut key_out = vec![0.0_f32; n_ff];
        matmul_vec(&xk, &cm.key, &mut key_out, c, n_ff);

        for val in &mut key_out {
            *val = val.max(0.0); // ReLU
            *val = *val * *val;  // Square
        }

        // value = key_out @ cm.value
        let mut output = vec![0.0_f32; c];
        matmul_vec(&key_out, &cm.value, &mut output, n_ff, c);

        // Somatic: output gate scale
        let out_scale = 0.7 + somatic.confidence * 0.6;
        for val in &mut output {
            *val *= out_scale;
        }

        output
    }
}

// ============================================================================
// Math primitives
// ============================================================================

/// Matrix-vector multiply: y = x @ M where x is [K], M is [K, N], y is [N].
///
/// GGUF LAYOUT (verified 2026-02-17):
///   GGUF ne[0] = innermost/fastest dimension (= columns in C-order)
///   For a weight with ne=(in_dim, out_dim), the flat data is stored as
///   [out_dim, in_dim] in row-major order: data[out * in_dim + in].
///   This matches PyTorch's nn.Linear [out_features, in_features] convention.
///
///   For matmul y = x @ W where x=[K=in_dim], we need W as [K, N=out_dim].
///   Since GGUF stores [N, K], we read the TRANSPOSE: M_logical[i, j] = M_physical[j * K + i].
///   This avoids copying data — just changes the access pattern.
///
///   LoRA weights also use matmul_vec — they follow the SAME [N, K] convention.
///   (matmul_vec_direct is defined but UNUSED — kept for reference.)
#[inline]
fn matmul_vec(x: &[f32], m: &[f32], y: &mut [f32], k: usize, n: usize) {
    assert!(
        m.len() >= k * n,
        "matmul_vec: m.len()={} but need k*n={} (k={}, n={})",
        m.len(), k * n, k, n
    );

    // y[j] = dot(x, m[j*k .. j*k+k])
    // GGUF layout: physical [N, K] → logical transpose: col j = m[j*k .. j*k+k]
    //
    // This is N independent dot products of length K.
    // With target-cpu=native, the inner dot product auto-vectorizes to AVX2/FMA:
    //   8 f32 per cycle × FMA = 16 FLOP/cycle
    //   At 3.5 GHz: ~56 GFLOP/s single-core (vs ~4 GFLOP/s without SIMD)

    // With target-cpu=native (AVX2+FMA), the inner dot product auto-vectorizes.
    //
    // Rayon ONLY for very large matmuls (head projection: n=65536).
    // For medium matmuls (n=2048), rayon overhead (~3-5μs per spawn) per
    // 192 parallel regions/token dominates the compute.
    if n >= 8192 {
        use rayon::prelude::*;
        let chunk_size = (n / rayon::current_num_threads()).max(256);
        y.par_chunks_mut(chunk_size).enumerate().for_each(|(chunk_idx, y_chunk)| {
            let base_j = chunk_idx * chunk_size;
            for (local_j, yj) in y_chunk.iter_mut().enumerate() {
                let j = base_j + local_j;
                let row = &m[j * k .. j * k + k];
                let mut acc = 0.0f32;
                for i in 0..k {
                    acc += x[i] * row[i];
                }
                *yj = acc;
            }
        });
    } else {
        for j in 0..n {
            let row = &m[j * k .. j * k + k];
            let mut acc = 0.0f32;
            for i in 0..k {
                acc += x[i] * row[i];
            }
            y[j] = acc;
        }
    }
}

/// UNUSED — kept for reference. Direct (non-transposing) matrix-vector multiply.
/// This was tested but GGUF LoRA weights follow the same [N, K] convention
/// as regular weights, so matmul_vec (with transpose read) is correct for all.
#[allow(dead_code)]
#[inline]
fn matmul_vec_direct(x: &[f32], m: &[f32], y: &mut [f32], k: usize, n: usize) {
    assert!(
        m.len() >= k * n,
        "matmul_vec_direct: m.len()={} but need k*n={} (k={}, n={})",
        m.len(), k * n, k, n
    );
    y.iter_mut().for_each(|v| *v = 0.0);
    for i in 0..k {
        let xi = x[i];
        if xi == 0.0 { continue; }
        let row_offset = i * n;
        for j in 0..n {
            y[j] += xi * m[row_offset + j];
        }
    }
}

/// LayerNorm: x = (x - mean) / sqrt(var + eps) * weight + bias
#[inline]
fn layer_norm(x: &mut [f32], weight: &[f32], bias: &[f32]) {
    let n = x.len() as f32;
    let eps = 1e-5_f32;

    let mean = x.iter().sum::<f32>() / n;
    let var = x.iter().map(|v| (v - mean) * (v - mean)).sum::<f32>() / n;
    let inv_std = 1.0 / (var + eps).sqrt();

    for i in 0..x.len() {
        x[i] = (x[i] - mean) * inv_std * weight[i] + bias[i];
    }
}

/// GroupNorm: normalize within each group (head).
/// Input: [H * N], groups = H, each group = N elements.
#[inline]
fn group_norm(x: &mut [f32], num_groups: usize, group_size: usize, weight: &[f32], bias: &[f32]) {
    let eps = 64e-5_f32; // RWKV uses 64e-5 for GroupNorm

    for g in 0..num_groups {
        let start = g * group_size;
        let end = start + group_size;
        let slice = &x[start..end];

        let mean = slice.iter().sum::<f32>() / group_size as f32;
        let var = slice.iter().map(|v| (v - mean) * (v - mean)).sum::<f32>() / group_size as f32;
        let inv_std = 1.0 / (var + eps).sqrt();

        for i in start..end {
            x[i] = (x[i] - mean) * inv_std * weight[i] + bias[i];
        }
    }
}

/// Sigmoid activation: 1 / (1 + exp(-x))
#[inline]
fn sigmoid(x: f32) -> f32 {
    1.0 / (1.0 + (-x).exp())
}
