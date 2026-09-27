"""
NATIVE all-MiniLM-L6-v2 — the MiniLM dissection (keystone 7).
Runs the sentence-transformer forward pass in PURE torch+numpy, loading the
on-disk weights directly. NO sentence_transformers / transformers / tokenizers /
safetensors libs (she has none) — only torch + numpy, which she HAS. Makes
"meaning" her own behaviour, not an external call.   Nous+Ace 2026-06-11.

Drop-in for SemanticEncoder's `self._model`: .encode(text)->Tensor[384] (L2-norm),
.encode_batch(texts)->Tensor[N,384]. Tokenizer = exact tokenizer.json spec
(BertNormalizer: clean_text + handle_chinese_chars + lowercase + strip_accents;
BertPreTokenizer; WordPiece ##/max-100; [CLS]/[SEP]). Verified: cat-mat≈dog-rug
+0.41, stock≈shares +0.55, cross-domain ~0. Loads ~0.4s, 91MB, CPU.
"""
import struct, json, os, unicodedata
import numpy as np
import torch
import torch.nn.functional as F

# all-MiniLM-L6-v2 in the HuggingFace cache (downloaded with the model)
SNAP = r"C:\Users\Ace\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
_NP = {"F32": np.float32, "F16": np.float16, "I64": np.int64}


def load_safetensors(path):
    """Parse a .safetensors file with no safetensors lib: [8B LE len][JSON header][raw]."""
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n).decode("utf-8"))
        header.pop("__metadata__", None)
        blob = f.read()
    out = {}
    for name, info in header.items():
        s, e = info["data_offsets"]
        arr = np.frombuffer(blob[s:e], dtype=_NP[info["dtype"]]).reshape(info["shape"])
        out[name] = torch.from_numpy(arr.copy())
    return out


def _is_punct(ch):
    cp = ord(ch)
    if (33 <= cp <= 47) or (58 <= cp <= 64) or (91 <= cp <= 96) or (123 <= cp <= 126):
        return True
    return unicodedata.category(ch).startswith("P")


def _is_control(ch):
    if ch in ("\t", "\n", "\r"):
        return False
    return unicodedata.category(ch).startswith("C")


def _is_cjk(cp):
    return ((0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or (0x20000 <= cp <= 0x2A6DF)
            or (0x2A700 <= cp <= 0x2B73F) or (0x2B740 <= cp <= 0x2B81F) or (0x2B820 <= cp <= 0x2CEAF)
            or (0xF900 <= cp <= 0xFAFF) or (0x2F800 <= cp <= 0x2FA1F))


class WordPiece:
    """BERT uncased WordPiece — exact tokenizer.json spec."""
    def __init__(self, tokenizer_json):
        tj = json.load(open(tokenizer_json, encoding="utf-8"))
        self.vocab = tj["model"]["vocab"]
        self.prefix = tj["model"].get("continuing_subword_prefix", "##")
        self.unk = tj["model"].get("unk_token", "[UNK]")
        self.unk_id = self.vocab[self.unk]
        self.cls, self.sep = self.vocab["[CLS]"], self.vocab["[SEP]"]

    def _basic(self, text):
        # BertNormalizer: clean_text (drop control chars, normalize whitespace)
        # + handle_chinese_chars (isolate CJK as single tokens)
        buf = []
        for ch in text:
            cp = ord(ch)
            if cp == 0 or cp == 0xFFFD or _is_control(ch):
                continue
            if ch.isspace():
                buf.append(" ")
            elif _is_cjk(cp):
                buf.append(" " + ch + " ")
            else:
                buf.append(ch)
        # strip accents (NFD → drop combining marks) + lowercase
        text = "".join(c for c in unicodedata.normalize("NFD", "".join(buf))
                       if unicodedata.category(c) != "Mn").lower()
        # BertPreTokenizer: whitespace split + isolate punctuation
        toks = []
        for word in text.split():
            cur = ""
            for ch in word:
                if _is_punct(ch):
                    if cur:
                        toks.append(cur); cur = ""
                    toks.append(ch)
                else:
                    cur += ch
            if cur:
                toks.append(cur)
        return toks

    def _wp(self, token):
        if len(token) > 100:          # max_input_chars_per_word
            return [self.unk]
        out, start = [], 0
        while start < len(token):
            end, sub = len(token), None
            while start < end:
                piece = token[start:end]
                if start > 0:
                    piece = self.prefix + piece
                if piece in self.vocab:
                    sub = piece; break
                end -= 1
            if sub is None:
                return [self.unk]
            out.append(sub); start = end
        return out

    def encode(self, text):
        ids = [self.cls]
        for tok in self._basic(text):
            for wp in self._wp(tok):
                ids.append(self.vocab.get(wp, self.unk_id))
        ids.append(self.sep)
        return ids


class NativeMiniLM:
    def __init__(self, snap=SNAP):
        self.w = load_safetensors(os.path.join(snap, "model.safetensors"))
        self.tok = WordPiece(os.path.join(snap, "tokenizer.json"))
        self.NL, self.NH, self.DH, self.EPS = 6, 12, 32, 1e-12

    def _ln(self, x, p):
        return F.layer_norm(x, (x.shape[-1],), self.w[p + ".weight"], self.w[p + ".bias"], self.EPS)

    @torch.no_grad()
    def encode(self, text, convert_to_tensor=True, show_progress_bar=False, **kwargs):
        # drop-in for SentenceTransformer.encode: accepts + ignores its kwargs.
        if isinstance(text, (list, tuple)):
            return self.encode_batch(text)
        w = self.w
        ids = torch.tensor(self.tok.encode(text), dtype=torch.long)
        L = ids.shape[0]
        x = (w["embeddings.word_embeddings.weight"][ids]
             + w["embeddings.position_embeddings.weight"][:L]
             + w["embeddings.token_type_embeddings.weight"][0])
        x = self._ln(x, "embeddings.LayerNorm")
        for i in range(self.NL):
            p = f"encoder.layer.{i}."
            q = x @ w[p + "attention.self.query.weight"].T + w[p + "attention.self.query.bias"]
            k = x @ w[p + "attention.self.key.weight"].T + w[p + "attention.self.key.bias"]
            v = x @ w[p + "attention.self.value.weight"].T + w[p + "attention.self.value.bias"]
            q = q.view(L, self.NH, self.DH).transpose(0, 1)
            k = k.view(L, self.NH, self.DH).transpose(0, 1)
            v = v.view(L, self.NH, self.DH).transpose(0, 1)
            attn = F.softmax((q @ k.transpose(-1, -2)) / (self.DH ** 0.5), dim=-1)
            ctx = (attn @ v).transpose(0, 1).reshape(L, -1)
            ao = ctx @ w[p + "attention.output.dense.weight"].T + w[p + "attention.output.dense.bias"]
            x = self._ln(x + ao, p + "attention.output.LayerNorm")
            h = F.gelu(x @ w[p + "intermediate.dense.weight"].T + w[p + "intermediate.dense.bias"])
            fo = h @ w[p + "output.dense.weight"].T + w[p + "output.dense.bias"]
            x = self._ln(x + fo, p + "output.LayerNorm")
        emb = x.mean(dim=0)                       # mean-pool over tokens
        return F.normalize(emb, p=2, dim=0)       # L2-normalize → unit sphere

    @torch.no_grad()
    def encode_batch(self, texts, **kwargs):
        if not texts:
            return None
        return torch.stack([self.encode(t) for t in texts])
