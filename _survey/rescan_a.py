"""rescan_a.py -- re-run SECRET HUNT A's exact patterns over a directory, a NUL-separated file list, or the
git INDEX (the blobs a commit would actually contain).  Read-only.  Prints file:line, kind, first 4 chars,
length, placeholder-hint -- never a full value.  Exit code 1 if any non-placeholder, non-triaged finding.

    python -B rescan_a.py <root> [--all]                 walk <root> (skips .git)
    git ls-files -z | python -B rescan_a.py --stdin0     scan the listed working-tree files
    python -B rescan_a.py --index [--all]                scan the STAGED blobs (index vs HEAD, ACMR)
    python -B rescan_a.py --index-all [--all]            scan EVERY blob in the index
    (--all also prints placeholder-hinted matches)

Also lists credential-NAMED files (STRONG globs) among the scanned paths.
"""
import os, re, sys, bisect
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from hunt_a_patterns import (PATTERNS, HIENT_RX, SKIP_VAL_RX, IDENTISH_RX, NOISY_TOKEN_NAME_RX,
                             CODE_EXT, TEXT_EXT, NOEXT_TEXT_NAMES, STRONG_RX, WEAK_RX,
                             PLACEHOLDER_RX, HEXISH, UUID_RX, shannon)

show_all = "--all" in sys.argv
findings = []
cred_named = []

# Hand-triaged false positives, keyed by (relpath, line, first 4 chars) so that a NEW value on the same
# line, or the same value moving, still fails the gate. Each entry cites where it was triaged.
TRIAGED_FP = {
    ("postal_core/akp_protocol.md", 182, "opti"):
        "protocol-spec JSON example: \"auth_token\": \"optional-bearer-token\" (secrets_A.md, False Positives)",
    ("_survey/secrets_A.md", 28, "torc"):
        "Hunt A's own False-Positives table quoting the type annotation `token_importance: \"torch.Tensor\"` (a type name)",
}
# The hunts' own masking convention: at most 4 visible chars, then `..[len]` (e.g. `sk-a..[108]`). A value of that
# exact shape is a MASKED STUB from a report table, never a credential -- it is treated like a placeholder hint.
MASKED_STUB_RX = re.compile(r"^.{1,4}\.\.\[\d+\]$")


def is_text(name):
    ext = os.path.splitext(name)[1].lower()
    return ext in TEXT_EXT or name in NOEXT_TEXT_NAMES or ext == "" or name.startswith(".env")


def scan_data(data, rel):
    if b"\x00" in data[:8192] or not data:
        return
    text = data.decode("utf-8", "replace")
    is_code = os.path.splitext(rel)[1].lower() in CODE_EXT
    nl = None
    seen = set()

    def ln_of(pos):
        nonlocal nl
        if nl is None:
            nl = [i for i, ch in enumerate(text) if ch == "\n"]
        i = bisect.bisect_right(nl, pos)
        start = nl[i - 1] + 1 if i > 0 else 0
        end = nl[i] if i < len(nl) else len(text)
        return i + 1, text[start:end]

    for name, rx, kind, sev in PATTERNS:
        for m in rx.finditer(text):
            secret = m.group(1) if (m.lastindex and m.group(1)) else m.group(0)
            if name in ("pw_assign", "env_assign"):
                secret = m.group(2)
                if SKIP_VAL_RX.match(secret): continue
                if re.match(r"^[a-z_]+$", secret) and len(secret) < 20: continue
                if name == "env_assign" and (is_code or IDENTISH_RX.match(secret)): continue
                if name == "pw_assign":
                    if NOISY_TOKEN_NAME_RX.search(m.group(1).lower()): continue
                    if len(secret) < 12 and shannon(secret) < 3.0: continue
            ln, line = ln_of(m.start())
            seen.add(ln)
            ph = bool(PLACEHOLDER_RX.search(secret)) or bool(PLACEHOLDER_RX.search(line)) or bool(MASKED_STUB_RX.match(secret))
            findings.append((rel, ln, kind, secret[:4], len(secret), sev, ph))
    for m in HIENT_RX.finditer(text):
        val = m.group(2)
        if IDENTISH_RX.match(val): continue
        if HEXISH.match(val) and len(val) in (32, 40, 64, 128):
            if not re.search(r"(?i)api[_\-]?key|secret|token|password", m.group(0)): continue
        if UUID_RX.match(val.replace("-", "")): continue
        if shannon(val) < 4.3: continue
        ln, line = ln_of(m.start())
        if ln in seen: continue
        ph = bool(PLACEHOLDER_RX.search(val)) or bool(PLACEHOLDER_RX.search(line))
        findings.append((rel, ln, "High-entropy literal in key/token context", val[:4], len(val), "MEDIUM", ph))


def scan_file(path, rel):
    try:
        data = open(path, "rb").read()
    except OSError as e:
        print("ERR", rel, e)
        return
    scan_data(data, rel)


def name_check(rel):
    fn = os.path.basename(rel)
    for g, rx in STRONG_RX:
        if rx.match(fn):
            cred_named.append((rel, g))
            break


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = 0
    nonblob = []
    if "--index" in sys.argv or "--index-all" in sys.argv:
        from gitindex import repo_root, staged_paths, index_blobs
        repo = repo_root(HERE)
        paths = staged_paths(repo, all_tracked="--index-all" in sys.argv)
        where = f"git index of {repo} ({'all' if '--index-all' in sys.argv else 'staged'}: {len(paths)} paths)"
        for rel, mode, data in index_blobs(repo, paths):
            name_check(rel)
            if data is None:
                nonblob.append((rel, mode))
                continue
            if is_text(os.path.basename(rel)):
                n += 1
                scan_data(data, rel)
    elif "--stdin0" in sys.argv:
        root = args[0] if args else os.getcwd()
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        listed = [p for p in raw.split("\0") if p]
        where = f"{len(listed)} listed files under {root}"
        for rel in listed:
            p = os.path.join(root, rel)
            name_check(rel)
            if is_text(os.path.basename(rel)) and os.path.isfile(p):
                n += 1
                scan_file(p, rel)
    else:
        root = args[0]
        where = root
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d != ".git"]
            for fn in fns:
                p = os.path.join(dp, fn)
                rel = os.path.relpath(p, root).replace("\\", "/")
                name_check(rel)
                if is_text(fn):
                    n += 1
                    scan_file(p, rel)

    print(f"[rescan_a] scanned {n} text files -- {where}")

    def _fp_key(f):
        # the mirror may be scanned from the repo root ("code/<rel>") or from code/ itself ("<rel>")
        rel = f[0][5:] if f[0].startswith("code/") else f[0]
        return (rel, f[1], f[3])

    triaged = [f for f in findings if not f[6] and _fp_key(f) in TRIAGED_FP]
    real = [f for f in findings if not f[6] and _fp_key(f) not in TRIAGED_FP]
    print(f"[rescan_a] findings: {len(findings)} total, {len(real)} REAL (no placeholder hint, not triaged), "
          f"{len(triaged)} triaged false positive, {len(findings) - len(real) - len(triaged)} placeholder-hinted")
    for f in sorted(findings, key=lambda f: (f[6], f[0], f[1])):
        if f[6] and not show_all:
            continue
        rel, ln, kind, f4, L, sev, ph = f
        tag = '  [placeholder-hint]' if ph else ('  [TRIAGED FP: ' + TRIAGED_FP[_fp_key(f)] + ']' if f in triaged else '  <-- REAL')
        print(f"  {rel}:{ln}  {kind}  first4={f4!r} len={L} {sev}{tag}")
    print(f"[rescan_a] credential-named files (STRONG globs): {len(cred_named)}")
    for rel, g in cred_named:
        print(f"  {rel}  ({g})")
    if nonblob:
        print(f"[rescan_a] index entries that are NOT plain blobs (gitlink/missing): {len(nonblob)}")
        for rel, mode in nonblob:
            print(f"  {rel}  mode={mode}")
    sys.exit(1 if (real or nonblob) else 0)


if __name__ == "__main__":
    main()
