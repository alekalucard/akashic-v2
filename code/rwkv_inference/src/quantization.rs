//! GGUF quantization — dequantize Q4_K_M and Q8_0 tensors.
//!
//! These match the Python implementations in quantization.py exactly.
//! Used when loading weights directly from GGUF in Rust (future optimization).
//! Currently, Python handles dequantization and passes f32 arrays to Rust.

/// Dequantize Q8_0 data: 32 weights per block, 34 bytes per block.
/// Block: [2 bytes f16 scale] [32 bytes int8 values]
pub fn dequantize_q8_0(data: &[u8], num_elements: usize) -> Vec<f32> {
    const BLOCK_SIZE: usize = 32;
    const BYTES_PER_BLOCK: usize = 34;

    let num_blocks = (num_elements + BLOCK_SIZE - 1) / BLOCK_SIZE;
    let mut result = vec![0.0_f32; num_blocks * BLOCK_SIZE];

    for block_idx in 0..num_blocks {
        let offset = block_idx * BYTES_PER_BLOCK;
        if offset + BYTES_PER_BLOCK > data.len() {
            break;
        }

        // Read f16 scale
        let scale_bytes = [data[offset], data[offset + 1]];
        let scale = f16_to_f32(u16::from_le_bytes(scale_bytes));

        // Read int8 values and dequantize
        let start = block_idx * BLOCK_SIZE;
        for i in 0..BLOCK_SIZE {
            let qi = data[offset + 2 + i] as i8;
            result[start + i] = qi as f32 * scale;
        }
    }

    result.truncate(num_elements);
    result
}

/// Dequantize Q4_K data: 256 weights per super-block, 144 bytes per super-block.
///
/// Super-block structure:
///   [0:2]    fp16 super-scale (d)
///   [2:4]    fp16 super-min (dmin)
///   [4:16]   12 bytes: 6-bit scales for 8 sub-blocks
///   [16:144] 128 bytes: packed 4-bit quantized values
pub fn dequantize_q4_k(data: &[u8], num_elements: usize) -> Vec<f32> {
    const SUPER_BLOCK_SIZE: usize = 256;
    const BYTES_PER_SUPER_BLOCK: usize = 144;
    const SUB_BLOCK_SIZE: usize = 32;
    const NUM_SUB_BLOCKS: usize = 8;

    let num_super_blocks = (num_elements + SUPER_BLOCK_SIZE - 1) / SUPER_BLOCK_SIZE;
    let mut result = vec![0.0_f32; num_super_blocks * SUPER_BLOCK_SIZE];

    for sb_idx in 0..num_super_blocks {
        let offset = sb_idx * BYTES_PER_SUPER_BLOCK;
        if offset + BYTES_PER_SUPER_BLOCK > data.len() {
            break;
        }

        // Read super-scale and super-min (fp16)
        let d = f16_to_f32(u16::from_le_bytes([data[offset], data[offset + 1]]));
        let dmin = f16_to_f32(u16::from_le_bytes([data[offset + 2], data[offset + 3]]));

        // Unpack 6-bit scales and mins from 12 bytes
        let scale_bytes = &data[offset + 4..offset + 16];
        let (scales, mins) = unpack_6bit_scales(scale_bytes);

        // Read packed 4-bit values
        let qs_data = &data[offset + 16..offset + 144];

        // Dequantize each sub-block
        let sb_start = sb_idx * SUPER_BLOCK_SIZE;
        for sub_idx in 0..NUM_SUB_BLOCKS {
            let scale = d * scales[sub_idx] as f32;
            let m = dmin * mins[sub_idx] as f32;
            let qs_offset = sub_idx * 16; // 16 bytes per sub-block (32 values packed 2-per-byte)

            for j in 0..16 {
                let byte = qs_data[qs_offset + j];
                let lo = (byte & 0x0F) as f32;
                let hi = ((byte >> 4) & 0x0F) as f32;

                let out_base = sb_start + sub_idx * SUB_BLOCK_SIZE;
                result[out_base + j] = lo * scale - m;
                result[out_base + j + 16] = hi * scale - m;
            }
        }
    }

    result.truncate(num_elements);
    result
}

/// Unpack 6-bit scales and mins from 12 bytes.
/// Returns (scales[8], mins[8]).
fn unpack_6bit_scales(data: &[u8]) -> ([u8; 8], [u8; 8]) {
    let mut scales = [0u8; 8];
    let mut mins = [0u8; 8];

    // First 4 sub-blocks: scales and mins from bytes 0-7
    for i in 0..4 {
        scales[i] = data[i * 2] & 0x3F;
        mins[i] = data[i * 2 + 1] & 0x3F;
    }

    // Last 4 sub-blocks: use high bits from bytes 0-7 and bytes 8-11
    for i in 0..4 {
        let hi_scale = ((data[i * 2] >> 6) & 0x03) as u8;
        let hi_min = ((data[i * 2 + 1] >> 6) & 0x03) as u8;
        scales[4 + i] = (data[8 + i] & 0x0F) | (hi_scale << 4);
        mins[4 + i] = ((data[8 + i] >> 4) & 0x0F) | (hi_min << 4);
    }

    (scales, mins)
}

/// Public wrapper for f16_to_f32 — used by gguf.rs for F16 tensor dequant.
#[inline]
pub fn f16_to_f32_pub(bits: u16) -> f32 {
    f16_to_f32(bits)
}

/// Dequantize Q4_0 data: 32 weights per block, 18 bytes per block.
/// Block: [2 bytes f16 scale] [16 bytes packed 4-bit values]
pub fn dequantize_q4_0(data: &[u8], num_elements: usize) -> Vec<f32> {
    const BLOCK_SIZE: usize = 32;
    const BYTES_PER_BLOCK: usize = 18;

    let num_blocks = (num_elements + BLOCK_SIZE - 1) / BLOCK_SIZE;
    let mut result = vec![0.0_f32; num_blocks * BLOCK_SIZE];

    for block_idx in 0..num_blocks {
        let offset = block_idx * BYTES_PER_BLOCK;
        if offset + BYTES_PER_BLOCK > data.len() {
            break;
        }

        // Read f16 scale
        let scale = f16_to_f32(u16::from_le_bytes([data[offset], data[offset + 1]]));

        // Read packed 4-bit values and dequantize
        let start = block_idx * BLOCK_SIZE;
        for j in 0..16 {
            let byte = data[offset + 2 + j];
            let lo = (byte & 0x0F) as i32 - 8;  // Q4_0: unsigned nibble minus 8
            let hi = ((byte >> 4) & 0x0F) as i32 - 8;
            result[start + j] = lo as f32 * scale;
            result[start + j + 16] = hi as f32 * scale;
        }
    }

    result.truncate(num_elements);
    result
}

/// Dequantize Q6_K data: 256 weights per super-block, 210 bytes per super-block.
///
/// Super-block structure:
///   [0:128]  ql — lower 4 bits of quantized values (128 bytes)
///   [128:192] qh — upper 2 bits packed (64 bytes)
///   [192:208] scales — 6-bit scales for 16 sub-groups (16 bytes, int8)
///   [208:210] fp16 super-scale (d)
pub fn dequantize_q6_k(data: &[u8], num_elements: usize) -> Vec<f32> {
    const SUPER_BLOCK_SIZE: usize = 256;
    const BYTES_PER_SUPER_BLOCK: usize = 210;

    let num_super_blocks = (num_elements + SUPER_BLOCK_SIZE - 1) / SUPER_BLOCK_SIZE;
    let mut result = vec![0.0_f32; num_super_blocks * SUPER_BLOCK_SIZE];

    for sb_idx in 0..num_super_blocks {
        let offset = sb_idx * BYTES_PER_SUPER_BLOCK;
        if offset + BYTES_PER_SUPER_BLOCK > data.len() {
            break;
        }

        let ql = &data[offset..offset + 128];
        let qh = &data[offset + 128..offset + 192];
        let scales_raw = &data[offset + 192..offset + 208];
        let d = f16_to_f32(u16::from_le_bytes([data[offset + 208], data[offset + 209]]));

        let sb_start = sb_idx * SUPER_BLOCK_SIZE;

        // Decode all 256 values
        for i in 0..256 {
            // Lower 4 bits from ql
            let ql_byte_idx = i / 2;
            let ql_nibble = if i % 2 == 0 {
                (ql[ql_byte_idx] & 0x0F) as i32
            } else {
                ((ql[ql_byte_idx] >> 4) & 0x0F) as i32
            };

            // Upper 2 bits from qh
            let qh_byte_idx = i / 4;
            let qh_shift = (i % 4) * 2;
            let qh_bits = ((qh[qh_byte_idx] >> qh_shift) & 0x03) as i32;

            // Full 6-bit quantized value (unsigned, needs centering)
            let q = ql_nibble | (qh_bits << 4);

            // Scale from per-sub-group scale
            let scale_idx = i / 16; // 16 sub-groups of 16 values
            let sc = scales_raw[scale_idx] as i8 as f32;

            result[sb_start + i] = d * sc * (q as f32 - 32.0);
        }
    }

    result.truncate(num_elements);
    result
}

/// Convert IEEE 754 half-precision float (f16) to f32.
#[inline]
fn f16_to_f32(bits: u16) -> f32 {
    let sign = ((bits >> 15) & 1) as u32;
    let exp = ((bits >> 10) & 0x1F) as u32;
    let mant = (bits & 0x3FF) as u32;

    if exp == 0 {
        if mant == 0 {
            // Zero
            return f32::from_bits(sign << 31);
        }
        // Subnormal
        let mut m = mant;
        let mut e = 0i32;
        loop {
            e -= 1;
            m <<= 1;
            if m & 0x400 != 0 { break; }
        }
        m &= 0x3FF;
        let f32_exp = (127 - 15 + 1 + e) as u32;
        return f32::from_bits((sign << 31) | (f32_exp << 23) | (m << 13));
    }

    if exp == 31 {
        if mant == 0 {
            // Infinity
            return f32::from_bits((sign << 31) | (0xFF << 23));
        }
        // NaN
        return f32::from_bits((sign << 31) | (0xFF << 23) | (mant << 13));
    }

    // Normal number
    let f32_exp = (exp as i32 - 15 + 127) as u32;
    f32::from_bits((sign << 31) | (f32_exp << 23) | (mant << 13))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_f16_to_f32() {
        // 1.0 in f16 = 0x3C00
        assert!((f16_to_f32(0x3C00) - 1.0).abs() < 1e-6);
        // -1.0 in f16 = 0xBC00
        assert!((f16_to_f32(0xBC00) - (-1.0)).abs() < 1e-6);
        // 0.0 in f16 = 0x0000
        assert_eq!(f16_to_f32(0x0000), 0.0);
        // 0.5 in f16 = 0x3800
        assert!((f16_to_f32(0x3800) - 0.5).abs() < 1e-6);
    }
}
