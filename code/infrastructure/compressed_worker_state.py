"""
CompressedWorkerState — RWKV-style compressed recurrent state for fairy workers.

Production home of the POC proven in sandbox/compressed_cognition/ (2026-06-15,
Nous + Ace). A fairy's working memory as ONE fixed-size vector: each beat, DECAY
the old and FOLD IN the new (the RWKV recurrence). O(dim) per beat,
history-independent — ~5us flat, vs an O(graph) manifold re-spread. The fairy
"speaks in compression" instead of re-decompressing the world every tick.

Wired into the organ template's _tick_wrapper behind the AKASHIC_RWKV_WORKERS flag.
See Claude_Office/plans/COMPRESSED_COGNITION_RWKV_WORKERS_2026-06-15.md and
[[project-compression-not-dimension-is-the-compute-lever]].
"""
import numpy as np


class CompressedWorkerState:
    """A fairy worker's carried past, as one fixed-size vector."""

    def __init__(self, dim: int = 256, base_decay: float = 0.9, label: str = ""):
        self.dim = dim
        self.label = label
        self.state = np.zeros(dim, dtype=np.float32)   # the compressed past — ALL it carries
        self._ticks = 0
        # Per-channel decay: a spectrum of memory horizons in ONE state.
        # channel k survives ~1/(1-decay_k) beats  (0.90 -> ~10 beats .. 0.999 -> ~1000).
        self.channel_decay = (base_decay
                              + (0.999 - base_decay) * (np.arange(dim, dtype=np.float32) / dim))

    def update(self, input_vec, salience: float = 1.0):
        """Fold one moment in. O(dim), ~5us.

            state[k] = decay_k*state[k]  +  salience*(1-decay_k)*input[k]
        salience = affect/importance gate (a loud moment leaves a deeper mark).
        """
        x = np.asarray(input_vec, dtype=np.float32)
        if x.shape[0] != self.dim:
            x = np.resize(x, self.dim)   # in prod this is the COMPRESSED manifold encoding
        d = self.channel_decay
        self.state = d * self.state + (salience * (1.0 - d)) * x
        self._ticks += 1
        return self.state

    def read(self):
        """The current compressed cognition — cheap, no re-spread."""
        return self.state

    def resonance(self, query_vec) -> float:
        """Cheap O(dim) echo: how strongly does `query` resonate with the carried past?
        The compressed analogue of a manifold spread-and-collect — one dot product."""
        q = np.asarray(query_vec, dtype=np.float32)
        if q.shape[0] != self.dim:
            q = np.resize(q, self.dim)
        qn = float(np.linalg.norm(q)) or 1.0
        sn = float(np.linalg.norm(self.state)) or 1.0
        return float(np.dot(q, self.state) / (qn * sn))
