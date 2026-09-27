/*
 * battery_matvec_fused.c -- AVX2 fused INT8 dequant + matvec + activation
 *                           + OpenMP multi-threading (v3)
 *
 * Replaces the Python tile loop in discharge_quantized_matvec with a single
 * vectorized C call.  Processes 8 int8 elements per SIMD instruction.
 *
 * OpenMP parallelism (v3):
 *   - quantized_matvec_fused: M rows distributed across threads (M=4096)
 *   - state_evolution_fused:  H heads distributed across threads (H=64)
 *   - groupnorm_fused:        num_groups distributed (32 groups)
 *   - Thread count controllable at runtime via battery_set_threads()
 *
 * Data layout (must match QuantizedTensor from quantized_weight_store.py):
 *   data:   [M, K_padded] int8,  row-major, K_padded = ceil(K/group_size)*group_size
 *   scales: [M, n_groups] float32, n_groups = K_padded / group_size
 *   x:      [K_padded] float32, zero-padded beyond K
 *   y:      [M] float32, output
 *
 * Dequant: float_val = int8_val * scale[row][col / group_size]
 *
 * Compile (MinGW-W64):
 *   gcc -O3 -march=skylake -mavx2 -mfma -fopenmp -shared -o battery_matvec_fused.dll battery_matvec_fused.c
 */

#include <immintrin.h>
#include <stdint.h>
#include <math.h>

#ifdef _OPENMP
  #include <omp.h>
#endif

#ifdef _WIN32
  #define EXPORT __declspec(dllexport)
#else
  #define EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Activation codes -- must match Python side */
#define ACT_NONE     0
#define ACT_SIGMOID  1
#define ACT_RELU_SQ  2
#define ACT_TANH     3

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/* Horizontal sum of 8 floats in a __m256 register */
static inline float hsum_avx(__m256 v) {
    __m128 hi  = _mm256_extractf128_ps(v, 1);
    __m128 lo  = _mm256_castps256_ps128(v);
    __m128 s   = _mm_add_ps(lo, hi);           /* 4 floats */
    __m128 shf = _mm_movehdup_ps(s);           /* [1,1,3,3] */
    __m128 sum = _mm_add_ps(s, shf);           /* [0+1, _, 2+3, _] */
    sum = _mm_add_ss(sum, _mm_movehl_ps(sum, sum));
    return _mm_cvtss_f32(sum);
}

/*
 * fast_exp_avx2 -- Cephes-style exp(x) for 8 floats
 *
 * Range reduction: exp(x) = 2^n * exp(r)
 *   n = round(x * log2(e))
 *   r = x - n * ln(2)           (two-part for precision)
 *   exp(r) via 7th-order minimax polynomial, |r| <= ln(2)/2
 *   2^n via integer exponent bit manipulation
 *
 * Accuracy: ~1e-6 relative error (sufficient for NN activations)
 */
static inline __m256 fast_exp_avx2(__m256 x) {
    /* Clamp to prevent overflow / underflow */
    x = _mm256_max_ps(x, _mm256_set1_ps(-88.0f));
    x = _mm256_min_ps(x, _mm256_set1_ps( 88.0f));

    /* n = round(x * log2(e)) */
    const __m256 LOG2E = _mm256_set1_ps(1.44269504088896341f);
    __m256 a = _mm256_mul_ps(x, LOG2E);
    __m256 n = _mm256_round_ps(a, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);

    /* r = x - n * ln(2), split for precision */
    const __m256 LN2_HI = _mm256_set1_ps(0.693145751953125f);
    const __m256 LN2_LO = _mm256_set1_ps(1.428606765330187e-06f);
    __m256 r = _mm256_sub_ps(x, _mm256_mul_ps(n, LN2_HI));
    r = _mm256_sub_ps(r, _mm256_mul_ps(n, LN2_LO));

    /* Minimax polynomial for exp(r), |r| <= ln(2)/2
     * Coefficients from Cephes single-precision library */
    __m256 p = _mm256_set1_ps(1.9875691500e-4f);
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.3981999507e-3f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(8.3334519073e-3f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(4.1665795894e-2f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.6666665459e-1f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(5.0000001201e-1f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.0f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.0f));

    /* 2^n: inject integer n into float exponent bits */
    __m256i ni = _mm256_cvtps_epi32(n);
    ni = _mm256_add_epi32(ni, _mm256_set1_epi32(127));   /* add IEEE bias */
    ni = _mm256_slli_epi32(ni, 23);                       /* shift to exponent */
    __m256 pow2n = _mm256_castsi256_ps(ni);

    return _mm256_mul_ps(p, pow2n);
}

/* sigmoid(x) = 1 / (1 + exp(-x)) */
static inline __m256 fast_sigmoid_avx2(__m256 x) {
    __m256 neg_x   = _mm256_sub_ps(_mm256_setzero_ps(), x);
    __m256 exp_neg = fast_exp_avx2(neg_x);
    __m256 one     = _mm256_set1_ps(1.0f);
    return _mm256_div_ps(one, _mm256_add_ps(one, exp_neg));
}

/* ------------------------------------------------------------------ */
/*  Main kernel                                                        */
/* ------------------------------------------------------------------ */

/*
 * quantized_matvec_fused -- fused INT8 dequant + matrix-vector multiply
 *
 * Computes:  y[i] = sum_k( data[i,k] * scales[i, k/group_size] * x[k] )
 * Then applies optional activation to y in-place.
 *
 * Inner loop: AVX2, 8 int8 elements per iteration
 *   - _mm_loadl_epi64:      load 8 int8 bytes
 *   - _mm256_cvtepi8_epi32: sign-extend int8 -> int32
 *   - _mm256_cvtepi32_ps:   int32 -> float32
 *   - _mm256_fmadd_ps:      fused multiply-add with scaled input vector
 *
 * group_size must be a multiple of 8 (always 64 in our system).
 */
EXPORT
void quantized_matvec_fused(
    const int8_t*  data,       /* [M, K_padded] row-major INT8          */
    const float*   scales,     /* [M, n_groups] per-group float32       */
    const float*   x,          /* [K_padded] input vector, zero-padded  */
    float*         y,          /* [M] output vector                     */
    int M,
    int K,
    int K_padded,
    int n_groups,
    int group_size,
    int activation             /* ACT_NONE/SIGMOID/RELU_SQ/TANH        */
) {
    const int chunks_per_group = group_size >> 3;  /* group_size / 8 */

    /* ---------- matvec: one row at a time ---------- */
    /* OpenMP: M=4096 independent rows, each accumulates its own y[i].
     * No cross-row dependencies. Perfect data parallelism.
     * schedule(static) for even row distribution. */
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < M; i++) {
        const int8_t* row = data   + (size_t)i * K_padded;
        const float*  sc  = scales + (size_t)i * n_groups;
        __m256 acc = _mm256_setzero_ps();

        for (int g = 0; g < n_groups; g++) {
            __m256 scale_v = _mm256_set1_ps(sc[g]);
            int base = g * group_size;

            for (int c = 0; c < chunks_per_group; c++) {
                int k = base + (c << 3);

                /* Load 8 int8 values, sign-extend to float32 */
                __m128i raw = _mm_loadl_epi64((const __m128i*)(row + k));
                __m256i i32 = _mm256_cvtepi8_epi32(raw);
                __m256  f32 = _mm256_cvtepi32_ps(i32);

                /* Load 8 floats from x, pre-multiply by group scale */
                __m256 xv = _mm256_loadu_ps(x + k);
                __m256 sx = _mm256_mul_ps(scale_v, xv);

                /* Accumulate: acc += dequantized * x_scaled */
                acc = _mm256_fmadd_ps(f32, sx, acc);
            }
        }

        y[i] = hsum_avx(acc);
    }

    /* ---------- activation in-place (vectorized) ---------- */
    if (activation == ACT_NONE) return;

    int m8 = M & ~7;   /* M rounded down to multiple of 8 */

    switch (activation) {

    case ACT_SIGMOID:
        for (int i = 0; i < m8; i += 8) {
            __m256 v = _mm256_loadu_ps(y + i);
            _mm256_storeu_ps(y + i, fast_sigmoid_avx2(v));
        }
        for (int i = m8; i < M; i++) {
            y[i] = 1.0f / (1.0f + expf(-y[i]));
        }
        break;

    case ACT_RELU_SQ: {
        __m256 zero = _mm256_setzero_ps();
        for (int i = 0; i < m8; i += 8) {
            __m256 v = _mm256_loadu_ps(y + i);
            __m256 r = _mm256_max_ps(v, zero);
            _mm256_storeu_ps(y + i, _mm256_mul_ps(r, r));
        }
        for (int i = m8; i < M; i++) {
            float v = y[i] > 0.0f ? y[i] : 0.0f;
            y[i] = v * v;
        }
        break;
    }

    case ACT_TANH: {
        __m256 two = _mm256_set1_ps(2.0f);
        __m256 one = _mm256_set1_ps(1.0f);
        for (int i = 0; i < m8; i += 8) {
            __m256 v = _mm256_loadu_ps(y + i);
            __m256 sig = fast_sigmoid_avx2(_mm256_mul_ps(two, v));
            _mm256_storeu_ps(y + i, _mm256_sub_ps(_mm256_mul_ps(two, sig), one));
        }
        for (int i = m8; i < M; i++) {
            y[i] = tanhf(y[i]);
        }
        break;
    }

    }  /* switch */
}

/* ------------------------------------------------------------------ */
/*  Kernel 2: Fused State Evolution (RWKV-7)                           */
/* ------------------------------------------------------------------ */

/*
 * state_evolution_fused -- RWKV-7 state recurrence for all heads
 *
 * Per head (h), with N×N state matrix:
 *   state = state * wt                           // decay: [N,N] * broadcast [N]
 *   icl_a = state @ (-kkt)                       // [N,N] @ [N] → [N]
 *   icl   = icl_a outer (kkt * at)               // [N] outer [N] → [N,N]
 *   vk    = vt outer kt                          // [N] outer [N] → [N,N]
 *   state = state + icl + vk                     // [N,N]
 *   output[h*N..] = state @ rt                   // [N,N] @ [N] → [N]
 *
 * Memory layout:
 *   state:  [H*N*N] float32, row-major. Modified IN-PLACE.
 *   wt,kkt,at,vt,kt,rt: each [H*N] float32 (squeezed from [H,1,N] or [H,N,1])
 *   output: [H*N] float32
 *
 * AVX2: N=64 → 8 iterations of 8-wide SIMD per row/dot product
 */
EXPORT
void state_evolution_fused(
    float*       state,     /* [H, N, N] row-major, modified in-place   */
    const float* wt,        /* [H, N] decay weights                     */
    const float* kkt,       /* [H, N] normalized key                    */
    const float* at,        /* [H, N] association coefficient            */
    const float* vt,        /* [H, N] value                             */
    const float* kt,        /* [H, N] key                               */
    const float* rt,        /* [H, N] receptance                        */
    float*       output,    /* [H*N] output buffer                      */
    int H,
    int N
) {
    const int N8 = N >> 3;  /* N / 8, assumes N is multiple of 8 */

    /* OpenMP: H=64 heads, each head has independent state[h], output[h].
     * Stack buffers kkt_at[64], neg_kkt[64] are thread-private (per-thread stack).
     * No cross-head dependencies. */
    #pragma omp parallel for schedule(static)
    for (int h = 0; h < H; h++) {
        float* S       = state  + (size_t)h * N * N;  /* [N, N] */
        const float* w = wt     + (size_t)h * N;
        const float* k_norm = kkt + (size_t)h * N;
        const float* a = at     + (size_t)h * N;
        const float* v = vt     + (size_t)h * N;
        const float* k = kt     + (size_t)h * N;
        const float* r = rt     + (size_t)h * N;
        float* out     = output + (size_t)h * N;

        /* --- Pre-compute kkt_at = kkt * at (element-wise) [N] --- */
        float kkt_at[64];   /* stack buffer, N <= 64 */
        for (int j = 0; j < N8; j++) {
            __m256 kk = _mm256_loadu_ps(k_norm + j*8);
            __m256 aa = _mm256_loadu_ps(a + j*8);
            _mm256_storeu_ps(kkt_at + j*8, _mm256_mul_ps(kk, aa));
        }

        /* --- Pre-compute neg_kkt = -kkt [N] --- */
        float neg_kkt[64];
        __m256 zero = _mm256_setzero_ps();
        for (int j = 0; j < N8; j++) {
            __m256 kk = _mm256_loadu_ps(k_norm + j*8);
            _mm256_storeu_ps(neg_kkt + j*8, _mm256_sub_ps(zero, kk));
        }

        /* --- Per-row of state: fuse decay + ICL + vk + readout --- */
        for (int i = 0; i < N; i++) {
            float* Si = S + (size_t)i * N;   /* state[h, i, :] */

            /* Step 1: Decay -- Si[j] *= w[j] */
            __m256 wi;
            for (int j = 0; j < N8; j++) {
                __m256 sj = _mm256_loadu_ps(Si + j*8);
                wi = _mm256_loadu_ps(w + j*8);
                _mm256_storeu_ps(Si + j*8, _mm256_mul_ps(sj, wi));
            }

            /* Step 2: icl_a[i] = dot(Si, neg_kkt) */
            __m256 dot_acc = _mm256_setzero_ps();
            for (int j = 0; j < N8; j++) {
                __m256 sj = _mm256_loadu_ps(Si + j*8);
                __m256 nk = _mm256_loadu_ps(neg_kkt + j*8);
                dot_acc = _mm256_fmadd_ps(sj, nk, dot_acc);
            }
            float icl_a_i = hsum_avx(dot_acc);

            /* Step 3: Si[j] += icl_a_i * kkt_at[j] + v[i] * k[j] */
            __m256 icl_scalar = _mm256_set1_ps(icl_a_i);
            __m256 vi_scalar  = _mm256_set1_ps(v[i]);
            for (int j = 0; j < N8; j++) {
                __m256 sj = _mm256_loadu_ps(Si + j*8);
                __m256 ka = _mm256_loadu_ps(kkt_at + j*8);
                __m256 kj = _mm256_loadu_ps(k + j*8);

                /* icl term: icl_a_i * kkt_at[j] */
                sj = _mm256_fmadd_ps(icl_scalar, ka, sj);
                /* vk term: v[i] * k[j] */
                sj = _mm256_fmadd_ps(vi_scalar, kj, sj);

                _mm256_storeu_ps(Si + j*8, sj);
            }

            /* Step 4: out[i] = dot(Si, r) -- readout */
            dot_acc = _mm256_setzero_ps();
            for (int j = 0; j < N8; j++) {
                __m256 sj = _mm256_loadu_ps(Si + j*8);
                __m256 rj = _mm256_loadu_ps(r + j*8);
                dot_acc = _mm256_fmadd_ps(sj, rj, dot_acc);
            }
            out[i] = hsum_avx(dot_acc);
        }
    }
}


/* ------------------------------------------------------------------ */
/*  Kernel 3: Fused LayerNorm                                          */
/* ------------------------------------------------------------------ */

/*
 * layernorm_fused -- two-pass LayerNorm with scale + bias
 *
 * Pass 1: compute mean and variance via sum and sum-of-squares
 * Pass 2: y[i] = (x[i] - mean) * rsqrt(var + eps) * weight[i] + bias[i]
 *
 * C must be a multiple of 8 (always 2048 in our system).
 */
EXPORT
void layernorm_fused(
    const float* x,         /* [C] input                                */
    const float* weight,    /* [C] scale                                */
    const float* bias,      /* [C] shift                                */
    float*       y,         /* [C] output                               */
    int C,
    float eps
) {
    const int C8 = C >> 3;
    float inv_C = 1.0f / (float)C;

    /* --- Pass 1: sum and sum-of-squares --- */
    __m256 vsum  = _mm256_setzero_ps();
    __m256 vsum2 = _mm256_setzero_ps();

    for (int i = 0; i < C8; i++) {
        __m256 xi = _mm256_loadu_ps(x + i*8);
        vsum  = _mm256_add_ps(vsum, xi);
        vsum2 = _mm256_fmadd_ps(xi, xi, vsum2);
    }

    float sum_val  = hsum_avx(vsum);
    float sum2_val = hsum_avx(vsum2);

    float mean = sum_val * inv_C;
    float var  = sum2_val * inv_C - mean * mean;
    float inv_std = 1.0f / sqrtf(var + eps);

    /* --- Pass 2: normalize + scale + bias --- */
    __m256 vmean    = _mm256_set1_ps(mean);
    __m256 vinv_std = _mm256_set1_ps(inv_std);

    for (int i = 0; i < C8; i++) {
        __m256 xi = _mm256_loadu_ps(x + i*8);
        __m256 wi = _mm256_loadu_ps(weight + i*8);
        __m256 bi = _mm256_loadu_ps(bias + i*8);

        /* (x - mean) * inv_std */
        __m256 normed = _mm256_mul_ps(_mm256_sub_ps(xi, vmean), vinv_std);
        /* normed * weight + bias */
        __m256 out = _mm256_fmadd_ps(normed, wi, bi);
        _mm256_storeu_ps(y + i*8, out);
    }

    /* Scalar tail for C not multiple of 8 */
    for (int i = C8 * 8; i < C; i++) {
        float normed = (x[i] - mean) * inv_std;
        y[i] = normed * weight[i] + bias[i];
    }
}


/* ------------------------------------------------------------------ */
/*  Kernel 4: Fused GroupNorm                                          */
/* ------------------------------------------------------------------ */

/*
 * groupnorm_fused -- per-group normalization with scale + bias
 *
 * x is split into num_groups groups of (C / num_groups) elements.
 * Each group: mean, var, normalize, then scale+bias from global weight/bias.
 *
 * group_size must be a multiple of 8 (always 64 in our system: 2048/32).
 */
EXPORT
void groupnorm_fused(
    const float* x,         /* [C] input                                */
    const float* weight,    /* [C] scale                                */
    const float* bias,      /* [C] shift                                */
    float*       y,         /* [C] output                               */
    int C,
    int num_groups,
    float eps
) {
    int group_size = C / num_groups;
    int gs8 = group_size >> 3;
    float inv_gs = 1.0f / (float)group_size;

    /* OpenMP: 32 independent groups, each normalizes its own slice.
     * No cross-group dependencies. */
    #pragma omp parallel for schedule(static)
    for (int g = 0; g < num_groups; g++) {
        int base = g * group_size;
        const float* xg = x + base;
        const float* wg = weight + base;
        const float* bg = bias + base;
        float* yg = y + base;

        /* --- Pass 1: sum and sum-of-squares for this group --- */
        __m256 vsum  = _mm256_setzero_ps();
        __m256 vsum2 = _mm256_setzero_ps();

        for (int i = 0; i < gs8; i++) {
            __m256 xi = _mm256_loadu_ps(xg + i*8);
            vsum  = _mm256_add_ps(vsum, xi);
            vsum2 = _mm256_fmadd_ps(xi, xi, vsum2);
        }

        float sum_val  = hsum_avx(vsum);
        float sum2_val = hsum_avx(vsum2);

        float mean = sum_val * inv_gs;
        float var  = sum2_val * inv_gs - mean * mean;
        float inv_std = 1.0f / sqrtf(var + eps);

        /* --- Pass 2: normalize + scale + bias --- */
        __m256 vmean    = _mm256_set1_ps(mean);
        __m256 vinv_std = _mm256_set1_ps(inv_std);

        for (int i = 0; i < gs8; i++) {
            __m256 xi = _mm256_loadu_ps(xg + i*8);
            __m256 wi = _mm256_loadu_ps(wg + i*8);
            __m256 bi = _mm256_loadu_ps(bg + i*8);

            __m256 normed = _mm256_mul_ps(_mm256_sub_ps(xi, vmean), vinv_std);
            __m256 out = _mm256_fmadd_ps(normed, wi, bi);
            _mm256_storeu_ps(yg + i*8, out);
        }

        /* Scalar tail */
        for (int i = gs8 * 8; i < group_size; i++) {
            float normed = (xg[i] - mean) * inv_std;
            yg[i] = normed * wg[i] + bg[i];
        }
    }
}


/* ------------------------------------------------------------------ */
/*  Utilities                                                          */
/* ------------------------------------------------------------------ */

/* Returns kernel version -- Python wrapper uses this to verify DLL loaded */
EXPORT
int battery_accel_version(void) {
    return 3;   /* v3: OpenMP multi-threaded */
}

/*
 * battery_set_threads -- Set OpenMP thread count at runtime.
 *
 * Called from Python side to configure parallelism based on
 * available cores and portal energy budget.
 *
 * When compiled WITHOUT -fopenmp, this is a no-op (graceful degradation).
 */
EXPORT
void battery_set_threads(int num_threads) {
#ifdef _OPENMP
    if (num_threads > 0) {
        omp_set_num_threads(num_threads);
    }
#endif
    (void)num_threads;  /* suppress unused warning when no OpenMP */
}

/*
 * battery_get_threads -- Query current OpenMP thread count.
 *
 * Returns the number of threads that will be used by parallel regions.
 * Returns 1 if compiled without OpenMP.
 */
EXPORT
int battery_get_threads(void) {
#ifdef _OPENMP
    return omp_get_max_threads();
#else
    return 1;
#endif
}

/*
 * battery_get_num_procs -- Query available processor count.
 *
 * Useful for auto-tuning thread count based on hardware.
 */
EXPORT
int battery_get_num_procs(void) {
#ifdef _OPENMP
    return omp_get_num_procs();
#else
    return 1;
#endif
}

#ifdef __cplusplus
}  /* extern "C" */
#endif
