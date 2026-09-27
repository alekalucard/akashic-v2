"""rescan_b.py -- re-run SECRET HUNT B's patterns over the STAGED mirror (or any directory / file list).
Read-only. Prints file:line, kind, first 4 chars, length, entropy -- never a full value.

    python -B rescan_b.py <root>                  scan every text file under <root> (skips .git)
    git ls-files -z | python -B rescan_b.py --stdin0 [--all]
    python -B rescan_b.py --index [--all]         scan the STAGED blobs (git index vs HEAD, ACMR)
    python -B rescan_b.py --index-all [--all]     scan EVERY blob in the git index

Hard findings (exit 1): the 23 known token formats from hunt_b.py, plus the two exact shapes of the credentials
found in her tree (`sk-ant-...` Anthropic, `-2oO` + 28 url-safe chars Personal.AI), plus a context-word quoted
assignment whose value is not a placeholder / identifier / path and has Shannon entropy >= 4.0 and length >= 16.
`--all` also prints the lower-confidence context rows that the filters dropped, for a hand look.
"""
import os, re, sys, math
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KNOWN = [
    ("Anthropic key", re.compile(r"sk-ant-(?:api|admin)?[0-9A-Za-z_-]{20,}")),
    ("Anthropic key shape (found in her tree)", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("Personal.AI key shape (found in her tree)", re.compile(r"-2oO[A-Za-z0-9_-]{28}")),
    ("OpenAI key", re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Google OAuth client secret", re.compile(r"\bGOCSPX-[0-9A-Za-z_-]{20,}")),
    ("Google OAuth client id", re.compile(r"\b[0-9]{6,}-[0-9a-z]{20,}\.apps\.googleusercontent\.com\b")),
    ("Google refresh token", re.compile(r"\b1//0[0-9A-Za-z_-]{20,}")),
    ("Google access token", re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}")),
    ("Discord token", re.compile(r"\b[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}")),
    ("Discord webhook", re.compile(r"discord(?:app)?\.com/api/webhooks/\d+/[\w-]{20,}")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("HuggingFace token", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("Telegram bot token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("Stripe key", re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[0-9A-Za-z]{20,}")),
    ("SendGrid key", re.compile(r"\bSG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")),
    ("Twilio key", re.compile(r"\bSK[0-9a-f]{32}\b")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("PyPI token", re.compile(r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{20,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY")),
    ("bearer header", re.compile(r"[Bb]earer\s+([A-Za-z0-9._~+/=-]{20,})")),
    ("URL with embedded credentials", re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://([^/\s:@'\"]{1,64}):([^/\s@'\"]{1,128})@[A-Za-z0-9.-]+")),
]
CTX_WORDS = re.compile(r"(?i)\b(?:api[_-]?key|apikey|key|token|secret|password|passwd|pwd|auth|credential|"
                       r"bearer|cookie|session|client_id|client_secret|refresh|webhook|access[_-]?key|"
                       r"private[_-]?key|signing|salt|passphrase)\b")
ASSIGN = re.compile(r"""(?P<name>[A-Za-z_][A-Za-z0-9_.\-\[\]'" ]{0,60}?)\s*[:=]\s*(?:r|b|f|u)?(?P<q>["'])(?P<val>(?:(?!(?P=q)).){6,})(?P=q)""")
ENV_KV = re.compile(r"""^\s*(?:set\s+|export\s+|\$env:)?(?P<name>[A-Za-z_][A-Za-z0-9_]{1,60})\s*=\s*(?P<val>[^\s"'#;][^\s#;]{5,})\s*$""")
PLACEHOLDER = re.compile(r"(?i)(?:your[_ -]|xxx|<[^>]+>|\$\{|%[A-Z_]+%|os\.environ|getenv|example|placeholder|"
                         r"changeme|change_me|dummy|redacted|\.\.\.|insert|todo|fixme|replace|sample|"
                         r"^none$|^null$|^true$|^false$|^\s*$|^\*+$|^_+$|not[_ -]?set|missing|unknown|_here\b|test)")
CODEY = re.compile(r"[\s(){};]|\\n|\\t|->|=>|::|\bself\b|\bdef\b|\breturn\b|\bimport\b|\{\}|%s|%d|\{[a-z_]+\}")
IDENTISH = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")          # dotted identifier / module path / tensor name
PATHISH = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\.{1,2}/|https?://|[A-Za-z0-9_\-]+(?:[\\/][A-Za-z0-9_.\-]+)+$)")
HEX = re.compile(r"^[0-9a-fA-F]+$")
UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

TEXT_EXT = {".py", ".pyi", ".pyx", ".rs", ".js", ".mjs", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml", ".ini",
            ".cfg", ".conf", ".md", ".txt", ".bat", ".cmd", ".ps1", ".psm1", ".psd1", ".sh", ".html", ".htm", ".css",
            ".c", ".h", ".cpp", ".hpp", ".cu", ".cuh", ".sql", ".lock", ".lua", ".go", ".mod", ".sum", ".vbs", ".mermaid",
            ".mmd", ".svg", ".example", ".gitignore", ".gitattributes", ".editorconfig", ".env", ".xml", ".csv", ".tsv"}


def shannon(s):
    if not s:
        return 0.0
    c = Counter(s)
    n = len(s)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def is_text(name):
    ext = os.path.splitext(name)[1].lower()
    return ext in TEXT_EXT or ext == "" or name.startswith(".env")


def scan(path, rel, hard, soft):
    try:
        data = open(path, "rb").read()
    except OSError as e:
        print("ERR", rel, e)
        return
    scan_data(data, rel, hard, soft)


def scan_data(data, rel, hard, soft):
    if not data or b"\x00" in data[:8192]:
        return
    text = data.decode("utf-8", "replace")
    seen = set()
    for i, line in enumerate(text.split("\n"), 1):
        for kind, rx in KNOWN:
            for m in rx.finditer(line):
                v = m.group(1) if m.groups() and m.group(1) else m.group(0)
                if kind == "OpenAI key" and v.startswith("sk-ant-"):
                    continue
                if kind == "URL with embedded credentials":
                    pw = m.group(2)
                    if PLACEHOLDER.search(pw) or pw in ("password", "pass", "pw"):
                        continue
                    v = pw
                if kind == "bearer header" and PLACEHOLDER.search(v):
                    continue
                key = (i, kind, v[:4])
                if key in seen:
                    continue
                seen.add(key)
                hard.append((rel, i, kind, v[:4], len(v), shannon(v)))
        if len(line) > 4000 or not CTX_WORDS.search(line):
            continue
        cands = [(m.group("name").strip(), m.group("val"), m.start()) for m in ASSIGN.finditer(line)]
        mk = ENV_KV.match(line)
        if mk:
            cands.append((mk.group("name"), mk.group("val"), mk.start()))
        for name, val, pos in cands:
            if not (CTX_WORDS.search(name) or CTX_WORDS.search(line[:pos])):
                continue
            reason = None
            if PLACEHOLDER.search(val) or PLACEHOLDER.search(line):
                reason = "placeholder"
            elif CODEY.search(val):
                reason = "code-shaped"
            elif IDENTISH.match(val):
                reason = "identifier/dotted"
            elif PATHISH.match(val):
                reason = "path/url"
            elif UUID.match(val):
                reason = "uuid"
            elif len(val) < 16:
                reason = "short"
            elif shannon(val) < 4.0:
                reason = "low entropy"
            elif HEX.match(val) and len(val) in (32, 40, 64, 128) and not re.search(r"(?i)api[_\-]?key|secret|token|password", name):
                reason = "hex digest, non-credential name"
            row = (rel, i, f"context assignment `{name[:40]}`", val[:4], len(val), shannon(val))
            if reason is None:
                hard.append(row)
            else:
                soft.append(row + (reason,))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    hard, soft = [], []
    nonblob = []
    n = 0
    if "--index" in sys.argv or "--index-all" in sys.argv:
        from gitindex import repo_root, staged_paths, index_blobs
        repo = repo_root(HERE)
        paths = staged_paths(repo, all_tracked="--index-all" in sys.argv)
        listed = len(paths)
        where = f"git index of {repo} ({'all' if '--index-all' in sys.argv else 'staged'})"
        for rel, mode, data in index_blobs(repo, paths):
            if data is None:
                nonblob.append((rel, mode))
                continue
            if is_text(os.path.basename(rel)):
                n += 1
                scan_data(data, rel, hard, soft)
    else:
        files = []
        if "--stdin0" in sys.argv:
            raw = sys.stdin.buffer.read().decode("utf-8", "replace")
            root = args[0] if args else os.getcwd()
            files = [(os.path.join(root, p), p) for p in raw.split("\0") if p]
        else:
            root = args[0]
            for dp, dns, fns in os.walk(root):
                dns[:] = [d for d in dns if d != ".git"]
                for fn in fns:
                    p = os.path.join(dp, fn)
                    files.append((p, os.path.relpath(p, root).replace("\\", "/")))
        listed = len(files)
        where = root
        for p, rel in files:
            if is_text(os.path.basename(p)) and os.path.isfile(p):
                n += 1
                scan(p, rel, hard, soft)
    print(f"[rescan_b] scanned {n} text files ({listed} listed) -- {where}")
    print(f"[rescan_b] HARD findings (known formats, the two known key shapes, un-filtered context literals): {len(hard)}")
    for rel, ln, kind, f4, L, H in sorted(hard):
        print(f"  {rel}:{ln}  {kind}  first4={f4!r} len={L} H={H:.2f}")
    print(f"[rescan_b] soft rows (context assignments dropped by a filter): {len(soft)}")
    if show_all:
        for rel, ln, kind, f4, L, H, why in sorted(soft):
            print(f"  {rel}:{ln}  {kind}  first4={f4!r} len={L} H={H:.2f}  [{why}]")
    if nonblob:
        print(f"[rescan_b] index entries that are NOT plain blobs (gitlink/missing): {len(nonblob)}")
        for rel, mode in nonblob:
            print(f"  {rel}  mode={mode}")
    sys.exit(1 if (hard or nonblob) else 0)


if __name__ == "__main__":
    main()
