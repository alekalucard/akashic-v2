"""hunt_a_patterns.py -- SECRET HUNT A pattern set (known token/key formats + assignment/header
literals + credential-file name globs), extracted from the scanner so the Builder/Skeptic can
re-run the exact same patterns on the STAGED mirror.  Import and use PATTERNS, HIENT_RX,
SKIP_VAL_RX, IDENTISH_RX, NOISY_TOKEN_NAME_RX, CODE_EXT, TEXT_EXT, STRONG_RX, WEAK_RX, shannon().
Nothing here prints or stores a full secret value.
"""
import os, re, sys, json, math, time, fnmatch, bisect


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

