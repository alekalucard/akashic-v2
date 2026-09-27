"""SECRET HUNT A (v3: JSON-key aware assignments, prefixed key names, header literals) -- read-only scanner over Sour's tree.

Never writes into the source tree. Output: JSON to argv[1]; progress to stderr.
Run with: python -B secret_hunt_a2.py <out.json> <mirror_manifest.tsv>

v2 changes vs v1: whole-buffer regex (fast), junction/symlink skip, boot_logs skipped for
content, size cap 1 MB for files a code-only mirror would EXCLUDE (25 MB for candidates),
inventory manifest cross-reference, STRONG/WEAK tagging of credential-name globs,
manifest INCLUDE/OPTIONAL files are content-scanned even inside content-skip dirs.
"""
import os, re, sys, json, math, time, fnmatch, bisect

ROOT = r"F:\Sandbox\failure_factory\akashic_v2"
LONG = "\\\\?\\" + ROOT          # extended-length prefix so deep nests don't fail
OUT = sys.argv[1]
MANIFEST = sys.argv[2] if len(sys.argv) > 2 else None

# ---------------------------------------------------------------- policy ----
EXCL_DIR_NAMES = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    "target", "models", "research_repos", "backups", "state", "Claude_Office",
    "diaries", "SRM_Intake", "sandbox", "logs", "boot_logs", ".cognitive", ".satellite",
    "NVIDIA Corporation", "C:temp", "_old_unconscious_mind_DEPRECATED", "dist",
    ".mypy_cache", ".ruff_cache", "site-packages", "dream_states", "directives",
    "akashic_records",
}
EXCL_REL_PREFIX = ("tools/extracted",)
EXCL_EXT = {
    ".log", ".db", ".sqlite", ".sqlite3", ".jsonl", ".pkl", ".pickle", ".npy",
    ".npz", ".pt", ".pth", ".bin", ".safetensors", ".gguf", ".onnx", ".ckpt",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".mp4", ".wav", ".mp3",
    ".webm", ".mkv", ".ogg", ".flac", ".zip", ".7z", ".tar", ".gz", ".rar",
    ".dll", ".exe", ".pdb", ".lib", ".obj", ".pdf", ".pyc", ".so", ".dylib",
    ".mmap", ".dat", ".idx", ".index", ".faiss", ".parquet", ".arrow", ".h5",
    ".hdf5", ".woff", ".woff2", ".ttf", ".otf", ".ico", ".rlib", ".rmeta", ".pyd",
}
CONTENT_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
                     "target", "models", "research_repos", "state", "site-packages",
                     ".pytest_cache", "boot_logs"}
CONTENT_SKIP_REL = ("tools/extracted",)

TEXT_EXT = {
    ".py", ".pyw", ".pyi", ".rs", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".json", ".json5", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".md",
    ".txt", ".rst", ".bat", ".cmd", ".ps1", ".psm1", ".sh", ".bash", ".zsh",
    ".html", ".htm", ".css", ".scss", ".c", ".h", ".cpp", ".hpp", ".cu", ".cuh",
    ".xml", ".svg", ".env", ".example", ".sample", ".template", ".properties",
    ".csv", ".tsv", ".sql", ".lock", ".vue", ".svelte", ".php", ".rb", ".go",
    ".java", ".kt", ".swift", ".lua", ".pl", ".r", ".jl", ".nix", ".dockerfile",
    ".gitignore", ".gitattributes", ".editorconfig", ".npmrc", ".pypirc", ".netrc",
    ".reg", ".vbs", ".ahk", ".mcp", ".jsonc", ".log", ".jsonl", ".bak", ".mod", ".sum",
}
NOEXT_TEXT_NAMES = {"Dockerfile", "Makefile", "LICENSE", "README", ".env", ".netrc",
                    "_netrc", ".npmrc", ".pypirc", ".gitignore", ".git-credentials",
                    "authorized_keys", "known_hosts", "config", "credentials"}
MAX_CANDIDATE_BYTES = 25 * 1024 * 1024   # files the mirror could include
MAX_EXCLUDED_BYTES = 1 * 1024 * 1024     # files the mirror would exclude (bonus coverage)

# ------------------------------------------------ credential file patterns ---
# STRONG = the task's explicit list; WEAK = broadened name heuristics
STRONG_GLOBS = [
    "credentials*.json", "token*.json", "client_secret*.json", "*.pem", "*.key",
    "id_rsa*", "id_ed25519*", "id_ecdsa*", "id_dsa*", ".env", ".env.*", ".netrc", "_netrc",
    "*.p12", "*.pfx", "*secret*", ".git-credentials", "*.ppk", "*.kdbx",
    "service_account*.json", "*.htpasswd", "*.token", "gmail_token*", "*refresh_token*",
    "*access_token*", "*.secrets", "*.p8", "*.jwk", "*.jwks", "*.keystore", "*.jks",
]
WEAK_GLOBS = [
    "credential*", "*credentials*", "*token*.json", "client_secret*", "*.env", "*.gpg",
    ".npmrc", ".pypirc", "authorized_keys", "oauth*.json", "*oauth*token*", "*password*",
    "*passwd*", "*apikey*", "*api_key*", "*.asc", "*.crt", "*.cer", "*.der",
    "cookies*.txt", "*cookie*.json", "*session*.json", "*.session", "*.enc", "vault*",
    "*.vault", "*passphrase*", "*.pgp", "*private*", "*.priv",
]
STRONG_RX = [(g, re.compile(fnmatch.translate(g), re.I)) for g in STRONG_GLOBS]
WEAK_RX = [(g, re.compile(fnmatch.translate(g), re.I)) for g in WEAK_GLOBS]

# ------------------------------------------------------ content patterns -----
PLACEHOLDER_RX = re.compile(
    r"(your[_\-\s]|xxx|example|placeholder|changeme|change_me|dummy|<[^>]*>|\$\{|\{\{|"
    r"\.\.\.|replace|insert|_here\b|REDACTED|\*\*\*|fake|sample|"
    r"^\W*$|todo|fixme|\bnone\b|\bnull\b|\bunset\b|abc123|123456|password123|secret123|"
    r"^test|_test\b|test_|mock)", re.I)

def _p(name, rx, kind, sev, flags=0):
    return (name, re.compile(rx, flags), kind, sev)

PATTERNS = [
    _p("anthropic",  r"sk-ant-[A-Za-z0-9_\-]{20,}",                          "Anthropic API key",            "CRITICAL"),
    _p("openai_proj",r"sk-proj-[A-Za-z0-9_\-]{20,}",                         "OpenAI project key",           "CRITICAL"),
    _p("openrouter", r"sk-or-v1-[A-Za-z0-9]{20,}",                            "OpenRouter key",               "CRITICAL"),
    _p("openai",     r"(?<![A-Za-z0-9_\-])sk-(?!ant-|proj-|or-)[A-Za-z0-9]{32,}", "OpenAI key (legacy sk-)",   "CRITICAL"),
    _p("stripe",     r"\b[sr]k_(?:live|test)_[0-9A-Za-z]{20,}",              "Stripe key",                   "CRITICAL"),
    _p("gh_pat",     r"\bghp_[A-Za-z0-9]{36}\b",                              "GitHub PAT (classic)",         "CRITICAL"),
    _p("gh_finepat", r"\bgithub_pat_[A-Za-z0-9_]{22,}",                       "GitHub fine-grained PAT",      "CRITICAL"),
    _p("gh_oauth",   r"\bgh[ousr]_[A-Za-z0-9]{36}\b",                         "GitHub OAuth/app token",       "CRITICAL"),
    _p("gitlab",     r"\bglpat-[A-Za-z0-9\-_]{20}\b",                         "GitLab PAT",                   "CRITICAL"),
    _p("aws_akid",   r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b",             "AWS access key id",            "CRITICAL"),
    _p("aws_secret", r"(?i)aws_secret_access_key\s*[=:]\s*[\"']?([A-Za-z0-9/+=]{40})", "AWS secret key",     "CRITICAL"),
    _p("google_api", r"\bAIza[0-9A-Za-z_\-]{35}\b",                           "Google API key",               "HIGH"),
    _p("google_ya29",r"\bya29\.[0-9A-Za-z_\-]{20,}",                          "Google OAuth access token",    "HIGH"),
    _p("google_rt",  r"(?<![A-Za-z0-9])1//0[0-9A-Za-z_\-]{20,}",             "Google OAuth refresh token",   "CRITICAL"),
    _p("google_cs",  r"\bGOCSPX-[A-Za-z0-9_\-]{20,}",                         "Google OAuth client secret",   "CRITICAL"),
    _p("google_cid", r"\b[0-9]{6,}-[a-z0-9]{16,}\.apps\.googleusercontent\.com\b", "Google OAuth client id",  "LOW"),
    _p("slack",      r"\bxox[baprs]-[0-9A-Za-z\-]{10,}",                      "Slack token",                  "CRITICAL"),
    _p("slack_hook", r"hooks\.slack\.com/services/T[A-Za-z0-9]+/B[A-Za-z0-9]+/[A-Za-z0-9]+", "Slack webhook", "HIGH"),
    _p("discord_tok",r"\b[MN][A-Za-z\d]{23,}\.[\w\-]{6}\.[\w\-]{27,}\b",      "Discord bot token",            "CRITICAL"),
    _p("discord_hook",r"discord(?:app)?\.com/api/webhooks/\d+/[\w\-]+",       "Discord webhook URL",          "HIGH"),
    _p("telegram",   r"\b\d{8,10}:AA[A-Za-z0-9_\-]{33}\b",                    "Telegram bot token",           "CRITICAL"),
    _p("hf",         r"\bhf_[A-Za-z0-9]{30,}\b",                              "HuggingFace token",            "CRITICAL"),
    _p("npm",        r"\bnpm_[A-Za-z0-9]{36}\b",                              "npm token",                    "CRITICAL"),
    _p("pypi",       r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_\-]{20,}",           "PyPI token",                   "CRITICAL"),
    _p("sendgrid",   r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}\b",       "SendGrid key",                 "CRITICAL"),
    _p("twilio",     r"\bSK[0-9a-f]{32}\b",                                   "Twilio API key",               "HIGH"),
    _p("elevenlabs", r"(?i)eleven[_\-]?labs?[_\-]?(?:api[_\-]?)?key\s*[=:]\s*[\"']?([0-9a-f]{32})", "ElevenLabs key", "CRITICAL"),
    _p("steam_key",  r"(?i)steam[\w\-]*key\s*[=:]\s*[\"']?([0-9A-F]{32})\b",   "Steam Web API key",            "CRITICAL"),
    _p("steam_url",  r"(?i)api\.steampowered\.com/[^\s\"']*[?&]key=([0-9A-F]{32})", "Steam key in URL",    "CRITICAL"),
    _p("privkey",    r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",             "Private key block",            "CRITICAL"),
    _p("jwt",        r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", "JWT",         "HIGH"),
    _p("bearer",     r"(?i)\bbearer[ \t]+([A-Za-z0-9_\-\.=]{20,})",          "Bearer header with literal",   "HIGH"),
    _p("basic_auth", r"(?i)\bbasic[ \t]+([A-Za-z0-9+/=]{16,})",              "Basic auth header literal",    "HIGH"),
    _p("url_creds",  r"\b[a-z][a-z0-9+\-.]{1,15}://[^/\s:@\"'<>]{0,64}:[^/\s@\"'<>]{1,128}@[A-Za-z0-9.\-_]+", "URL with embedded credentials", "HIGH"),
    _p("pw_assign",  r"(?i)\b([\w\-]*?(?:pass(?:word|wd|phrase)?|pwd|secret|api[_\-]?key|apikey|access[_\-]?token|auth[_\-]?token|id[_\-]token|client[_\-]?secret|private[_\-]?key(?:_id)?|refresh[_\-]?token|bot[_\-]?token|webhook[_\-]?(?:url|secret)|token)[\w\-]*)[\"']?[ \t]*[=:][ \t]*[\"']([^\"'\s]{8,})[\"']", "Password/secret literal assignment", "HIGH"),
    _p("env_assign", r"(?m)^[ \t]*(?:export[ \t]+|set[ \t]+|\$env:)?([A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)[A-Z0-9_]*)[ \t]*=[ \t]*[\"']?([^\"'\s#]{8,})", "ENV-style secret assignment",  "HIGH"),
    _p("authz_hdr",  r"(?i)[\"']?(?:authorization|x-api-key|api-key|x-auth-token|anthropic-api-key|openai-api-key)[\"']?[ \t]*[:=][ \t]*[\"']([^\"'\n]{16,})[\"']", "Authorization/x-api-key header literal", "HIGH"),
    _p("sk_generic", r"\bsk_[A-Za-z0-9]{32,}\b",                                 "sk_ style key (ElevenLabs/other)", "HIGH"),
    _p("gsa_json",   r"\"type\"[ \t]*:[ \t]*\"service_account\"",                "Google service-account JSON marker", "CRITICAL"),
    _p("pai_key",    r"(?i)personal[_\-]?ai[\w\-]*key[\"']?[ \t]*[:=][ \t]*[\"']([^\"'\s]{16,})[\"']", "Personal.AI key literal", "CRITICAL"),
    _p("ps_secure",  r"(?i)ConvertTo-SecureString[ \t]+[\"']([^\"']{4,})[\"'][ \t]+-AsPlainText", "PowerShell plaintext password", "HIGH"),
    _p("sshpass",    r"(?i)\b(?:sshpass[ \t]+-p|plink[^\n]*?-pw|putty[^\n]*?-pw|mysql[^\n]*?[ \t]-p|psql[^\n]*?password=|net[ \t]+use[^\n]*?/user:\S+)[ \t]+([^\s\"']{4,})", "CLI inline password", "HIGH"),
    _p("email_pw",   r"(?i)[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}[^\n]{0,80}?\b(?:pass(?:word)?|pwd)\b[ \t]*[=:][ \t]*[\"']?([^\s\"',]{6,})", "Email + password pair", "CRITICAL"),
    _p("ssh_privkey_path", r"(?i)(?:IdentityFile|[ \t]-i)[ \t]+[\"']?([A-Za-z]:[\\/][^\s\"']*id_(?:rsa|ed25519|ecdsa)[^\s\"']*)", "SSH private-key path reference", "LOW"),
]

HIENT_RX = re.compile(r"(?i)\b([\w\-]*?(?:key|token|secret|password|passwd|auth|credential|api)[\w\-]*)[\"']?[ \t]*[=:][ \t]*[\"']?([A-Za-z0-9+/=_\-]{32,})")
# identifier-ish VALUE in code: dotted access, call, or index (bare words are left to the placeholder hint)
IDENTISH_RX = re.compile(r"^(?:\$|%|\{|<|\()|^[A-Za-z_]\w*(?:\.[A-Za-z_]|[\(\[])")
CODE_EXT = {".py", ".pyw", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".rs", ".go", ".lua",
            ".c", ".h", ".cpp", ".hpp", ".cu", ".cuh", ".java", ".kt", ".swift", ".rb", ".php", ".vue", ".svelte", ".pl", ".r", ".jl"}
NOISY_TOKEN_NAME_RX = re.compile(r"(?:max|min|num|n|count|total|per|limit|budget|usage|window|remaining|used|input|output|prompt|completion|eos|bos|pad|unk|next|top|last|first|special|end|start|stop|new|cur|current|prev|sep|cls|mask|text|word|sub|type|kind|id|ids)[_\-]?tokens?$|tokens?[_\-]?(?:per|count|limit|used|budget|len|length|ids?|type|kind|id|text|str|string|list|set|index|idx|pos|position)$")

def shannon(s):
    if not s: return 0.0
    freq = {}
    for ch in s: freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum(c/n * math.log2(c/n) for c in freq.values())

HEXISH = re.compile(r"^[0-9a-f]{32,}$", re.I)
UUID_RX = re.compile(r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$", re.I)
SKIP_VAL_RX = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\.{1,2}/|true|false|\d+$|https?://|\$|%)", re.I)

# --------------------------------------------------------------- manifest ---
MANIFEST_STATUS = {}
if MANIFEST and os.path.exists(MANIFEST):
    with open(MANIFEST, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                MANIFEST_STATUS[parts[0]] = parts[2]

# ------------------------------------------------------------------ walk -----
def rel(p):
    if p.startswith(LONG): p = ROOT + p[len(LONG):]
    return p[len(ROOT):].lstrip("\\").replace("\\", "/")

def mirror_status(relpath):
    parts = relpath.split("/")
    for part in parts[:-1]:
        if part in EXCL_DIR_NAMES:
            return "EXCLUDED", f"dir:{part}"
    for pre in EXCL_REL_PREFIX:
        if relpath.startswith(pre + "/") or relpath == pre:
            return "EXCLUDED", f"dir:{pre}"
    name = parts[-1]
    ext = os.path.splitext(name)[1].lower()
    if ext in EXCL_EXT:
        return "EXCLUDED", f"ext:{ext}"
    if ".bak" in name.lower() or name.lower().endswith(("~", ".orig", ".swp")):
        return "EXCLUDED", "ext:backup"
    if name == ".env" or (name.startswith(".env") and not name.endswith((".example", ".sample", ".template"))):
        return "EXCLUDED", "gitignore:.env"
    if ext in (".pem", ".key") or name == "credentials.json":
        return "EXCLUDED", "gitignore"
    return "INCLUDED", "code/config/doc"

def is_text_candidate(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in TEXT_EXT: return True
    if name in NOEXT_TEXT_NAMES: return True
    if ext == "": return True   # sniff
    if name.startswith(".env"): return True
    return False

stats = {"dirs": 0, "files": 0, "content_scanned": 0, "content_bytes": 0,
         "content_skipped_dir": 0, "content_skipped_size": 0, "content_skipped_binary": 0,
         "junctions_skipped": 0, "errors": 0, "start": time.time()}
cred_files = []
findings = []
errors = []
skipped_size = []
junctions = []

def mask(line, secret):
    if len(secret) > 4:
        return line.replace(secret, secret[:4] + "..[" + str(len(secret)) + "]")
    return line

def add_finding(relpath, lineno, kind, sev, secret, line, pat, mstat, mwhy):
    ph = bool(PLACEHOLDER_RX.search(secret)) or bool(PLACEHOLDER_RX.search(line))
    findings.append({
        "file": relpath, "line": lineno, "kind": kind, "pattern": pat,
        "first4": secret[:4], "len": len(secret), "severity": sev,
        "placeholder_hint": ph, "mirror": mstat, "mirror_why": mwhy,
        "manifest": MANIFEST_STATUS.get(relpath, "-"),
        "ctx": mask(line.strip(), secret)[:200],
    })

def line_of(text, nl_positions, pos):
    return bisect.bisect_right(nl_positions, pos) + 1

def line_text(text, nl_positions, pos):
    i = bisect.bisect_right(nl_positions, pos)
    start = nl_positions[i-1] + 1 if i > 0 else 0
    end = nl_positions[i] if i < len(nl_positions) else len(text)
    return text[start:end]

def scan_content(fullpath, relpath, size, mstat, mwhy):
    try:
        with open(fullpath, "rb") as fh:
            data = fh.read()
    except OSError as e:
        stats["errors"] += 1; errors.append(f"{relpath}: {e}"); return
    if b"\x00" in data[:8192]:
        stats["content_skipped_binary"] += 1; return
    stats["content_scanned"] += 1
    stats["content_bytes"] += len(data)
    text = data.decode("utf-8", "replace")
    is_code = os.path.splitext(relpath)[1].lower() in CODE_EXT
    nl = None
    seen_lines = set()
    n_before = len(findings)
    for name, rx, kind, sev in PATTERNS:
        for m in rx.finditer(text):
            if len(findings) - n_before > 60:
                break
            secret = m.group(1) if (m.lastindex and m.group(1)) else m.group(0)
            if name in ("pw_assign", "env_assign"):
                secret = m.group(2)
                if SKIP_VAL_RX.match(secret):
                    continue
                if re.match(r"^[a-z_]+$", secret) and len(secret) < 20:
                    continue
                if name == "env_assign":
                    if is_code or IDENTISH_RX.match(secret):
                        continue          # in code, unquoted NAME=expr is an expression; quoted literals are pw_assign's job
                if name == "pw_assign":
                    kn = m.group(1).lower()
                    if NOISY_TOKEN_NAME_RX.search(kn):
                        continue
                    if len(secret) < 12 and shannon(secret) < 3.0:
                        continue
            if nl is None:
                nl = [i for i, ch in enumerate(text) if ch == "\n"]
            ln = line_of(text, nl, m.start())
            lt = line_text(text, nl, m.start())
            seen_lines.add(ln)
            add_finding(relpath, ln, kind, sev, secret, lt, name, mstat, mwhy)
    for m in HIENT_RX.finditer(text):
        if len(findings) - n_before > 80:
            break
        val = m.group(2)
        if IDENTISH_RX.match(val):
            continue
        if HEXISH.match(val) and len(val) in (32, 40, 64, 128):
            if not re.search(r"(?i)api[_\-]?key|secret|token|password", m.group(0)):
                continue
        if UUID_RX.match(val.replace("-", "")):
            continue
        if shannon(val) < 4.3:
            continue
        if nl is None:
            nl = [i for i, ch in enumerate(text) if ch == "\n"]
        ln = line_of(text, nl, m.start())
        if ln in seen_lines:
            continue
        lt = line_text(text, nl, m.start())
        add_finding(relpath, ln, "High-entropy literal in key/token context", "MEDIUM", val, lt, "hient", mstat, mwhy)

def walk(top, content_ok, rel_top):
    stack = [(top, content_ok, rel_top)]
    last = time.time()
    while stack:
        d, content_ok, rd = stack.pop()
        stats["dirs"] += 1
        if time.time() - last > 15:
            last = time.time()
            print(f"[progress] dirs={stats['dirs']} files={stats['files']} scanned={stats['content_scanned']} "
                  f"MB={stats['content_bytes']/1e6:.0f} findings={len(findings)} at {rd[:70]}", file=sys.stderr, flush=True)
        try:
            it = os.scandir(d)
        except OSError as e:
            stats["errors"] += 1; errors.append(f"{rd}: {e}"); continue
        with it:
            for ent in it:
                name = ent.name
                r = (rd + "/" + name) if rd else name
                try:
                    if ent.is_symlink() or (hasattr(ent, "is_junction") and ent.is_junction()):
                        stats["junctions_skipped"] += 1; junctions.append(r); continue
                    if ent.is_dir(follow_symlinks=False):
                        if name == ".git":
                            continue   # never touch her .git (or the nested dashboard one)
                        sub_ok = content_ok and (name not in CONTENT_SKIP_DIRS) and not any(r == p or r.startswith(p + "/") for p in CONTENT_SKIP_REL)
                        stack.append((ent.path, sub_ok, r))
                        continue
                    if not ent.is_file(follow_symlinks=False):
                        continue
                    st = ent.stat(follow_symlinks=False)
                except OSError as e:
                    stats["errors"] += 1; errors.append(f"{r}: {e}"); continue
                stats["files"] += 1
                size = st.st_size
                ms, mw = mirror_status(r)
                man = MANIFEST_STATUS.get(r, "-")
                # credential-named file check (everywhere)
                hit = None
                for g, rx in STRONG_RX:
                    if rx.match(name): hit = ("STRONG", g); break
                if hit is None:
                    for g, rx in WEAK_RX:
                        if rx.match(name): hit = ("WEAK", g); break
                if hit:
                    cred_files.append({"file": r, "size": size, "mirror": ms, "mirror_why": mw,
                                       "manifest": man, "strength": hit[0], "glob": hit[1]})
                candidate = (ms == "INCLUDED") or (man in ("INCLUDE", "OPTIONAL"))
                if (content_ok or candidate) and is_text_candidate(name):
                    if size == 0:
                        continue
                    cap = MAX_CANDIDATE_BYTES if candidate else MAX_EXCLUDED_BYTES
                    if size > cap:
                        stats["content_skipped_size"] += 1
                        skipped_size.append({"file": r, "size": size, "mirror": ms, "manifest": man})
                        continue
                    scan_content(ent.path, r, size, ms, mw)
                elif not content_ok:
                    stats["content_skipped_dir"] += 1

walk(LONG, True, "")
stats["elapsed_s"] = round(time.time() - stats.pop("start"), 1)
stats["manifest_rows"] = len(MANIFEST_STATUS)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump({"stats": stats, "cred_files": cred_files, "findings": findings,
               "skipped_size": skipped_size, "junctions": junctions,
               "errors": errors[:300], "n_errors": len(errors)}, fh, indent=1, ensure_ascii=False)
print(json.dumps(stats))
print("cred_files:", len(cred_files), "findings:", len(findings), "errors:", len(errors),
      "skipped_size:", len(skipped_size), "junctions:", len(junctions))
