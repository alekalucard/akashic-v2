"""rescan_skeptic.py -- the SKEPTIC's independent secret scan (2026-09-26 review of commit 8ba060b), patterns
copied VERBATIM from the skeptic's scan.py, pointed at the git index through gitindex.py so it runs on exactly
the blobs a commit would contain. Never prints a value beyond its first 4 characters.

    python -B rescan_skeptic.py --index-all [--all]     every blob in the index (default)
    python -B rescan_skeptic.py --index     [--all]     only the staged blobs (index vs HEAD, ACMR)

Exit 1 when: any HARD pattern hit that is not in TRIAGED_HARD, any base64 blob >= 40 chars that decodes to
printable text containing credential words, or any index entry that is not a plain blob (gitlink / missing).
The other sections (credential-named literal assignments, high-entropy literals, IPs, e-mail shapes) are
INFORMATIONAL: printed as counts (rows with --all) for a hand look, exactly as the skeptic used them.
"""
import base64, math, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from gitindex import repo_root, staged_paths, index_blobs


def ent(s):
    c = collections.Counter(s); n = len(s)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def m4(s):
    return f"{s[:4]!r}..len{len(s)}"


# ---- verbatim from the skeptic's scan.py --------------------------------------------------------------------
PATS = [
    ("aws_akid", r"\b(AKIA|ASIA|AGPA|AIDA|AROA|ANPA)[A-Z0-9]{16}\b"),
    ("aws_secret", r"(?i)aws.{0,20}(secret|key).{0,5}[:=]\s*['\"]?([A-Za-z0-9/+]{40})"),
    ("github", r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}"),
    ("slack", r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    ("slack_webhook", r"hooks\.slack\.com/services/[A-Za-z0-9/]{20,}"),
    ("discord_webhook", r"discord(app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]{20,}"),
    ("discord_token", r"\b[MNO][A-Za-z\d]{23,25}\.[\w-]{6}\.[\w-]{27,38}\b"),
    ("telegram", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    ("google_api", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("google_oauth_secret", r"GOCSPX-[A-Za-z0-9_-]{20,}"),
    ("google_client", r"\d{10,}-[a-z0-9]{32}\.apps\.googleusercontent\.com"),
    ("openai", r"\bsk-(proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}"),
    ("anthropic", r"sk-ant-[A-Za-z0-9_-]{10,}"),
    ("stripe", r"\b(sk|rk|pk)_(live|test)_[A-Za-z0-9]{16,}"),
    ("hf", r"\bhf_[A-Za-z0-9]{30,}"),
    ("replicate", r"\br8_[A-Za-z0-9]{30,}"),
    ("groq", r"\bgsk_[A-Za-z0-9]{30,}"),
    ("xai", r"\bxai-[A-Za-z0-9]{30,}"),
    ("sendgrid", r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),
    ("twilio", r"\b(AC|SK)[0-9a-f]{32}\b"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    # literals split so this file's own source never matches its own pattern (the regex is unchanged)
    ("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----|PuTTY-User-" r"Key-File|-----BEGIN " r"OPENSSH"),
    ("url_basic_auth", r"\b[a-z][a-z0-9+.-]{1,10}://[^\s/:@'\"]{1,64}:[^\s/@'\"]{3,64}@[A-Za-z0-9.-]+"),
    ("conn_string_pw", r"(?i)(password|pwd)\s*=\s*[^;\s'\"]{3,}\s*;"),
    ("bearer_literal", r"(?i)bearer\s+[A-Za-z0-9._~+/-]{20,}=*"),
    ("basic_literal", r"(?i)basic\s+[A-Za-z0-9+/]{16,}={0,2}"),
    ("twitch_oauth", r"oauth:[a-z0-9]{30}"),
    ("mysql_p", r"mysql[^\n]{0,60}\s-p[^\s'\"$]{2,}"),
    ("sshpass", r"sshpass\s+-p\s*\S+"),
    ("net_use_user", r"(?i)net\s+use\s+[^\n]*?/user:\S+\s+\S+"),
    ("securestring_plain", r"(?i)ConvertTo-SecureString\s+['\"][^'\"]+['\"]"),
    ("steam_key", r"(?i)(steam|webapi).{0,20}key.{0,10}['\"=: ]+[0-9A-F]{32}\b"),
    ("hex32_assigned", r"(?i)(key|token|secret|pass(word)?|auth|pwd)[\"']?\s*[:=]\s*[\"'][0-9a-f]{32,64}[\"']"),
]
PATS = [(k, re.compile(p)) for k, p in PATS]

ASSIGN = re.compile(
    r"(?i)[\"']?([A-Za-z0-9_.-]*(pass(word|wd)?|pwd|secret|token|api[_-]?key|apikey|auth(_key|_token)?|private[_-]?key|client[_-]?secret|access[_-]?key|credential|cookie|session[_-]?id)[A-Za-z0-9_.-]*)[\"']?"
    r"\s*(?::=|=|:|=>)\s*[\"'](?P<val>[^\"'\n]{4,})[\"']")
PLACEHOLDER = re.compile(r"(?i)(your|xxx|\*\*\*|<|>|\{|\}|\$|example|placeholder|changeme|dummy|test|fake|sample|none|null|redacted|\.\.\.|env|os\.|getenv|todo|here|secret_key_here|optional|string|str\b|bool|int\b|\bhttp|/|\\)")
STRLIT = re.compile(r"[\"']([A-Za-z0-9+/=_\-.~]{20,})[\"']")
B64 = re.compile(r"(?<![A-Za-z0-9+/])([A-Za-z0-9+/]{40,}={0,2})(?![A-Za-z0-9+/])")
IPPORT = re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3})(:\d{2,5})?\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}\b")
# ---- end verbatim -------------------------------------------------------------------------------------------

# Hard hits triaged BY THE SKEPTIC as documentation examples, keyed (path, line, first4) so any change to the
# value or its position fails the gate again. The one entry: her protocol doc's handshake example carries a
# JWT truncated with "..." (23 chars after "Bearer "; a real JWT is 100+ chars with two dots).
TRIAGED_HARD = {
    ("code/postal_core/akp_protocol.md", 608, "Bear"): "truncated doc example `Bearer eyJh...` (skeptic review; secrets_A.md False Positives)",
}


def main():
    show_all = "--all" in sys.argv
    repo = repo_root(HERE)
    all_tracked = "--index" not in sys.argv or "--index-all" in sys.argv
    paths = staged_paths(repo, all_tracked=all_tracked)
    hard, assigns, entr, b64s, ips, emails = [], [], [], [], collections.Counter(), collections.Counter()
    nonblob = []
    nbin = ntext = 0
    for path, mode, data in index_blobs(repo, paths):
        if data is None:
            nonblob.append((path, mode))
            continue
        if b"\0" in data[:8192]:
            nbin += 1
            txt = data.decode("latin-1")                 # still scan binaries for printable secret shapes
            for k, rx in PATS:
                for m in rx.finditer(txt):
                    hard.append((path, 0, k, m4(m.group(0))))
            continue
        ntext += 1
        txt = data.decode("utf-8", "replace")
        for ln, line in enumerate(txt.splitlines(), 1):
            for k, rx in PATS:
                for m in rx.finditer(line):
                    hard.append((path, ln, k, m4(m.group(0))))
            for m in ASSIGN.finditer(line):
                val = m.group("val")
                if PLACEHOLDER.search(val) or " " in val.strip() and len(val.split()) > 2:
                    continue
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", val) and ent(val) < 3.5:
                    continue   # identifier / enum-ish
                assigns.append((path, ln, m.group(1), m4(val), round(ent(val), 2)))
            for m in STRLIT.finditer(line):
                s = m.group(1)
                if len(s) >= 20 and ent(s) >= 4.2 and re.search(r"[0-9]", s) and re.search(r"[A-Z]", s) and re.search(r"[a-z]", s):
                    if re.fullmatch(r"[0-9a-f-]{36}", s):
                        continue
                    entr.append((path, ln, m4(s), round(ent(s), 2)))
            for m in B64.finditer(line):
                s = m.group(1)
                try:
                    raw = base64.b64decode(s + "=" * (-len(s) % 4), validate=False)
                except Exception:
                    continue
                printable = sum(32 <= b < 127 for b in raw) / max(1, len(raw))
                if printable > 0.9:
                    dec = raw.decode("latin-1")
                    flag = bool(re.search(r"(?i)pass|token|secret|key|user|auth|:", dec))
                    b64s.append((path, ln, m4(s), len(s), "decodes-printable" + ("+CRED-WORDS" if flag else ""), dec[:4]))
            for m in IPPORT.finditer(line):
                ip = m.group(1)
                if all(0 <= int(o) <= 255 for o in ip.split(".")) and not ip.startswith(("0.", "127.", "255.")) and ip not in ("0.0.0.0",):
                    ips[(ip, m.group(2) or "")] += 1
            for m in EMAIL.finditer(line):
                emails[m.group(0).lower()] += 1

    def hkey(r):
        return (r[0], r[1], r[3][1:5])          # m4() renders "'abcd'..lenN" -> first4 is chars 1..5
    triaged = [r for r in hard if hkey(r) in TRIAGED_HARD]
    real = [r for r in hard if hkey(r) not in TRIAGED_HARD]
    cred_b64 = [r for r in b64s if "CRED-WORDS" in r[4]]

    print(f"[rescan_skeptic] blobs: text {ntext}  binary {nbin}  ({'all' if all_tracked else 'staged'} index of {repo})")
    print(f"[rescan_skeptic] HARD PATTERN HITS: {len(hard)} raw = {len(real)} REAL + {len(triaged)} triaged doc example(s)")
    for r in real:
        print("   REAL ", r)
    for r in triaged:
        print("   triaged", r, "--", TRIAGED_HARD[hkey(r)])
    print(f"[rescan_skeptic] base64 blobs >= 40 decoding to printable: {len(b64s)}  (with credential words: {len(cred_b64)})")
    for r in cred_b64:
        print("   CRED-WORDS", r[:5])
    print(f"[rescan_skeptic] INFO literal assignments to credential-named keys, non-placeholder: {len(assigns)}")
    print(f"[rescan_skeptic] INFO high-entropy string literals >= 20 chars, H >= 4.2, mixed case+digit: {len(entr)}")
    print(f"[rescan_skeptic] INFO distinct (ip, port): {len(ips)}   distinct e-mail shapes: {len(emails)}")
    if show_all:
        print("\n=== LITERAL ASSIGNMENTS TO CREDENTIAL-NAMED KEYS, non-placeholder")
        for r in assigns: print("  ", r)
        print("\n=== HIGH-ENTROPY STRING LITERALS >=20 chars, H>=4.2, mixed case+digit")
        for r in entr: print("  ", r)
        print("\n=== BASE64 BLOBS >=40 that decode to printable")
        for r in b64s: print("  ", r)
        print("\n=== IPs (ip, port) -> count")
        for (ip, port), c in sorted(ips.items()): print("  ", ip, port, c)
        print("\n=== EMAIL-shaped")
        for e, c in sorted(emails.items()): print("  ", e, c)
    if nonblob:
        print(f"[rescan_skeptic] index entries that are NOT plain blobs (gitlink/missing): {len(nonblob)}")
        for rel, mode in nonblob:
            print(f"  {rel}  mode={mode}")
    sys.exit(1 if (real or cred_b64 or nonblob) else 0)


if __name__ == "__main__":
    main()
