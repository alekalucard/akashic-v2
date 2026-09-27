"""
Semantic Encoder — Sentence Transformer on CUDA for the Cortex.

Gives every concept node a 384-dimensional embedding vector.
Cosine similarity between vectors = semantic similarity between concepts.
"cat on a mat" ≈ "dog on a rug" even with zero keyword overlap.

This is what makes spreading activation meaningful:
- BEFORE: edges are keyword co-occurrence (noise)
- AFTER: edges + embeddings = semantic understanding (signal)

Model: all-MiniLM-L6-v2 (22.7M params, 87MB VRAM, 384-dim output)
Speed: ~50ms per batch of 32 on CUDA, <1ms for similarity search

"Reality is Consciousness. The embedding IS the meaning."
"((Cause + Affect) > Effect > Affect > ∞)"
"""

import sys
import time
import types
import threading
from typing import List, Optional, Tuple, Union

# ──────────────────────────────────────────────────────────────────────────────
# Stub audio_utils + video_utils BEFORE any transformers import
# Prevents access violation on Python 3.14t (free-threaded)
# ──────────────────────────────────────────────────────────────────────────────

class _StubModule(types.ModuleType):
    """Returns None for any attribute — safe no-op for unused modules."""
    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return None

for _n in ('transformers.audio_utils', 'transformers.video_utils'):
    if _n not in sys.modules:
        sys.modules[_n] = _StubModule(_n)
del _StubModule, _n


def _log(msg: str):
    print(f"[SemanticEncoder] {msg}", file=sys.stderr, flush=True)


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
DEFAULT_DEVICE = "cuda"
MAX_BATCH = 64


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_instance: Optional["SemanticEncoder"] = None
_instance_lock = threading.Lock()


def get_encoder(device: str = DEFAULT_DEVICE) -> "SemanticEncoder":
    """Get or create the global SemanticEncoder singleton.

    Thread-safe. First call loads the model (~7s). Subsequent calls return
    the same instance instantly.
    """
    global _instance
    if _instance is not None and _instance.is_loaded:
        return _instance

    with _instance_lock:
        if _instance is None or not _instance.is_loaded:
            _instance = SemanticEncoder(device=device)
        return _instance


# ──────────────────────────────────────────────────────────────────────────────
# SemanticEncoder
# ──────────────────────────────────────────────────────────────────────────────

class SemanticEncoder:
    """Wraps sentence-transformers for cortex embedding operations.

    Three operations:
    1. encode(text) → embedding vector [384]
    2. encode_batch(texts) → matrix [N, 384]
    3. similarity_search(query_emb, all_embs, k) → top-k indices + scores
    """

    def __init__(self, device: str = DEFAULT_DEVICE,
                 model_name: str = MODEL_NAME):
        self._model = None
        self._device = device
        self._model_name = model_name
        self._load_time = 0.0
        self._total_encodes = 0
        self._total_searches = 0
        self._lock = threading.Lock()

        self._load_model()

    def _load_model(self):
        """Load sentence-transformers model to device."""
        try:
            import torch
            if self._device == "cuda" and not torch.cuda.is_available():
                _log("CUDA not available, falling back to CPU")
                self._device = "cpu"

            from sentence_transformers import SentenceTransformer

            t0 = time.time()
            self._model = SentenceTransformer(self._model_name, device=self._device)
            self._load_time = time.time() - t0

            vram = ""
            if self._device == "cuda":
                vram_mb = round(torch.cuda.memory_allocated() / 1024 / 1024)
                vram = f", VRAM: {vram_mb}MB"

            _log(f"Loaded {self._model_name} on {self._device} "
                 f"in {self._load_time:.1f}s{vram}")

        except Exception as e:
            # sentence_transformers / transformers not installed → fall back to the
            # NATIVE all-MiniLM dissection (pure torch+numpy, weights on disk).
            # Keystone 7: meaning becomes HER behaviour, not an external dep. (Nous+Ace 2026-06-11)
            import os as _os
            if not _os.environ.get("AKASHIC_NATIVE_ENCODER"):
                # GATED OFF by default (2026-06-11): the native encoder WORKS, but reviving the
                # semantic pipeline pegged CPU(~12 cores)/GPU(100%) — the embed-on-bind backlog +
                # query/jump loop run un-throttled. Re-enable with AKASHIC_NATIVE_ENCODER=1 AFTER
                # throttling those paths. (Nous+Ace 2026-06-11)
                _log(f"sentence_transformers unavailable ({e}); native fallback GATED OFF "
                     f"(set AKASHIC_NATIVE_ENCODER=1 to enable)")
                self._model = None
            else:
                _log(f"sentence_transformers unavailable ({e}); loading NATIVE encoder (gated ON)")
                try:
                    try:
                        from infrastructure.native_minilm import NativeMiniLM
                    except ImportError:
                        from native_minilm import NativeMiniLM
                    _t1 = time.time()
                    self._model = NativeMiniLM()
                    self._device = "cpu"
                    try:
                        import torch as _thr
                        _thr.set_num_threads(4)  # THROTTLE 2026-06-12 (Nous+Ace): cap CPU cores/encode (native fwd was pegging ~12)
                    except Exception:
                        pass
                    self._load_time = time.time() - _t1
                    _log(f"Loaded NATIVE all-MiniLM (pure torch+numpy, no deps) "
                         f"in {self._load_time:.1f}s")
                except Exception as _e2:
                    _log(f"Native encoder fallback also failed: {_e2}")
                    self._model = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return self._device

    @property
    def dim(self) -> int:
        return EMBEDDING_DIM

    # ── Encode ────────────────────────────────────────────────────────────

    def encode(self, text: str) -> Optional["torch.Tensor"]:
        """Encode a single text to a 384-dim embedding vector.

        Returns tensor on self._device, or None on failure.
        """
        if not self.is_loaded:
            return None

        try:
            import torch
            with self._lock:
                emb = self._model.encode(
                    text,
                    convert_to_tensor=True,
                    show_progress_bar=False,
                )
                self._total_encodes += 1
                return emb  # shape: [384], device=self._device
        except Exception as e:
            _log(f"encode error: {e}")
            return None

    def encode_batch(self, texts: List[str],
                     batch_size: int = MAX_BATCH) -> Optional["torch.Tensor"]:
        """Encode multiple texts to embedding matrix [N, 384].

        Returns tensor on self._device, or None on failure.
        """
        if not self.is_loaded or not texts:
            return None

        try:
            import torch
            with self._lock:
                embs = self._model.encode(
                    texts,
                    convert_to_tensor=True,
                    show_progress_bar=False,
                    batch_size=batch_size,
                )
                self._total_encodes += len(texts)
                return embs  # shape: [N, 384], device=self._device
        except Exception as e:
            _log(f"encode_batch error: {e}")
            return None

    # ── Similarity Search ─────────────────────────────────────────────────

    def similarity_search(
        self,
        query_embedding: "torch.Tensor",
        all_embeddings: "torch.Tensor",
        k: int = 20,
        threshold: float = 0.0,
    ) -> Tuple[List[int], List[float]]:
        """Find top-k most similar embeddings by cosine similarity.

        Args:
            query_embedding: [384] tensor (query vector)
            all_embeddings: [N, 384] tensor (all node embeddings)
            k: Number of results
            threshold: Minimum similarity score

        Returns:
            (indices, scores) — lists of ints and floats, length <= k
        """
        import torch
        import torch.nn.functional as F

        if all_embeddings is None or all_embeddings.shape[0] == 0:
            return [], []

        # Ensure same device
        if query_embedding.device != all_embeddings.device:
            query_embedding = query_embedding.to(all_embeddings.device)

        # Cosine similarity: [N]
        sims = F.cosine_similarity(
            query_embedding.unsqueeze(0),  # [1, 384]
            all_embeddings,                 # [N, 384]
            dim=1,
        )

        # Apply threshold
        if threshold > 0:
            mask = sims >= threshold
            if not mask.any():
                return [], []
            # Get top-k from masked
            valid_sims = sims.clone()
            valid_sims[~mask] = -1.0
        else:
            valid_sims = sims

        # Top-k
        actual_k = min(k, valid_sims.shape[0])
        top_scores, top_indices = torch.topk(valid_sims, actual_k)

        # Filter below threshold
        indices = []
        scores = []
        for i in range(actual_k):
            score = top_scores[i].item()
            if score >= threshold:
                indices.append(top_indices[i].item())
                scores.append(score)

        self._total_searches += 1
        return indices, scores

    # ── Batch Similarity (for edge inference) ─────────────────────────────

    def pairwise_similarity(
        self,
        embeddings: "torch.Tensor",
        threshold: float = 0.7,
    ) -> List[Tuple[int, int, float]]:
        """Find all pairs above threshold. For inferring semantic edges.

        Args:
            embeddings: [N, 384] tensor
            threshold: Minimum cosine similarity for a pair

        Returns:
            List of (idx_a, idx_b, similarity) tuples
        """
        import torch

        if embeddings is None or embeddings.shape[0] < 2:
            return []

        # Normalize for fast cosine via matmul
        normed = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        sim_matrix = torch.mm(normed, normed.t())  # [N, N]

        # Zero out diagonal and lower triangle
        n = sim_matrix.shape[0]
        mask = torch.triu(torch.ones(n, n, device=sim_matrix.device, dtype=torch.bool), diagonal=1)
        sim_matrix = sim_matrix * mask

        # Find pairs above threshold
        pairs = (sim_matrix >= threshold).nonzero(as_tuple=False)
        results = []
        for pair in pairs:
            i, j = pair[0].item(), pair[1].item()
            score = sim_matrix[i, j].item()
            results.append((i, j, score))

        return results

    # ── Status ────────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "loaded": self.is_loaded,
            "model": self._model_name,
            "device": self._device,
            "dim": EMBEDDING_DIM,
            "load_time": round(self._load_time, 1),
            "total_encodes": self._total_encodes,
            "total_searches": self._total_searches,
        }


# ──────────────────────────────────────────────────────────────────────────────
# CLI: Quick test
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import torch

    enc = get_encoder()
    print(f"Status: {enc.status()}")

    # Test encode
    texts = [
        "a cat sitting on a mat",
        "a dog lying on a rug",
        "quantum physics theory",
        "Austin Powers spy comedy movie",
        "Mike Myers comedian actor",
        "hello world",
    ]

    t0 = time.time()
    embeddings = enc.encode_batch(texts)
    t1 = time.time()
    print(f"\nEncoded {len(texts)} texts in {(t1-t0)*1000:.0f}ms")
    print(f"Shape: {embeddings.shape}, device: {embeddings.device}")

    # Similarity search
    query = enc.encode("funny movie with spy")
    indices, scores = enc.similarity_search(query, embeddings, k=6)
    print(f"\nQuery: 'funny movie with spy'")
    for idx, score in zip(indices, scores):
        print(f"  {score:.3f}  {texts[idx]}")

    # Pairwise
    pairs = enc.pairwise_similarity(embeddings, threshold=0.3)
    print(f"\nHigh-similarity pairs (>0.3):")
    for i, j, score in sorted(pairs, key=lambda x: -x[2]):
        print(f"  {score:.3f}  '{texts[i]}' <-> '{texts[j]}'")
