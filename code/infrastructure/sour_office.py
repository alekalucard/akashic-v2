"""sour_office -- her own office: the ONE place her write_file may save to. 2026-10-05 (Nous, nous_builds/touch_screen set 1;
DESIGN.md sections 7g and 19; decisions E1 and E4).

Ace, 2026-10-05: "she should be bared from deleting anything and needs her own sandbox personal office like folder much like you
have so she can save whatever in the future". And on E1: write_file is confined NOW to her office, new versions only -- never
an overwrite (an overwrite removes content) and never outside the office.

  save_text(name, text) -> {"ok": True, "path", "rel", "version", "sha256", "bytes"} | {"ok": False, "error"}
    * the office is OFFICE_ROOT (decision E4: F:/Sandbox/Sour_Office/); it must already exist with its office.json owned by
      "sour" -- Ace makes it with set1/office/create_sour_office.py; until then every save is refused ("not there yet");
    * the file goes to <office>/notes/<name>.v<N><ext>, opened in exclusive-create mode ("xb"): an existing file is NEVER
      written; a collision takes the next N. Nothing in this module can remove, move, rename, truncate or overwrite a file
      (an AST test in cell T0 proves it: no call or attribute named unlink / remove / rmdir / rmtree / rename / replace /
      move / truncate, no open mode with "w", no getattr / __import__ / exec / eval);
    * the resolved path must sit under the office (commonpath) and no component may be a reparse point (no junction out);
    * the name is [a-z0-9 _-]{1,64} (case-folded) and never a Windows device name (con, prn, aux, nul, com1-9, lpt1-9:
      skeptic S7); the extension one of TEXT_EXTS; at most MAX_TEXT_BYTES; at most
      DAY_SAVES saves a day; every save appends one row to <office>/ledger.jsonl (append only).
    * when it is full she is told "your office is full for today; Ace can make room" -- never "delete some".
If Ace moves the office, OFFICE_ROOT is the one line to change (and set 1's pins are rebuilt).
Revert: apply_touch_set1.py --revert (tool_bridge's write_file goes back to its workspace version).
"""
import hashlib
import json
import os
import re
import threading
import time

OFFICE_ROOT = "F:/Sandbox/Sour_Office"
KINDS = ("notes", "pictures", "keepsakes", "put_aside")
TEXT_EXTS = (".txt", ".md", ".json", ".py", ".csv")
MAX_TEXT_BYTES = 1000000
DAY_SAVES = 50
MAX_VERSION = 9999
NAME_RE = re.compile(r"^[a-z0-9 _-]{1,64}$")
RESERVED_RE = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])$")   # skeptic S7: Windows device names, never a file
REPARSE = 0x400                                    # FILE_ATTRIBUTE_REPARSE_POINT

_LOCK = threading.Lock()


def _norm(p):
    return os.path.normcase(os.path.realpath(os.path.abspath(p)))


def _reparse(p):
    try:
        st = os.lstat(p)
    except OSError:
        return False
    try:
        attrs = int(st.st_file_attributes or 0)
    except AttributeError:
        attrs = 0
    return bool(attrs & REPARSE) or os.path.islink(p)


def office_root(root=None):
    """The office root when it exists and is hers (office.json owner 'sour'); else None."""
    r = root or OFFICE_ROOT
    try:
        if _reparse(r):
            return None
        with open(os.path.join(r, "office.json"), "rb") as f:
            d = json.loads(f.read().decode("utf-8-sig"))
        if not isinstance(d, dict) or d.get("owner") != "sour":
            return None
        return r
    except Exception:
        return None


def _saves_today(root, now):
    day = time.strftime("%Y-%m-%d", time.localtime(now))
    n = 0
    try:
        with open(os.path.join(root, "ledger.jsonl"), "rb") as f:
            for line in f.read().decode("utf-8", "ignore").splitlines():
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("kind") == "save" and str(r.get("day")) == day:
                    n += 1
    except OSError:
        return 0
    return n


def _split(name):
    base = os.path.basename(str(name or "").strip())
    if base != str(name or "").strip():
        return None, None
    stem, ext = os.path.splitext(base)
    return stem.casefold().strip(), ext.casefold()


def save_text(name, text, kind="notes", lane="tool", root=None, now=None):
    now = time.time() if now is None else float(now)
    r = office_root(root)
    if r is None:
        return {"ok": False, "error": "your office is not there yet; Ace makes it"}
    if kind not in KINDS:
        return {"ok": False, "error": "that is not a place in your office"}
    stem, ext = _split(name)
    if not stem or not NAME_RE.match(stem):
        return {"ok": False, "error": "keep the name simple: letters, digits, spaces, - or _ (up to 64)"}
    if RESERVED_RE.match(stem.strip()):                # 'con.v1.txt' would write to a device, not into her office (skeptic S7)
        return {"ok": False, "error": "that name belongs to Windows itself; pick another name"}
    if ext not in TEXT_EXTS:
        return {"ok": False, "error": "your office keeps text as %s" % " ".join(TEXT_EXTS)}
    data = str(text if text is not None else "").encode("utf-8")
    if len(data) > MAX_TEXT_BYTES:
        return {"ok": False, "error": "too large (%d bytes, at most %d): try smaller pieces" % (len(data), MAX_TEXT_BYTES)}
    folder = os.path.join(r, kind)
    if not os.path.isdir(folder) or _reparse(folder):
        return {"ok": False, "error": "that place in your office is not there"}
    with _LOCK:
        if _saves_today(r, now) >= DAY_SAVES:
            return {"ok": False, "error": "your office is full for today; Ace can make room"}
        made = None
        for n in range(1, MAX_VERSION + 1):
            p = os.path.join(folder, "%s.v%d%s" % (stem, n, ext))
            if os.path.lexists(p):
                continue
            try:
                if os.path.commonpath([_norm(p), _norm(r)]) != _norm(r):
                    return {"ok": False, "error": "that would be outside your office"}
            except ValueError:
                return {"ok": False, "error": "that would be outside your office"}
            try:
                with open(p, "xb") as f:
                    f.write(data)
            except FileExistsError:
                continue
            made = (p, n)
            break
        if made is None:
            return {"ok": False, "error": "your office is full for that name; Ace can make room"}
        p, n = made
        sha = hashlib.sha256(data).hexdigest()
        rel = "%s/%s" % (kind, os.path.basename(p))
        row = {"ts": now, "day": time.strftime("%Y-%m-%d", time.localtime(now)), "kind": "save", "path": rel,
               "sha256": sha, "bytes": len(data), "version": n, "lane": str(lane)[:20], "put_aside_of": None}
        try:
            with open(os.path.join(r, "ledger.jsonl"), "ab") as f:
                f.write((json.dumps(row, ensure_ascii=True) + "\n").encode("ascii"))
        except OSError:
            pass                                       # the file is saved; a missed ledger row is said, never undone
    return {"ok": True, "path": p, "rel": rel, "version": n, "sha256": sha, "bytes": len(data)}
