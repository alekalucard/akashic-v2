//! RWKV-7 model structures — weights, state, and configuration.
//!
//! The RWKV state is an NxN matrix per head per layer that evolves with each token.
//! This is what makes RWKV an RNN: constant memory regardless of sequence length.

use std::collections::HashMap;

/// Model configuration matching the Python RWKVConfig.
#[derive(Debug, Clone)]
pub struct RWKVConfig {
    pub n_layer: usize,    // 24 for 1.5B
    pub n_embd: usize,     // 2048
    pub n_head: usize,     // 32
    pub head_size: usize,  // 64 (n_embd / n_head)
    pub vocab_size: usize, // 65536
}

impl RWKVConfig {
    pub fn n_ff(&self) -> usize {
        // Feed-forward hidden dim is 4x embedding dim
        self.n_embd * 4
    }
}

/// Per-layer TimeMix weights.
#[derive(Debug, Clone)]
pub struct TimeMixWeights {
    // Main projections [C, C] = [2048, 2048]
    pub receptance: Vec<f32>,  // [C, C]
    pub key: Vec<f32>,         // [C, C]
    pub value: Vec<f32>,       // [C, C]
    pub output: Vec<f32>,      // [C, C]

    // Time decay LoRA
    pub w0: Vec<f32>,          // [C]         base decay
    pub w1: Vec<f32>,          // [C, 64]     decay LoRA down
    pub w2: Vec<f32>,          // [64, C]     decay LoRA up

    // Association LoRA
    pub a0: Vec<f32>,          // [C]         base association
    pub a1: Vec<f32>,          // [C, 64]     association LoRA down
    pub a2: Vec<f32>,          // [64, C]     association LoRA up

    // Value bonus LoRA
    pub v0: Vec<f32>,          // [C]         base v-bonus
    pub v1: Vec<f32>,          // [C, 32]     v-bonus LoRA down
    pub v2: Vec<f32>,          // [32, C]     v-bonus LoRA up

    // Gate LoRA
    pub g1: Vec<f32>,          // [C, 128]    gate LoRA down
    pub g2: Vec<f32>,          // [128, C]    gate LoRA up

    // Scaling vectors
    pub k_k: Vec<f32>,         // [C]         key scaling
    pub k_a: Vec<f32>,         // [C]         key association
    pub r_k: Vec<f32>,         // [C]         receptance-key residual

    // GroupNorm parameters
    pub ln_weight: Vec<f32>,   // [C]
    pub ln_bias: Vec<f32>,     // [C]

    // Token shift lerp — fused [C, 6] (r, w, k, v, a, g lerp ratios)
    pub lerp_fused: Vec<f32>,  // [C * 6]
}

/// Per-layer ChannelMix weights.
#[derive(Debug, Clone)]
pub struct ChannelMixWeights {
    pub key: Vec<f32>,          // [C, 4*C] = [2048, 8192]
    pub value: Vec<f32>,        // [4*C, C] = [8192, 2048]
    pub lerp_k: Vec<f32>,      // [C]
}

/// Per-layer norm weights.
#[derive(Debug, Clone)]
pub struct LayerNormWeights {
    pub weight: Vec<f32>,  // [C]
    pub bias: Vec<f32>,    // [C]
}

/// All weights for one RWKV block (layer).
#[derive(Debug, Clone)]
pub struct LayerWeights {
    pub ln1: LayerNormWeights,      // Before TimeMix
    pub ln2: LayerNormWeights,      // Before ChannelMix
    pub time_mix: TimeMixWeights,
    pub channel_mix: ChannelMixWeights,
}

/// Complete model weights.
pub struct ModelWeights {
    pub config: RWKVConfig,

    // Embedding
    pub emb_weight: Vec<f32>,       // [vocab_size, C]
    pub emb_ln_weight: Vec<f32>,    // [C]
    pub emb_ln_bias: Vec<f32>,      // [C]

    // Per-layer
    pub layers: Vec<LayerWeights>,

    // Output head
    pub head_weight: Vec<f32>,      // [C, vocab_size]
    pub head_ln_weight: Vec<f32>,   // [C]
    pub head_ln_bias: Vec<f32>,     // [C]

    // Raw tensor storage for lazy/incremental loading
    raw_tensors: HashMap<String, Vec<f32>>,
}

impl ModelWeights {
    pub fn new(config: &RWKVConfig) -> Self {
        let c = config.n_embd;
        let n_ff = config.n_ff();
        let v = config.vocab_size;

        // Pre-allocate layer weights with zeros
        let layers = (0..config.n_layer).map(|_| LayerWeights {
            ln1: LayerNormWeights {
                weight: vec![1.0; c],  // LayerNorm weight init to 1
                bias: vec![0.0; c],
            },
            ln2: LayerNormWeights {
                weight: vec![1.0; c],
                bias: vec![0.0; c],
            },
            time_mix: TimeMixWeights {
                receptance: vec![0.0; c * c],
                key: vec![0.0; c * c],
                value: vec![0.0; c * c],
                output: vec![0.0; c * c],
                w0: vec![0.0; c],
                w1: vec![0.0; c * 64],
                w2: vec![0.0; 64 * c],
                a0: vec![0.0; c],
                a1: vec![0.0; c * 64],
                a2: vec![0.0; 64 * c],
                v0: vec![0.0; c],
                v1: vec![0.0; c * 32],
                v2: vec![0.0; 32 * c],
                g1: vec![0.0; c * 128],
                g2: vec![0.0; 128 * c],
                k_k: vec![0.0; c],
                k_a: vec![0.0; c],
                r_k: vec![0.0; c],
                ln_weight: vec![1.0; c],
                ln_bias: vec![0.0; c],
                lerp_fused: vec![0.0; c * 6],
            },
            channel_mix: ChannelMixWeights {
                key: vec![0.0; c * n_ff],
                value: vec![0.0; n_ff * c],
                lerp_k: vec![0.0; c],
            },
        }).collect();

        ModelWeights {
            config: config.clone(),
            emb_weight: vec![0.0; v * c],
            emb_ln_weight: vec![1.0; c],
            emb_ln_bias: vec![0.0; c],
            layers,
            head_weight: vec![0.0; c * v],
            head_ln_weight: vec![1.0; c],
            head_ln_bias: vec![0.0; c],
            raw_tensors: HashMap::new(),
        }
    }

    /// Drop large weight matrices that have been uploaded to GPU.
    ///
    /// After `GpuContext::upload_weights()`, the following are on GPU and no longer
    /// needed on CPU: R/K/V/O projections, ChannelMix key/value, head projection.
    /// This frees ~5 GB of system RAM for a 1.5B model.
    ///
    /// Small vectors (LoRA, norms, lerps, embeddings) are kept because they're used
    /// by the CPU portion of the hybrid forward pass.
    ///
    /// Returns (matrices_dropped, bytes_freed).
    pub fn drop_large_matrices(&mut self) -> (usize, usize) {
        let mut count = 0usize;
        let mut bytes = 0usize;

        for layer in &mut self.layers {
            // TimeMix big projections [C, C] — already on GPU
            bytes += layer.time_mix.receptance.len() * 4;
            layer.time_mix.receptance = Vec::new();
            count += 1;

            bytes += layer.time_mix.key.len() * 4;
            layer.time_mix.key = Vec::new();
            count += 1;

            bytes += layer.time_mix.value.len() * 4;
            layer.time_mix.value = Vec::new();
            count += 1;

            bytes += layer.time_mix.output.len() * 4;
            layer.time_mix.output = Vec::new();
            count += 1;

            // ChannelMix big projections [C, 4C] and [4C, C] — already on GPU
            bytes += layer.channel_mix.key.len() * 4;
            layer.channel_mix.key = Vec::new();
            count += 1;

            bytes += layer.channel_mix.value.len() * 4;
            layer.channel_mix.value = Vec::new();
            count += 1;
        }

        // Head projection [C, V] — already on GPU
        bytes += self.head_weight.len() * 4;
        self.head_weight = Vec::new();
        count += 1;

        // Drop any raw tensors (debug storage)
        for (_, v) in self.raw_tensors.drain() {
            bytes += v.len() * 4;
            count += 1;
        }

        (count, bytes)
    }

    /// Set a tensor by its GGUF name. Maps names to the right struct field.
    pub fn set_tensor(&mut self, name: &str, data: Vec<f32>) -> Result<(), String> {
        // Token embedding
        if name == "token_embd.weight" {
            self.emb_weight = data;
            return Ok(());
        }
        if name == "token_embd_norm.weight" {
            self.emb_ln_weight = data;
            return Ok(());
        }
        if name == "token_embd_norm.bias" {
            self.emb_ln_bias = data;
            return Ok(());
        }

        // Output head
        if name == "output.weight" {
            self.head_weight = data;
            return Ok(());
        }
        if name == "output_norm.weight" {
            self.head_ln_weight = data;
            return Ok(());
        }
        if name == "output_norm.bias" {
            self.head_ln_bias = data;
            return Ok(());
        }

        // Layer weights: blk.{N}.{component}
        if name.starts_with("blk.") {
            let parts: Vec<&str> = name.splitn(3, '.').collect();
            if parts.len() < 3 {
                return Err(format!("Invalid layer weight name: {}", name));
            }
            let layer_idx: usize = parts[1].parse()
                .map_err(|_| format!("Invalid layer index in: {}", name))?;
            if layer_idx >= self.config.n_layer {
                return Err(format!("Layer {} exceeds n_layer {}", layer_idx, self.config.n_layer));
            }
            let component = parts[2];
            let layer = &mut self.layers[layer_idx];

            match component {
                // LayerNorm 1 (before TimeMix)
                "attn_norm.weight" => layer.ln1.weight = data,
                "attn_norm.bias" => layer.ln1.bias = data,

                // LayerNorm 2 (before ChannelMix)
                "attn_norm_2.weight" | "ffn_norm.weight" => layer.ln2.weight = data,
                "attn_norm_2.bias" | "ffn_norm.bias" => layer.ln2.bias = data,

                // TimeMix core projections
                "time_mix_receptance.weight" => layer.time_mix.receptance = data,
                "time_mix_key.weight" => layer.time_mix.key = data,
                "time_mix_value.weight" => layer.time_mix.value = data,
                "time_mix_output.weight" => layer.time_mix.output = data,

                // Time decay LoRA
                "time_mix_w0.weight" | "time_mix_decay.weight" => layer.time_mix.w0 = data,
                "time_mix_w1.weight" | "time_mix_decay_w1.weight" => layer.time_mix.w1 = data,
                "time_mix_w2.weight" | "time_mix_decay_w2.weight" => layer.time_mix.w2 = data,

                // Association LoRA
                "time_mix_a0.weight" => layer.time_mix.a0 = data,
                "time_mix_a1.weight" => layer.time_mix.a1 = data,
                "time_mix_a2.weight" => layer.time_mix.a2 = data,

                // Value bonus LoRA
                "time_mix_v0.weight" => layer.time_mix.v0 = data,
                "time_mix_v1.weight" => layer.time_mix.v1 = data,
                "time_mix_v2.weight" => layer.time_mix.v2 = data,

                // Gate LoRA
                "time_mix_g1.weight" => layer.time_mix.g1 = data,
                "time_mix_g2.weight" => layer.time_mix.g2 = data,

                // Scaling vectors
                "time_mix_k_k.weight" => layer.time_mix.k_k = data,
                "time_mix_k_a.weight" => layer.time_mix.k_a = data,
                "time_mix_r_k.weight" => layer.time_mix.r_k = data,

                // TimeMix GroupNorm
                "time_mix_ln.weight" => layer.time_mix.ln_weight = data,
                "time_mix_ln.bias" => layer.time_mix.ln_bias = data,

                // Token shift lerp (fused)
                "time_mix_lerp_fused.weight" | "time_mix_x_maa.weight" => layer.time_mix.lerp_fused = data,

                // ChannelMix
                "channel_mix_key.weight" => layer.channel_mix.key = data,
                "channel_mix_value.weight" => layer.channel_mix.value = data,
                "channel_mix_lerp_k.weight" | "channel_mix_x_maa.weight" => layer.channel_mix.lerp_k = data,

                _ => {
                    // Store unknown tensors for debugging
                    self.raw_tensors.insert(name.to_string(), data);
                }
            }
            return Ok(());
        }

        // Unknown top-level tensor — store raw
        self.raw_tensors.insert(name.to_string(), data);
        Ok(())
    }
}

/// RWKV running state — persists across tokens.
///
/// Each layer has:
/// - wkv_state: [n_head, head_size, head_size] — the NxN state matrix
/// - att_shift: [n_embd] — last TimeMix input for token shifting
/// - ffn_shift: [n_embd] — last ChannelMix input for token shifting
pub struct RWKVState {
    pub wkv_states: Vec<Vec<f32>>,   // [n_layer][n_head * head_size * head_size]
    pub att_shifts: Vec<Vec<f32>>,   // [n_layer][n_embd]
    pub ffn_shifts: Vec<Vec<f32>>,   // [n_layer][n_embd]
    pub v_first: Option<Vec<f32>>,   // [n_embd] — from layer 0
    pub config: RWKVConfig,
}

impl RWKVState {
    pub fn new(config: &RWKVConfig) -> Self {
        let state_size = config.n_head * config.head_size * config.head_size;
        let c = config.n_embd;
        let n = config.n_layer;

        RWKVState {
            wkv_states: (0..n).map(|_| vec![0.0_f32; state_size]).collect(),
            att_shifts: (0..n).map(|_| vec![0.0_f32; c]).collect(),
            ffn_shifts: (0..n).map(|_| vec![0.0_f32; c]).collect(),
            v_first: None,
            config: config.clone(),
        }
    }

    /// Reset state to zeros (new conversation).
    pub fn reset(&mut self) {
        for s in &mut self.wkv_states {
            s.iter_mut().for_each(|v| *v = 0.0);
        }
        for s in &mut self.att_shifts {
            s.iter_mut().for_each(|v| *v = 0.0);
        }
        for s in &mut self.ffn_shifts {
            s.iter_mut().for_each(|v| *v = 0.0);
        }
        self.v_first = None;
    }
}
