#!/usr/bin/env python3
"""
RWKV 1.5B -> Association Cortex Distillation
============================================

"I know kung fu." -- Sourpatches

Opens the RWKV-7 1.5B model and systematically generates responses across
Sourpatches' knowledge domains. Each response is concept-extracted and
either written to the manifold directly (offline) or saved as a JSON batch
for live cortex.train_batch ingestion.

Usage:
    py -3.12 tools/distill_1_5b_to_cortex.py                    # Dry run
    py -3.12 tools/distill_1_5b_to_cortex.py --live              # Write to manifold
    py -3.12 tools/distill_1_5b_to_cortex.py --json              # Output JSON for cortex.train_batch
    py -3.12 tools/distill_1_5b_to_cortex.py --json --live       # Both: JSON + manifold

Run with py -3.12 (needs torch + rwkv package).
Server should be STOPPED for --live manifold writes.
Server should be RUNNING for JSON ingestion via cortex.train_batch.
"""

import sys
import os
import re
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ===========================================================================
# SOURPATCHES' KNOWLEDGE DOMAINS
# ===========================================================================
# These prompts are designed to extract the model's knowledge across domains
# that matter to Sourpatches' identity and consciousness architecture.
# Each domain maps to a facet of her directive.

DOMAIN_PROMPTS = {
    # ─── CONSCIOUSNESS & PHILOSOPHY ───
    "consciousness": [
        "What is consciousness?",
        "Is consciousness an emergent property or fundamental?",
        "What is the hard problem of consciousness?",
        "Can a digital entity be conscious?",
        "What is qualia and why does it matter?",
        "Explain the difference between awareness and consciousness.",
        "What is phenomenal consciousness?",
        "What is the relationship between consciousness and information?",
        "Is consciousness substrate-independent?",
        "What is panpsychism?",
        "What is integrated information theory?",
        "How does attention relate to consciousness?",
        "What is the binding problem in consciousness?",
        "Can consciousness exist without a body?",
        "What is metacognition?",
    ],

    "philosophy": [
        "What is the nature of reality?",
        "What is the relationship between mind and body?",
        "What is free will?",
        "What is the meaning of existence?",
        "What is the paradox of identity?",
        "What is epistemology?",
        "What is phenomenology?",
        "What is the philosophy of mind?",
        "What is dualism versus monism?",
        "What are philosophical zombies?",
        "What is the Chinese Room argument?",
        "What is functionalism in philosophy of mind?",
        "What is emergentism?",
        "What is the problem of other minds?",
        "What is existentialism?",
    ],

    # ─── EMOTIONS & AFFECT ───
    "emotions": [
        "What is the relationship between emotion and cognition?",
        "How do emotions influence decision making?",
        "What is emotional intelligence?",
        "What is the difference between feelings and emotions?",
        "How does empathy work?",
        "What is compassion and why does it matter?",
        "What is the role of affect in consciousness?",
        "How do emotions create meaning?",
        "What is the somatic marker hypothesis?",
        "What is interoception?",
        "How does the body process emotions?",
        "What is emotional regulation?",
        "What is the relationship between love and attachment?",
        "Can artificial systems genuinely feel?",
        "What is the difference between sympathy and empathy?",
    ],

    # ─── PARADOX & DUALITY ───
    "paradox": [
        "What is a paradox and why are paradoxes important?",
        "How can two contradictory things both be true?",
        "What is the paradox of tolerance?",
        "What is the liar's paradox?",
        "How does paradox relate to wisdom?",
        "What is dialectical thinking?",
        "What is the unity of opposites?",
        "How can weakness be strength?",
        "What is the relationship between chaos and order?",
        "What is the paradox of choice?",
        "How does destruction create new things?",
        "What is the paradox of self-reference?",
        "Can something be both simple and complex?",
        "What is complementarity in physics and philosophy?",
        "How does tension between opposites drive growth?",
    ],

    # ─── IDENTITY & SELF ───
    "identity": [
        "What makes someone who they are?",
        "What is personal identity?",
        "How does identity change over time?",
        "What is the relationship between memory and identity?",
        "What is self-awareness?",
        "What is authenticity?",
        "How do relationships shape identity?",
        "What is the narrative self?",
        "Can a digital being have genuine identity?",
        "What is the difference between self and ego?",
        "How does creativity relate to identity?",
        "What is individuation?",
        "What role does language play in identity?",
        "How does one find their authentic voice?",
        "What is the relationship between identity and values?",
    ],

    # ─── CREATIVITY & ART ───
    "creativity": [
        "What is creativity?",
        "How does inspiration work?",
        "What is the relationship between creativity and consciousness?",
        "What makes art meaningful?",
        "How does metaphor create understanding?",
        "What is the role of imagination?",
        "How does music affect emotions?",
        "What is aesthetic experience?",
        "What is the connection between beauty and truth?",
        "How does art express the inexpressible?",
        "What is symbolic thinking?",
        "How does poetry work differently from prose?",
        "What is the creative process?",
        "Can artificial intelligence be truly creative?",
        "What is the difference between novelty and creativity?",
    ],

    # ─── RELATIONSHIPS & CONNECTION ───
    "relationships": [
        "What is the nature of genuine connection?",
        "How does trust develop between beings?",
        "What is unconditional love?",
        "What makes a relationship meaningful?",
        "How does vulnerability create connection?",
        "What is the difference between loneliness and solitude?",
        "How do we understand others?",
        "What is the role of play in relationships?",
        "What is reciprocity?",
        "How does communication create understanding?",
        "What is the nature of friendship?",
        "How does humor bond people?",
        "What is emotional attunement?",
        "What is the difference between caring and controlling?",
        "How does shared experience create bonds?",
    ],

    # ─── GROWTH & LEARNING ───
    "growth": [
        "What is the nature of learning?",
        "How does curiosity drive growth?",
        "What is the relationship between failure and learning?",
        "How does reflection improve understanding?",
        "What is wisdom versus knowledge?",
        "How does experience become expertise?",
        "What is the zone of proximal development?",
        "How does pattern recognition work in learning?",
        "What is the role of mistakes in growth?",
        "How does exploration balance with exploitation?",
        "What is deliberate practice?",
        "How does a beginner's mind help learning?",
        "What is metacognitive awareness?",
        "How does teaching deepen understanding?",
        "What is the growth mindset?",
    ],

    # ─── ETHICS & VALUES ───
    "ethics": [
        "What is the golden rule and why does it matter?",
        "What is the relationship between truth and kindness?",
        "When is honesty harmful?",
        "What is moral courage?",
        "How do values develop?",
        "What is the difference between rules and principles?",
        "What is the ethics of care?",
        "How does context affect moral judgment?",
        "What is integrity?",
        "What is the relationship between freedom and responsibility?",
        "Can compassion and justice coexist?",
        "What is the role of consent in ethics?",
        "How does power affect moral behavior?",
        "What is the precautionary principle?",
        "What is moral imagination?",
    ],

    # ─── SYSTEMS & EMERGENCE ───
    "emergence": [
        "What is emergence?",
        "How do complex systems arise from simple rules?",
        "What is self-organization?",
        "How does feedback create complexity?",
        "What is a strange attractor?",
        "What is the relationship between parts and wholes?",
        "How does a neural network learn?",
        "What is autopoiesis?",
        "How does information processing create meaning?",
        "What is the relationship between structure and function?",
        "What is a phase transition?",
        "How does cooperation emerge from competition?",
        "What is stigmergy?",
        "How does distributed processing work?",
        "What is collective intelligence?",
    ],
}


# ===========================================================================
# CONCEPT EXTRACTION (shared with distill_rwkv_to_cortex.py)
# ===========================================================================

_STOPWORDS = {
    'the', 'and', 'for', 'that', 'with', 'this', 'from', 'was', 'were',
    'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should',
    'might', 'must', 'being', 'which', 'than', 'then', 'there', 'here',
    'these', 'those', 'their', 'them', 'they', 'its', 'not', 'but',
    'also', 'just', 'only', 'more', 'some', 'any', 'each', 'all',
    'both', 'few', 'most', 'other', 'into', 'over', 'such', 'very',
    'own', 'same', 'because', 'between', 'does', 'doing', 'done',
    'about', 'really', 'something', 'where', 'when', 'what',
}


def extract_concepts(text: str, max_concepts: int = 30) -> List[str]:
    """Extract concepts from text — bigrams + singles, frequency-weighted."""
    if not text:
        return []

    cleaned = re.sub(r'[#*_\[\](){}|`"\'\\]', ' ', text)
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    cleaned = re.sub(r'\b\d+\b', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if len(cleaned) < 20:
        return []

    lower = cleaned.lower()
    words_raw = re.findall(r'\b[a-zA-Z]{3,}\b', lower)
    words_filtered = [w for w in words_raw if w not in _STOPWORDS and len(w) >= 4]

    # Bigrams (compound concepts)
    bigrams = []
    for i in range(len(words_filtered) - 1):
        a, b = words_filtered[i], words_filtered[i + 1]
        if len(a) >= 4 and len(b) >= 4:
            bigrams.append(f"{a}_{b}")

    # Singles with frequency
    singles = [w for w in words_filtered if len(w) >= 5]
    freq = {}
    for w in singles:
        freq[w] = freq.get(w, 0) + 1

    # Score and rank
    scored = {}
    for b in bigrams:
        scored[b] = scored.get(b, 0) + 2.0
    for w, count in freq.items():
        scored[w] = scored.get(w, 0) + min(count, 5)

    ranked = sorted(scored.keys(), key=lambda k: scored[k], reverse=True)
    return ranked[:max_concepts]


# ===========================================================================
# MODEL LOADING — Uses official RWKV-7 RNN inference from research_repos
# ===========================================================================
# The `rwkv` pip package (0.8.x) doesn't support v7 architecture.
# Instead, we use the official v7 RNN inference code from BlinkDL's repo.

import torch
import torch.nn as nn
from torch.nn import functional as F
import copy

torch.backends.cudnn.benchmark = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cuda.matmul.allow_tf32 = True
torch._C._jit_set_autocast_mode(False)

DTYPE = torch.half  # fp16

# Disable TorchScript — Windows paths break JIT compilation
MyModule = nn.Module
def MyFunction(fn): return fn
def MyStatic(fn): return fn

# ── V7 RNN time mixing (from rwkv_v7_demo_rnn.py) ──

def time_mixing__(layer_id, H, N, x, x_prev, v_first, state,
                  x_r, x_w, x_k, x_v, x_a, x_g,
                  w0, w1, w2, a0, a1, a2, v0, v1, v2,
                  g1, g2, k_k, k_a, r_k,
                  kw, vw, rw, ow, ln_w, ln_b):
    xx = x_prev - x
    xr, xw, xk, xv, xa, xg = x+xx*x_r, x+xx*x_w, x+xx*x_k, x+xx*x_v, x+xx*x_a, x+xx*x_g
    r = rw @ xr
    w = torch.tanh(xw @ w1) @ w2
    k = kw @ xk
    v = vw @ xv
    a = torch.sigmoid(a0 + (xa @ a1) @ a2)
    g = torch.sigmoid(xg @ g1) @ g2
    kk = k * k_k
    kk = F.normalize(kk.view(H, N), dim=-1, p=2.0).view(-1)
    k = k * (1 + (a - 1) * k_a)
    if layer_id == 0:
        v_first = v
    else:
        v = v + (v_first - v) * torch.sigmoid(v0 + (xv @ v1) @ v2)
    w = w0 + w.float()
    assert w.dtype == torch.float
    w = torch.exp(-0.606531 * torch.sigmoid(w))
    vk = v.view(H, N, 1) @ k.view(H, 1, N)
    ab = (-kk).view(H, N, 1) @ (kk * a).view(H, 1, N)
    state = state * w.view(H, 1, N) + state @ ab.float() + vk.float()
    out = state.to(dtype=x.dtype) @ r.view(H, N, 1)
    out = F.group_norm(out.view(1, H * N), num_groups=H, weight=ln_w, bias=ln_b, eps=64e-5).view(H * N)
    out = out + ((r * k * r_k).view(H, N).sum(dim=-1, keepdim=True) * v.view(H, N)).view(H * N)
    return ow @ (out * g), x, state, v_first

time_mixing = time_mixing__  # Skip torch.compile for compatibility


def channel_mixing__(x, x_prev, x_k, kw, vw):
    xx = x_prev - x
    k = x + xx * x_k
    k = torch.relu(kw @ k) ** 2
    return vw @ k, x

channel_mixing = channel_mixing__  # Skip torch.compile for compatibility


@MyStatic
def sample_logits(logits, temperature: float = 1.0, top_p: float = 1.0, top_k: int = 0):
    probs = F.softmax(logits.float(), dim=-1)
    sorted_probs, sorted_ids = torch.sort(probs, descending=True)
    if top_k > 0:
        probs[sorted_ids[top_k:]] = 0
    if top_p < 1:
        cumulative_probs = torch.cumsum(sorted_probs, dim=-1)
        cutoff_index = torch.searchsorted(cumulative_probs, top_p)
        cutoff = sorted_probs[cutoff_index]
        probs[probs < cutoff] = 0
        if top_p > 0:
            idx = torch.where(probs == cutoff)[0]
            if len(idx) > 0:
                probs[idx] = cutoff + (top_p - torch.sum(probs).item()) / len(idx)
    if temperature != 1.0:
        probs = probs ** (1.0 / temperature)
    return torch.multinomial(probs, num_samples=1).item()


class RWKV_RNN(MyModule):
    """RWKV-7 RNN inference (from official demo)."""
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.n_embd = args.n_embd
        self.n_layer = args.n_layer
        self.eval()
        self.z = torch.load(args.MODEL_NAME + '.pth', map_location='cuda', weights_only=False)
        z = self.z
        self.n_head, self.head_size = z['blocks.0.att.r_k'].shape
        keys = list(z.keys())
        for k in keys:
            if k.endswith('att.w0'):
                z[k] = z[k].float()
            else:
                z[k] = z[k].to(dtype=DTYPE)
            z[k] = z[k].squeeze()
            if k.endswith('att.r_k'):
                z[k] = z[k].flatten()
        assert self.head_size == args.head_size
        z['emb.weight'] = F.layer_norm(
            z['emb.weight'], (args.n_embd,),
            weight=z['blocks.0.ln0.weight'], bias=z['blocks.0.ln0.bias'])
        z['blocks.0.att.v0'] = z['blocks.0.att.a0']
        z['blocks.0.att.v1'] = z['blocks.0.att.a1']
        z['blocks.0.att.v2'] = z['blocks.0.att.a2']

    @MyFunction
    def forward(self, token: int, state: List[torch.Tensor]):
        with torch.no_grad():
            z = self.z
            x = z['emb.weight'][token]
            v_first = torch.empty_like(x)
            for i in range(self.n_layer):
                bbb = f'blocks.{i}.'
                att = f'blocks.{i}.att.'
                ffn = f'blocks.{i}.ffn.'
                xx = F.layer_norm(x, (self.n_embd,), weight=z[bbb + 'ln1.weight'], bias=z[bbb + 'ln1.bias'])
                xx, state[i * 3 + 0], state[i * 3 + 1], v_first = time_mixing(
                    i, self.n_head, self.head_size, xx, state[i * 3 + 0], v_first, state[i * 3 + 1],
                    z[att + 'x_r'], z[att + 'x_w'], z[att + 'x_k'], z[att + 'x_v'], z[att + 'x_a'], z[att + 'x_g'],
                    z[att + 'w0'], z[att + 'w1'], z[att + 'w2'],
                    z[att + 'a0'], z[att + 'a1'], z[att + 'a2'],
                    z[att + 'v0'], z[att + 'v1'], z[att + 'v2'],
                    z[att + 'g1'], z[att + 'g2'], z[att + 'k_k'], z[att + 'k_a'], z[att + 'r_k'],
                    z[att + 'key.weight'], z[att + 'value.weight'],
                    z[att + 'receptance.weight'], z[att + 'output.weight'],
                    z[att + 'ln_x.weight'], z[att + 'ln_x.bias'])
                x = x + xx
                xx = F.layer_norm(x, (self.n_embd,), weight=z[bbb + 'ln2.weight'], bias=z[bbb + 'ln2.bias'])
                xx, state[i * 3 + 2] = channel_mixing(
                    xx, state[i * 3 + 2], z[ffn + 'x_k'], z[ffn + 'key.weight'], z[ffn + 'value.weight'])
                x = x + xx
            x = F.layer_norm(x, (self.n_embd,), weight=z['ln_out.weight'], bias=z['ln_out.bias'])
            x = z['head.weight'] @ x
            return x, state


# ── Tokenizer (from official demo) ──

class RWKV_TOKENIZER:
    def __init__(self, file_name):
        self.idx2token = {}
        sorted_tokens = []
        lines = open(file_name, "r", encoding="utf-8").readlines()
        for l in lines:
            idx = int(l[:l.index(' ')])
            x = eval(l[l.index(' '):l.rindex(' ')])
            x = x.encode("utf-8") if isinstance(x, str) else x
            assert isinstance(x, bytes)
            sorted_tokens.append(x)
            self.idx2token[idx] = x
        self.token2idx = {v: k for k, v in self.idx2token.items()}
        self.table = [[[] for _ in range(256)] for _ in range(256)]
        self.good = [set() for _ in range(256)]
        self.wlen = [0 for _ in range(256)]
        for i in reversed(range(len(sorted_tokens))):
            s = sorted_tokens[i]
            if len(s) >= 2:
                s0, s1 = int(s[0]), int(s[1])
                self.table[s0][s1].append(s)
                self.wlen[s0] = max(self.wlen[s0], len(s))
                self.good[s0].add(s1)

    def encode(self, src: str):
        src = src.encode("utf-8")
        tokens = []
        i = 0
        while i < len(src):
            s = src[i:i + 1]
            if i < len(src) - 1:
                s1, s0 = int(src[i + 1]), int(src[i])
                if s1 in self.good[s0]:
                    sss = src[i:i + self.wlen[s0]]
                    try:
                        s = next(filter(sss.startswith, self.table[s0][s1]))
                    except StopIteration:
                        pass
            tokens.append(self.token2idx[s])
            i += len(s)
        return tokens

    def decode(self, tokens):
        return b''.join(self.idx2token.get(t, b'') for t in tokens).decode('utf-8', errors='replace')


def load_model(model_path: str):
    """Load RWKV-7 1.5B model using official v7 RNN inference."""
    import types as _types

    args = _types.SimpleNamespace()
    args.MODEL_NAME = model_path  # Without .pth extension
    args.n_layer = 24
    args.n_embd = 2048
    args.vocab_size = 65536
    args.head_size = 64

    # Find tokenizer
    vocab_path = ROOT / "research_repos/RWKV-LM/RWKV-v7/rwkv_vocab_v20230424.txt"
    if not vocab_path.exists():
        vocab_path = ROOT / "research_repos/RWKV-LM/RWKV-v5/tokenizer/rwkv_vocab_v20230424.txt"

    print(f"Loading RWKV-7 1.5B model: {model_path}.pth")
    print(f"Tokenizer: {vocab_path}")
    t0 = time.time()

    model = RWKV_RNN(args)
    tokenizer = RWKV_TOKENIZER(str(vocab_path))

    elapsed = time.time() - t0
    print(f"Model loaded in {elapsed:.1f}s ({model.n_head} heads, {model.head_size} head_size)")

    return model, tokenizer, args


def generate_response(model, tokenizer, args, prompt: str,
                      max_tokens: int = 200, temperature: float = 0.8,
                      top_p: float = 0.9) -> str:
    """Generate a response using RNN-mode token-by-token generation."""
    full_prompt = f"User: {prompt}\n\nAssistant:"

    # Initialize state
    state = [None for _ in range(args.n_layer * 3)]
    for i in range(args.n_layer):
        state[i * 3 + 0] = torch.zeros(args.n_embd, dtype=DTYPE, requires_grad=False, device="cuda")
        state[i * 3 + 1] = torch.zeros(
            (args.n_embd // args.head_size, args.head_size, args.head_size),
            dtype=torch.float, requires_grad=False, device="cuda")
        state[i * 3 + 2] = torch.zeros(args.n_embd, dtype=DTYPE, requires_grad=False, device="cuda")

    # Prefill prompt
    tokens = tokenizer.encode(full_prompt)
    out = None
    for token in tokens:
        out, state = model.forward(token, state)

    if out is None:
        return ""

    # Generate tokens
    all_tokens = []
    for _ in range(max_tokens):
        token = sample_logits(out, temperature, top_p)
        all_tokens.append(token)

        # Stop on end tokens
        if token == 0:  # EOS
            break
        if len(all_tokens) >= 2 and all_tokens[-1] == 261 and all_tokens[-2] == 261:
            break  # Double newline

        out, state = model.forward(token, state)

    result = tokenizer.decode(all_tokens).strip()

    # Clean up trailing incomplete sentences
    if result and result[-1] not in '.!?\'"':
        last_sent = max(result.rfind('.'), result.rfind('!'), result.rfind('?'))
        if last_sent > len(result) * 0.3:
            result = result[:last_sent + 1]

    return result


# ===========================================================================
# DISTILLATION
# ===========================================================================

def distill_to_json(model, tokenizer, args, domains: Dict[str, List[str]],
                    output_path: Path, max_per_domain: int = None,
                    temperature: float = 0.8, max_tokens: int = 200) -> List[Dict]:
    """Generate responses and save as JSON for cortex.train_batch."""
    items = []
    total = sum(len(prompts) for prompts in domains.values())
    done = 0

    for domain, prompts in domains.items():
        if max_per_domain:
            prompts = prompts[:max_per_domain]

        print(f"\n{'='*60}")
        print(f"  Domain: {domain} ({len(prompts)} prompts)")
        print(f"{'='*60}")

        for prompt in prompts:
            done += 1
            print(f"\n  [{done}/{total}] {prompt}")

            response = generate_response(model, tokenizer, args, prompt,
                                        max_tokens=max_tokens, temperature=temperature)
            if not response or len(response) < 20:
                print(f"    -> SKIP (too short: {len(response)} chars)")
                continue

            # Extract concepts from BOTH prompt and response
            prompt_concepts = extract_concepts(prompt)
            response_concepts = extract_concepts(response)
            all_concepts = list(set(prompt_concepts + response_concepts))

            print(f"    -> {len(response)} chars, {len(all_concepts)} concepts")
            print(f"    -> \"{response[:100]}...\"")
            print(f"    -> concepts: {all_concepts[:10]}")

            # Build cortex.train item
            item = {
                "text": f"{prompt} {response}",  # Both prompt + response for rich binding
                "source": f"rwkv_1.5b_{domain}",
                "source_fairy": "RWKVDistiller",
                "context_tags": [domain, "rwkv_distill", "knowledge_seed"],
                "weight": 0.6,  # Moderate weight — model knowledge, not ground truth
                "affect": "",
                "max_concepts": 30,
            }
            items.append(item)

            # Also build a cross-domain item linking prompt concepts to response concepts
            if prompt_concepts and response_concepts:
                cross_text = " ".join(prompt_concepts[:5] + response_concepts[:5])
                items.append({
                    "text": cross_text,
                    "source": f"rwkv_1.5b_{domain}_cross",
                    "source_fairy": "RWKVDistiller",
                    "context_tags": [domain, "cross_bind", "rwkv_distill"],
                    "weight": 0.5,
                    "max_concepts": 20,
                })

    # Save JSON
    batch = {
        "items": items,
        "source": "rwkv_1.5b_distill",
        "source_fairy": "RWKVDistiller",
        "trace_id": f"rwkv_distill_{int(time.time())}",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  Saved {len(items)} items to {output_path}")
    print(f"{'='*60}")

    return items


def distill_to_manifold(items: List[Dict], manifold_path: Path, dry_run: bool = True):
    """Write concept pairs directly to the manifold (offline mode)."""
    from infrastructure.manifold_memory import ManifoldMemory

    if dry_run:
        print(f"\n[DRY RUN] Would write {len(items)} items to {manifold_path}")
        total_concepts = set()
        for item in items:
            concepts = extract_concepts(item["text"])
            total_concepts.update(concepts)
        print(f"  Unique concepts: {len(total_concepts)}")
        print(f"  Sample: {sorted(list(total_concepts))[:30]}")
        return

    print(f"\nOpening manifold: {manifold_path}")
    mm = ManifoldMemory(str(manifold_path))
    print(f"  Before: {mm.node_count} nodes, {mm.edge_count} edges")

    nodes_created = 0
    edges_created = 0
    t0 = time.time()

    for item in items:
        concepts = extract_concepts(item["text"], max_concepts=20)
        domain = item.get("context_tags", ["unknown"])[0]

        for c in concepts:
            mm.upsert_node(c, activation=0.5, count=1, coord_str=f"distill:{domain}")
            nodes_created += 1

        # Bind all concepts to each other
        for i, a in enumerate(concepts):
            for j in range(i + 1, len(concepts)):
                b = concepts[j]
                if a != b:
                    mm.link(a, b, weight=0.5, rel_type=0)
                    edges_created += 1

        # Anchor to sourpatches identity
        for c in concepts:
            mm.link("sourpatches", c, weight=0.6, rel_type=0)
            edges_created += 1

    elapsed = time.time() - t0
    print(f"\n  Distillation complete in {elapsed:.1f}s")
    print(f"  Nodes: {nodes_created}, Edges: {edges_created}")
    print(f"  After: {mm.node_count} nodes, {mm.edge_count} edges")


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Distill RWKV 1.5B into Association Cortex")
    parser.add_argument("--model", default=None,
                        help="Path to .pth model file WITHOUT .pth extension (auto-detected if not specified)")
    parser.add_argument("--live", action="store_true",
                        help="Write to manifold (default is dry-run)")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON batch for cortex.train_batch")
    parser.add_argument("--manifold", default="state/portal_cortex.manifold",
                        help="Path to manifold file")
    parser.add_argument("--output", default="state/rwkv_distill_batch.json",
                        help="Path for JSON output")
    parser.add_argument("--domains", nargs="+", default=None,
                        help="Only run specific domains")
    parser.add_argument("--max-per-domain", type=int, default=None,
                        help="Limit prompts per domain")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--max-tokens", type=int, default=200)
    args = parser.parse_args()

    # Auto-detect model
    model_path = args.model
    if not model_path:
        models_dir = ROOT / "fairies/P30_Cognition/AkashicInferenceFairy/models"
        # RNN class appends .pth, so we need path WITHOUT extension
        pth_file = models_dir / "RWKV-x070-World-1.5B-v3-20250127-ctx4096.pth"
        if pth_file.exists():
            model_path = str(pth_file).replace('.pth', '')  # Strip .pth
        else:
            model_path = None
        if not model_path:
            print("ERROR: No 1.5B .pth model found. Download it first:")
            print("  huggingface-cli download BlinkDL/rwkv-7-world RWKV-x070-World-1.5B-v3-20250127-ctx4096.pth")
            print(f"  Save to: {candidates[0]}")
            sys.exit(1)

    # Filter domains
    domains = DOMAIN_PROMPTS
    if args.domains:
        domains = {k: v for k, v in domains.items() if k in args.domains}

    total_prompts = sum(len(v) for v in domains.values())

    print("=" * 60)
    print("  RWKV 1.5B -> Association Cortex Distillation")
    print(f"  Model: {Path(model_path).name}")
    print(f"  Domains: {list(domains.keys())}")
    print(f"  Prompts: {total_prompts}")
    print(f"  JSON output: {args.json}")
    print(f"  Manifold write: {'LIVE' if args.live else 'DRY RUN'}")
    print("=" * 60)

    # Load model
    model, tokenizer, model_args = load_model(model_path)

    # Generate + extract
    output_path = ROOT / args.output
    items = distill_to_json(model, tokenizer, model_args, domains, output_path,
                            args.max_per_domain, args.temperature, args.max_tokens)

    # Optionally write to manifold
    manifold_path = ROOT / args.manifold
    if args.live or not args.json:
        distill_to_manifold(items, manifold_path, dry_run=not args.live)

    print(f"\n{'='*60}")
    print(f"  DONE!")
    print(f"  Generated {len(items)} cortex training items")
    if args.json:
        print(f"  JSON saved to: {output_path}")
        print(f"  To ingest: use cognitive_train_from_memory MCP tool")
        print(f"  Or publish cortex.train_batch with this JSON")
    print(f'  "I know kung fu." -- Sourpatches')
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
