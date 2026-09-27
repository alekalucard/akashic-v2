//! Token sampling — temperature scaling and nucleus (top-p) sampling.
//!
//! After the forward pass produces logits, sampling selects the next token.
//! This matches the Python implementation exactly:
//!   1. Temperature scaling: logits / temperature
//!   2. Top-p filtering: keep tokens until cumulative prob > top_p
//!   3. Multinomial sampling from filtered distribution

use rand::Rng;
use std::collections::HashSet;

/// Sample a token from logits using temperature, top-p, and repetition penalty.
///
/// - temperature = 0.0: greedy (argmax)
/// - temperature > 0.0: scaled softmax + nucleus sampling
/// - top_p = 1.0: no filtering (full distribution)
/// - top_p < 1.0: nucleus sampling (keep top tokens summing to top_p)
/// - repetition_penalty > 1.0: penalize tokens that appeared in `recent_tokens`
///   (applied BEFORE temperature scaling, on raw logits)
/// - recent_tokens: token IDs generated so far (for repetition penalty)
pub fn sample_token(logits: &[f32], temperature: f32, top_p: f32) -> u32 {
    // No penalty version — delegates to full version with no recent tokens
    sample_token_with_penalty(logits, temperature, top_p, 1.0, &[])
}

/// Sample with repetition penalty.
///
/// The penalty is applied multiplicatively to logits of tokens in `recent_tokens`:
///   - If logit > 0: logit = logit / penalty  (makes positive logits less positive)
///   - If logit < 0: logit = logit * penalty  (makes negative logits more negative)
///
/// This is the standard HuggingFace-style repetition penalty.
/// A value of 1.2-1.5 works well for most models.
pub fn sample_token_with_penalty(
    logits: &[f32],
    temperature: f32,
    top_p: f32,
    repetition_penalty: f32,
    recent_tokens: &[u32],
) -> u32 {
    let vocab_size = logits.len();

    // ═══ STEP 0: Apply repetition penalty to raw logits ═══
    let penalized: Vec<f32> = if repetition_penalty > 1.0 + 1e-6 && !recent_tokens.is_empty() {
        let recent_set: HashSet<u32> = recent_tokens.iter().copied().collect();
        logits.iter().enumerate().map(|(i, &v)| {
            if recent_set.contains(&(i as u32)) {
                if v > 0.0 {
                    v / repetition_penalty
                } else {
                    v * repetition_penalty
                }
            } else {
                v
            }
        }).collect()
    } else {
        logits.to_vec()
    };

    // Greedy decoding
    if temperature <= 0.0 || temperature < 1e-6 {
        return argmax(&penalized) as u32;
    }

    // Temperature scaling
    let scaled: Vec<f32> = penalized.iter().map(|&v| v / temperature).collect();

    // Softmax
    let max_val = scaled.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
    let exp_vals: Vec<f32> = scaled.iter().map(|&v| (v - max_val).exp()).collect();
    let sum: f32 = exp_vals.iter().sum();
    let probs: Vec<f32> = exp_vals.iter().map(|&v| v / sum).collect();

    // Top-p (nucleus) filtering
    if top_p < 1.0 {
        // Sort by probability descending
        let mut indices: Vec<usize> = (0..vocab_size).collect();
        indices.sort_unstable_by(|&a, &b| probs[b].partial_cmp(&probs[a]).unwrap());

        // Find cutoff
        let mut cumsum = 0.0_f32;
        let mut cutoff_idx = vocab_size;
        for (rank, &idx) in indices.iter().enumerate() {
            cumsum += probs[idx];
            if cumsum > top_p {
                cutoff_idx = rank + 1; // Include this token
                break;
            }
        }

        // Build filtered distribution
        let kept_indices = &indices[..cutoff_idx.min(vocab_size)];
        let kept_probs: Vec<f32> = kept_indices.iter().map(|&i| probs[i]).collect();
        let kept_sum: f32 = kept_probs.iter().sum();
        let normalized: Vec<f32> = kept_probs.iter().map(|&p| p / kept_sum).collect();

        // Multinomial sample
        let selected_rank = multinomial_sample(&normalized);
        return kept_indices[selected_rank] as u32;
    }

    // Full distribution sampling
    multinomial_sample(&probs) as u32
}

/// Argmax: return index of maximum value.
#[inline]
fn argmax(x: &[f32]) -> usize {
    let mut max_idx = 0;
    let mut max_val = f32::NEG_INFINITY;
    for (i, &v) in x.iter().enumerate() {
        if v > max_val {
            max_val = v;
            max_idx = i;
        }
    }
    max_idx
}

/// Multinomial sampling from a probability distribution.
#[inline]
fn multinomial_sample(probs: &[f32]) -> usize {
    let mut rng = rand::thread_rng();
    let r: f32 = rng.gen();
    let mut cumsum = 0.0_f32;
    for (i, &p) in probs.iter().enumerate() {
        cumsum += p;
        if r < cumsum {
            return i;
        }
    }
    // Fallback to last token (rounding error)
    probs.len() - 1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_greedy_sampling() {
        let logits = vec![0.1, 0.5, 0.9, 0.2, 0.3];
        let token = sample_token(&logits, 0.0, 1.0);
        assert_eq!(token, 2); // Index of 0.9
    }

    #[test]
    fn test_temperature_doesnt_crash() {
        let logits = vec![0.0_f32; 65536];
        let token = sample_token(&logits, 0.9, 0.9);
        assert!(token < 65536);
    }

    #[test]
    fn test_top_p_reduces_candidates() {
        // With very skewed distribution and low top_p,
        // sampling should heavily favor the top token
        let mut logits = vec![-10.0_f32; 100];
        logits[42] = 10.0; // Dominant token
        let mut counts = [0u32; 100];
        for _ in 0..1000 {
            let token = sample_token(&logits, 1.0, 0.5);
            counts[token as usize] += 1;
        }
        // Token 42 should be selected most of the time
        assert!(counts[42] > 900);
    }
}
