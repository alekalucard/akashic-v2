//! GGUF file parser — reads GGUF model files directly from Rust.
//!
//! Replaces the Python gguf_parser.py + quantization.py pipeline that takes
//! ~430 seconds. Rust + mmap + rayon parallel dequant → ~20-40 seconds.
//!
//! GGUF spec: https://github.com/ggerganov/ggml/blob/master/docs/gguf.md

use std::collections::HashMap;
use std::path::Path;
use memmap2::Mmap;
use byteorder::{LittleEndian, ByteOrder};
use rayon::prelude::*;

use crate::quantization;

// ============================================================================
// Constants
// ============================================================================

const GGUF_MAGIC: u32 = 0x46554747; // "GGUF" little-endian
const DEFAULT_ALIGNMENT: usize = 32;

// GGML quantization type IDs
const GGML_TYPE_F32: u32 = 0;
const GGML_TYPE_F16: u32 = 1;
const GGML_TYPE_Q4_0: u32 = 2;
const GGML_TYPE_Q8_0: u32 = 8;
const GGML_TYPE_Q4_K: u32 = 12;
const GGML_TYPE_Q6_K: u32 = 14;
const GGML_TYPE_BF16: u32 = 30;

// GGUF metadata value types
const GGUF_TYPE_UINT8: u32 = 0;
const GGUF_TYPE_INT8: u32 = 1;
const GGUF_TYPE_UINT16: u32 = 2;
const GGUF_TYPE_INT16: u32 = 3;
const GGUF_TYPE_UINT32: u32 = 4;
const GGUF_TYPE_INT32: u32 = 5;
const GGUF_TYPE_FLOAT32: u32 = 6;
const GGUF_TYPE_BOOL: u32 = 7;
const GGUF_TYPE_STRING: u32 = 8;
const GGUF_TYPE_ARRAY: u32 = 9;
const GGUF_TYPE_UINT64: u32 = 10;
const GGUF_TYPE_INT64: u32 = 11;
const GGUF_TYPE_FLOAT64: u32 = 12;

// ============================================================================
// Data structures
// ============================================================================

/// Parsed model configuration from GGUF metadata.
#[derive(Debug, Clone, Default)]
pub struct GGUFConfig {
    pub architecture: String,
    pub n_layer: usize,
    pub n_embd: usize,
    pub n_head: usize,
    pub head_size: usize,
    pub vocab_size: usize,
}

/// Information about one tensor in the file.
#[derive(Debug, Clone)]
pub struct TensorInfo {
    pub name: String,
    pub shape: Vec<usize>,
    pub type_id: u32,
    pub offset: usize,        // Byte offset within data section
    pub n_elements: usize,
    pub size_bytes: usize,    // Size of raw (quantized) data
}

/// A parsed GGUF file, memory-mapped for fast access.
pub struct GGUFReader {
    mmap: Mmap,
    pub config: GGUFConfig,
    pub tensors: Vec<TensorInfo>,
    tensor_map: HashMap<String, usize>,  // name → index in tensors
    data_offset: usize,                   // Start of tensor data section
}

// ============================================================================
// Cursor — lightweight reader over the mmap
// ============================================================================

struct Cursor<'a> {
    data: &'a [u8],
    pos: usize,
}

impl<'a> Cursor<'a> {
    fn new(data: &'a [u8]) -> Self {
        Cursor { data, pos: 0 }
    }

    fn remaining(&self) -> usize {
        self.data.len().saturating_sub(self.pos)
    }

    fn read_u8(&mut self) -> u8 {
        let v = self.data[self.pos];
        self.pos += 1;
        v
    }

    fn read_u16(&mut self) -> u16 {
        let v = LittleEndian::read_u16(&self.data[self.pos..]);
        self.pos += 2;
        v
    }

    fn read_u32(&mut self) -> u32 {
        let v = LittleEndian::read_u32(&self.data[self.pos..]);
        self.pos += 4;
        v
    }

    fn read_u64(&mut self) -> u64 {
        let v = LittleEndian::read_u64(&self.data[self.pos..]);
        self.pos += 8;
        v
    }

    fn read_i32(&mut self) -> i32 {
        let v = LittleEndian::read_i32(&self.data[self.pos..]);
        self.pos += 4;
        v
    }

    fn read_f32(&mut self) -> f32 {
        let v = LittleEndian::read_f32(&self.data[self.pos..]);
        self.pos += 4;
        v
    }

    fn read_f64(&mut self) -> f64 {
        let v = LittleEndian::read_f64(&self.data[self.pos..]);
        self.pos += 8;
        v
    }

    fn read_string(&mut self) -> String {
        let len = self.read_u64() as usize;
        let s = std::str::from_utf8(&self.data[self.pos..self.pos + len])
            .unwrap_or("<invalid utf8>")
            .to_string();
        self.pos += len;
        s
    }

    fn read_bool(&mut self) -> bool {
        let v = self.data[self.pos] != 0;
        self.pos += 1;
        v
    }

    /// Skip a metadata value (for fields we don't care about).
    fn skip_value(&mut self, vtype: u32) {
        match vtype {
            GGUF_TYPE_UINT8 | GGUF_TYPE_INT8 | GGUF_TYPE_BOOL => { self.pos += 1; }
            GGUF_TYPE_UINT16 | GGUF_TYPE_INT16 => { self.pos += 2; }
            GGUF_TYPE_UINT32 | GGUF_TYPE_INT32 | GGUF_TYPE_FLOAT32 => { self.pos += 4; }
            GGUF_TYPE_UINT64 | GGUF_TYPE_INT64 | GGUF_TYPE_FLOAT64 => { self.pos += 8; }
            GGUF_TYPE_STRING => { let _ = self.read_string(); }
            GGUF_TYPE_ARRAY => {
                let elem_type = self.read_u32();
                let count = self.read_u64() as usize;
                for _ in 0..count {
                    self.skip_value(elem_type);
                }
            }
            _ => { /* unknown type — pray it's zero-length */ }
        }
    }

    /// Read a metadata value as i64 (for integer-like types).
    fn read_value_as_i64(&mut self, vtype: u32) -> i64 {
        match vtype {
            GGUF_TYPE_UINT8 => self.read_u8() as i64,
            GGUF_TYPE_INT8 => self.read_u8() as i8 as i64,
            GGUF_TYPE_UINT16 => self.read_u16() as i64,
            GGUF_TYPE_INT16 => self.read_u16() as i16 as i64,
            GGUF_TYPE_UINT32 => self.read_u32() as i64,
            GGUF_TYPE_INT32 => self.read_i32() as i64,
            GGUF_TYPE_UINT64 => self.read_u64() as i64,
            GGUF_TYPE_INT64 => self.read_u64() as i64,
            GGUF_TYPE_FLOAT32 => self.read_f32() as i64,
            GGUF_TYPE_FLOAT64 => self.read_f64() as i64,
            GGUF_TYPE_BOOL => if self.read_bool() { 1 } else { 0 },
            _ => { self.skip_value(vtype); 0 }
        }
    }

    /// Read a metadata value as String.
    fn read_value_as_string(&mut self, vtype: u32) -> String {
        if vtype == GGUF_TYPE_STRING {
            self.read_string()
        } else {
            let v = self.read_value_as_i64(vtype);
            v.to_string()
        }
    }

    fn slice(&self, offset: usize, len: usize) -> &'a [u8] {
        &self.data[offset..offset + len]
    }
}

// ============================================================================
// Quantization helpers (size calculation)
// ============================================================================

fn tensor_byte_size(type_id: u32, n_elements: usize) -> usize {
    match type_id {
        GGML_TYPE_F32 => n_elements * 4,
        GGML_TYPE_F16 | GGML_TYPE_BF16 => n_elements * 2,
        GGML_TYPE_Q8_0 => {
            let blocks = (n_elements + 31) / 32;
            blocks * 34
        }
        GGML_TYPE_Q4_0 => {
            let blocks = (n_elements + 31) / 32;
            blocks * 18
        }
        GGML_TYPE_Q4_K => {
            let blocks = (n_elements + 255) / 256;
            blocks * 144
        }
        GGML_TYPE_Q6_K => {
            let blocks = (n_elements + 255) / 256;
            blocks * 210
        }
        _ => n_elements * 4, // assume F32 for unknown
    }
}

/// Dequantize raw bytes to f32 based on type_id.
/// Dispatches to the appropriate dequantizer in quantization.rs.
pub fn dequantize(data: &[u8], type_id: u32, n_elements: usize) -> Vec<f32> {
    match type_id {
        GGML_TYPE_F32 => {
            // Direct reinterpret — 4 bytes per f32, little-endian
            let mut result = vec![0.0f32; n_elements];
            for i in 0..n_elements {
                result[i] = LittleEndian::read_f32(&data[i * 4..]);
            }
            result
        }
        GGML_TYPE_F16 => {
            // f16 → f32 conversion
            let mut result = vec![0.0f32; n_elements];
            for i in 0..n_elements {
                let bits = LittleEndian::read_u16(&data[i * 2..]);
                result[i] = quantization::f16_to_f32_pub(bits);
            }
            result
        }
        GGML_TYPE_BF16 => {
            // bf16 → f32: just shift upper 16 bits
            let mut result = vec![0.0f32; n_elements];
            for i in 0..n_elements {
                let bits = LittleEndian::read_u16(&data[i * 2..]) as u32;
                result[i] = f32::from_bits(bits << 16);
            }
            result
        }
        GGML_TYPE_Q8_0 => quantization::dequantize_q8_0(data, n_elements),
        GGML_TYPE_Q4_0 => quantization::dequantize_q4_0(data, n_elements),
        GGML_TYPE_Q4_K => quantization::dequantize_q4_k(data, n_elements),
        GGML_TYPE_Q6_K => quantization::dequantize_q6_k(data, n_elements),
        _ => {
            println!("[GGUF] Warning: unknown quant type {} — treating as F32", type_id);
            let mut result = vec![0.0f32; n_elements];
            let count = std::cmp::min(n_elements, data.len() / 4);
            for i in 0..count {
                result[i] = LittleEndian::read_f32(&data[i * 4..]);
            }
            result
        }
    }
}

// ============================================================================
// GGUFReader implementation
// ============================================================================

impl GGUFReader {
    /// Open and parse a GGUF file (memory-mapped).
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self, String> {
        let path = path.as_ref();
        let file = std::fs::File::open(path)
            .map_err(|e| format!("Cannot open {}: {}", path.display(), e))?;

        let mmap = unsafe { Mmap::map(&file) }
            .map_err(|e| format!("Cannot mmap {}: {}", path.display(), e))?;

        if mmap.len() < 16 {
            return Err("File too small to be GGUF".to_string());
        }

        let mut cur = Cursor::new(&mmap);

        // ── Header ──
        let magic = cur.read_u32();
        if magic != GGUF_MAGIC {
            return Err(format!("Invalid GGUF magic: {:#x} (expected {:#x})", magic, GGUF_MAGIC));
        }
        let version = cur.read_u32();
        if version < 2 || version > 3 {
            return Err(format!("Unsupported GGUF version: {}", version));
        }

        let n_tensors = cur.read_u64() as usize;
        let n_kv = cur.read_u64() as usize;

        println!("[GGUF/Rust] Parsing {} (v{}, {} tensors, {} kv)",
            path.file_name().unwrap_or_default().to_string_lossy(),
            version, n_tensors, n_kv);

        // ── Metadata ──
        let mut config = GGUFConfig::default();
        let mut alignment = DEFAULT_ALIGNMENT;

        for _ in 0..n_kv {
            let key = cur.read_string();
            let vtype = cur.read_u32();

            // Extract the fields we need, skip the rest
            match key.as_str() {
                "general.architecture" => {
                    config.architecture = cur.read_value_as_string(vtype);
                }
                "general.alignment" => {
                    alignment = cur.read_value_as_i64(vtype) as usize;
                }
                k if k.ends_with(".block_count") => {
                    config.n_layer = cur.read_value_as_i64(vtype) as usize;
                }
                k if k.ends_with(".embedding_length") => {
                    config.n_embd = cur.read_value_as_i64(vtype) as usize;
                }
                k if k.ends_with(".attention.head_count") => {
                    config.n_head = cur.read_value_as_i64(vtype) as usize;
                }
                k if k.ends_with(".wkv.head_size") => {
                    config.head_size = cur.read_value_as_i64(vtype) as usize;
                }
                k if k.ends_with(".vocab_size") || k == "tokenizer.ggml.tokens" => {
                    // vocab_size can come from metadata or token array length
                    if k.ends_with(".vocab_size") {
                        config.vocab_size = cur.read_value_as_i64(vtype) as usize;
                    } else {
                        // Array of tokens — count them
                        if vtype == GGUF_TYPE_ARRAY {
                            let _elem_type = cur.read_u32();
                            let count = cur.read_u64() as usize;
                            if config.vocab_size == 0 {
                                config.vocab_size = count;
                            }
                            // Skip the actual token strings
                            for _ in 0..count {
                                cur.skip_value(_elem_type);
                            }
                        } else {
                            cur.skip_value(vtype);
                        }
                    }
                }
                _ => {
                    cur.skip_value(vtype);
                }
            }
        }

        // RWKV: compute n_head from head_size if not set
        if config.n_head == 0 && config.head_size > 0 && config.n_embd > 0 {
            config.n_head = config.n_embd / config.head_size;
            println!("[GGUF/Rust] Computed n_head = {} / {} = {}",
                config.n_embd, config.head_size, config.n_head);
        }
        if config.head_size == 0 && config.n_head > 0 && config.n_embd > 0 {
            config.head_size = config.n_embd / config.n_head;
        }

        println!("[GGUF/Rust] Config: layers={} embd={} heads={} head_size={} vocab={}",
            config.n_layer, config.n_embd, config.n_head, config.head_size, config.vocab_size);

        // ── Tensor info section ──
        let mut tensors = Vec::with_capacity(n_tensors);
        let mut tensor_map = HashMap::with_capacity(n_tensors);

        for idx in 0..n_tensors {
            let name = cur.read_string();
            let n_dims = cur.read_u32() as usize;
            let mut shape = Vec::with_capacity(n_dims);
            for _ in 0..n_dims {
                shape.push(cur.read_u64() as usize);
            }
            let type_id = cur.read_u32();
            let offset = cur.read_u64() as usize;

            let n_elements: usize = shape.iter().product();
            let size_bytes = tensor_byte_size(type_id, n_elements);

            tensor_map.insert(name.clone(), idx);
            tensors.push(TensorInfo {
                name,
                shape,
                type_id,
                offset,
                n_elements,
                size_bytes,
            });
        }

        // ── Data section offset (aligned) ──
        let header_end = cur.pos;
        let data_offset = ((header_end + alignment - 1) / alignment) * alignment;

        println!("[GGUF/Rust] Parsed {} tensors, data starts at offset {}",
            tensors.len(), data_offset);

        Ok(GGUFReader {
            mmap,
            config,
            tensors,
            tensor_map,
            data_offset,
        })
    }

    /// Get raw bytes for a tensor (zero-copy from mmap).
    pub fn tensor_data(&self, info: &TensorInfo) -> &[u8] {
        let start = self.data_offset + info.offset;
        let end = start + info.size_bytes;
        &self.mmap[start..end]
    }

    /// Dequantize a single tensor to f32.
    pub fn dequantize_tensor(&self, info: &TensorInfo) -> Vec<f32> {
        let raw = self.tensor_data(info);
        dequantize(raw, info.type_id, info.n_elements)
    }

    /// Dequantize ALL tensors in parallel using rayon.
    /// Returns Vec<(name, f32_data)> in file order.
    pub fn dequantize_all_parallel(&self) -> Vec<(String, Vec<f32>)> {
        self.tensors.par_iter()
            .map(|info| {
                let data = self.dequantize_tensor(info);
                (info.name.clone(), data)
            })
            .collect()
    }

    /// Dequantize tensors in parallel, calling a callback for each result.
    /// This allows streaming into ModelWeights without collecting all at once.
    pub fn dequantize_streaming<F>(&self, mut callback: F)
    where
        F: FnMut(&str, Vec<f32>) + Send,
    {
        // Process in batches to limit peak RAM.
        // Each batch is dequantized in parallel, then fed to callback serially.
        const BATCH_SIZE: usize = 28; // One layer's worth of tensors

        for batch in self.tensors.chunks(BATCH_SIZE) {
            let results: Vec<(String, Vec<f32>)> = batch.par_iter()
                .map(|info| {
                    let data = self.dequantize_tensor(info);
                    (info.name.clone(), data)
                })
                .collect();

            for (name, data) in results {
                callback(&name, data);
            }
        }
    }

    /// Get a tensor by name.
    pub fn get_tensor_info(&self, name: &str) -> Option<&TensorInfo> {
        self.tensor_map.get(name).map(|&idx| &self.tensors[idx])
    }
}
