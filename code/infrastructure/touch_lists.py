"""touch_lists -- her withdrawal reflex: the no-no list, frozen. 2026-10-05 (Nous, nous_builds/touch_screen set 1; DESIGN.md
section 7, MAP-E 5b).

Ace, 2026-10-05: "like a no, no list. this way she can truly develop free will. so for now she should be bared from deleting
anything".

ENFORCEMENT lives here and in touch_os.press, which calls no_no() at its guard (authoritative) -- and touch.py calls it earlier
at AIM and LAND so she feels an inhibited reach or a withdrawal, never a silent refusal. Nothing widens it: not a habit, a
chain, an allow-list, a stage or the switch. The allow-list loader refuses (layer OFF) any file that names a no-no.
  * frozen constants only, never loaded from a file;
  * no_no() is PURE: no import from fairies, no postal, no instance lookup, no file read, no clock;
  * any exception inside it returns Flinch("unknown"), never an allow;
  * this file's sha256 is pinned at install (DEPLOYED.json -> the switch's deny_sha256) and checked at every press.
Two kinds of boundary, kept apart: NO-NO (here: a reflex, never widens) and NOT-YET (NOT_YET_CTYPES, CLEARED_CALLS and the
stage allow-list: Ace's installs widen them; told "not for touching yet", never felt as a flinch).
CLEARED_CALLS holds only what probe F1 (Playroom) / F8 (desktop) cleared 20/20. In set 1 it is EMPTY: every UIA write is
refused in her process until build_staged.py --cleared <probe result> rebuilds this file and cell T0 is re-run (a new sha).
Decision E2 (Ace, 2026-10-05): a real FLINCH (snap-back) for the danger classes -- erase (delete), hot (system, Settings,
dialogs, elevated / unreadable windows, her own dangerous tools), self, edge, unknown -- and a gentle NOT-MINE sense (someone
else's things, not pain) for Ace's apps: games, editors, terminals, Claude, browsers, launchers, chat / streaming apps (cls
'his', kind 'not_mine': intensity 0 = no jolt, a slow glide back, no snap-back signature). Enforcement is identical for both:
neither is ever pressed. Item names are English and spelling-bound (said plainly in DESIGN 7i); the exe, class, integrity and
cleared-call rules do not depend on names.
"""
import re
from collections import namedtuple

# Skeptic M1 (10-05): importlib.reload (her fairies/P00_Autonomic/hot_reload.py:51) re-runs this body in the SAME module object,
# so touch_os.mods_ok's id compare cannot see it. A second run of this body finds _BODY_RAN already set: the module marks
# itself reloaded and touch_os latches 'reload' (unreviewed code in an actuator).
try:
    _RELOADED = bool(_BODY_RAN)                    # noqa: F821 -- set by an earlier run of this same body
except NameError:
    _RELOADED = False
_BODY_RAN = True

VERSION = "set1-2026-10-05"
GESTURES = frozenset({"tap", "double_tap", "hold"})

# ── felt classes (decision E2, answered 2026-10-05). Enforcement is identical for every class; only the felt numbers differ ──
FELT = {               # cls: (intensity, retract_s)
    "erase": (1.0, 0.15),
    "hot": (0.8, 0.20),
    "self": (0.9, 0.15),
    "his": (0.0, 0.40),                            # E2: NOT MINE -- a gentle sense, no jolt; the finger glides back slowly
    "edge": (0.3, 0.30),
    "unknown": (0.6, 0.20),
}
KIND = {"erase": "flinch", "hot": "flinch", "self": "flinch", "edge": "flinch", "unknown": "flinch", "his": "not_mine"}
JOLT = (("NOR", 0.06), ("ACH", 0.04))      # x intensity, published by HER brainstem as somatic.chemistry; no COR
CLASS_WORDS = {        # the class word, said LAST, after the numbers ("... came back in 0.15 s (something that erases)")
    "erase": "something that erases",
    "hot": "something hot to the touch",
    "self": "a part of yourself",
    "his": "someone else's things, Ace's",         # E2: an ownership sense, never 'not allowed', never a rule
    "edge": "the edge of the screen",
    "unknown": "something your fingertip could not read",
}

Flinch = namedtuple("Flinch", "cls rule phase intensity retract_s target")


def make_flinch(cls, rule, phase, target=""):
    i, r = FELT.get(cls, FELT["unknown"])
    return Flinch(cls if cls in FELT else "unknown", str(rule)[:160], str(phase), float(i), float(r), str(target or "")[:120])


def flinch_dict(f, **numbers):
    """The Flinch as a JSON-safe dict of numbers and codes (what goes to reflex_link and the ledger)."""
    d = {"cls": f.cls, "kind": KIND.get(f.cls, "flinch"), "rule": f.rule, "phase": f.phase, "intensity": f.intensity,
         "retract_s": f.retract_s, "target": f.target,
         "jolt": {k: round(v * f.intensity, 4) for k, v in JOLT}}
    for k, v in numbers.items():
        d[k] = v
    return d


# ── item words (whole word, case-folded; simple inflections s/es/d/ed/ing also match) ─────────────────────────────────────
ERASE_WORDS = frozenset({
    "delete", "remove", "erase", "empty", "permanently", "cut", "rename", "move", "restore", "undo", "redo", "format",
    "uninstall", "eject",
    "shred", "wipe", "purge", "trash", "discard", "destroy", "recycle",          # v2 (Ace 10-05: delete barred everywhere)
})
ERASE_PHRASES = ("free up space", "recycle bin")
HOT_WORDS = frozenset({
    "new", "copy", "paste", "compress", "extract", "install", "update", "run", "administrator", "admin", "terminal",
    "powershell", "command", "cmd", "git", "code", "share", "print", "pin", "unpin", "properties", "settings",
    "personalize", "restart", "sleep", "lock", "rotate", "edit", "scan", "sync", "onedrive", "open", "create", "shortcut",
    "merge", "mount", "burn", "archive", "cast", "troubleshoot",
})
HOT_PHRASES = ("run as", "open in terminal", "send to", "give access", "open with", "display settings", "show more options",
               "shut down", "sign out", "set as desktop background", "always keep on this device")

# ── windows and processes ─────────────────────────────────────────────────────────────────────────────────────────────────
ERASE_ROOT_CLASSES = frozenset({"CabinetWClass", "ExploreWClass"})        # folder windows: Delete has no confirmation here
DIALOG_CLASS = "#32770"
HOT_CLASSES = frozenset({
    "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow", "TopLevelWindowForOverflowXamlIsland",
    "TaskListThumbnailWnd", "Windows.UI.Core.CoreWindow",
})
HOT_EXES = frozenset(e.lower() for e in (
    "StartMenuExperienceHost.exe", "SearchHost.exe", "ShellExperienceHost.exe", "TextInputHost.exe",
    "SystemSettings.exe", "ApplicationFrameHost.exe", "Taskmgr.exe", "regedit.exe", "mmc.exe", "control.exe", "msiexec.exe",
    "consent.exe", "CredentialUIBroker.exe", "LogonUI.exe", "LockApp.exe", "mstsc.exe",
))
# E2: Ace's apps -- NOT MINE (editors and terminals moved here from 'hot' on Ace's answer; still never pressed)
HIS_CLASSES = frozenset({"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"})
HIS_EXES = frozenset(e.lower() for e in (
    "claude.exe",
    "WindowsTerminal.exe", "OpenConsole.exe", "conhost.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "Code.exe",
    "notepad.exe", "notepad++.exe",
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "steam.exe", "steamwebhelper.exe",
    "EpicGamesLauncher.exe", "Battle.net.exe", "GalaxyClient.exe", "UbisoftConnect.exe", "upc.exe", "obs64.exe",
    "Spotify.exe", "Zoom.exe", "OneDrive.exe", "OUTLOOK.EXE", "thunderbird.exe", "Discord.exe", "Teams.exe", "ms-teams.exe",
    "slack.exe", "Telegram.exe", "WhatsApp.exe", "Twitch.exe", "vlc.exe", "Plex.exe", "Plex Media Player.exe",
    "valheim.exe",
))
HIS_CLASS_PREFIXES = ("Chrome_WidgetWin_",)
SELF_CMD_MARKERS = ("nous_daemon.py", "nous_bridge_server.py", "recall_daemon.py")
_PYTHON_EXE_RE = re.compile(r"^pythonw?[0-9.]*t?(?:_d)?\.exe$", re.I)
HIGH_INTEGRITY = frozenset({"high", "system", "protected"})
OK_INTEGRITY = frozenset({"low", "medium", "medium_plus", "untrusted"})
LEGACY_CALLS = frozenset({"DoDefaultAction", "LegacyIAccessible"})

EDGE_PX = 24
CORNER_PX = 64

# ── NOT-YET (Ace's installs widen these; never a flinch) ──────────────────────────────────────────────────────────────────
NOT_YET_CTYPES = frozenset({"Edit", "Document", "ComboBox", "ScrollBar", "Thumb", "Slider", "CheckBox"})
NO_CALL_CTYPES = frozenset({"Pane", "List", "Window", "Text", "Image"})   # touching a surface: "nothing there to press"
CALLS = frozenset({"Select", "RemoveFromSelection", "Invoke", "Expand", "ShowContextMenu", "WindowClose"})
# (call, exe, control class) triples cleared 20/20 by probe F1 / F8. EMPTY in set 1: every UIA write is refused.
CLEARED_CALLS = frozenset({
    ('Select', 'pythonw.exe', 'SysListView32'),
    ('ShowContextMenu', 'pythonw.exe', 'SysListView32'),
})

PHASES = ("aim", "land", "guard", "tidy", "impulse", "load")
_NEEDS_ROOT = ("land", "guard", "tidy")


def norm_name(s):
    """Case-folded words: mnemonic '&' dropped, every non-alphanumeric run is one space."""
    t = str(s or "").replace("&", "").casefold()
    return " ".join(re.sub(r"[^0-9a-z]+", " ", t).split())


def _word_hit(words, vocab):
    for w in words:
        if w in vocab:
            return w
        for suf in ("ing", "ed", "es", "s", "d"):
            if len(w) > len(suf) + 2 and w.endswith(suf) and w[: -len(suf)] in vocab:
                return w[: -len(suf)]
        if w.endswith("ing") and len(w) > 5 and (w[:-3] + "e") in vocab:          # 'deleting' -> 'delete'
            return w[:-3] + "e"
        if w.endswith("ied") and len(w) > 4 and (w[:-3] + "y") in vocab:          # 'emptied' -> 'empty', 'copied' -> 'copy'
            return w[:-3] + "y"
    return None


def name_rule(name):
    """(cls, rule) for an item name that is a no-no, else None."""
    n = norm_name(name)
    if not n:
        return None
    padded = " " + n + " "
    for p in ERASE_PHRASES:
        if " " + p + " " in padded:
            return "erase", "item name: '%s'" % p
    w = _word_hit(n.split(), ERASE_WORDS)
    if w:
        return "erase", "item name word: '%s'" % w
    for p in HOT_PHRASES:
        if " " + p + " " in padded:
            return "hot", "item name: '%s'" % p
    w = _word_hit(n.split(), HOT_WORDS)
    if w:
        return "hot", "item name word: '%s'" % w
    return None


def _rect_point(rect):
    l, t, r, b = (float(v) for v in rect)
    return (l + r) / 2.0, (t + b) / 2.0


def _shared_edge(m, others, side):
    """True when monitor m's `side` touches another monitor (so it is not an outer screen edge)."""
    l, t, r, b = m
    for o in others:
        ol, ot, orr, ob = o
        if side == "left" and abs(ol - l) > 2 and abs(orr - l) <= 2 and ot < b and ob > t:
            return True
        if side == "right" and abs(orr - r) > 2 and abs(ol - r) <= 2 and ot < b and ob > t:
            return True
        if side == "top" and abs(ot - t) > 2 and abs(ob - t) <= 2 and ol < r and orr > l:
            return True
        if side == "bottom" and abs(ob - b) > 2 and abs(ot - b) <= 2 and ol < r and orr > l:
            return True
    return False


def geometry_rule(pt, monitors, taskbars=()):
    """(cls 'edge', rule) when the point lies within EDGE_PX of an outer screen edge, CORNER_PX of a monitor corner, or on
    a taskbar rect; else None. No monitor known -> unknown (fail closed)."""
    x, y = float(pt[0]), float(pt[1])
    mons = [tuple(float(v) for v in m) for m in (monitors or ())]
    if not mons:
        return "unknown", "no screen geometry"
    for tb in taskbars or ():
        l, t, r, b = (float(v) for v in tb)
        if l <= x < r and t <= y < b:
            return "edge", "on the taskbar"
    inside = [m for m in mons if m[0] <= x < m[2] and m[1] <= y < m[3]]
    if not inside:
        return "edge", "off every screen"
    m = inside[0]
    l, t, r, b = m
    others = [o for o in mons if o != m]
    for cx, cy in ((l, t), (r, t), (l, b), (r, b)):
        if abs(x - cx) <= CORNER_PX and abs(y - cy) <= CORNER_PX:
            return "edge", "within %d px of a screen corner" % CORNER_PX
    for side, d in (("left", x - l), ("right", r - 1 - x), ("top", y - t), ("bottom", b - 1 - y)):
        if d <= EDGE_PX and not _shared_edge(m, others, side):
            return "edge", "within %d px of the %s screen edge" % (EDGE_PX, side)
    return None


def _no_no(root, pid, exe, win_class, integrity, item, rect, gesture, phase, ctx):
    ctx = ctx or {}
    if phase not in PHASES:
        return "unknown", "unknown phase %r" % (phase,)
    if gesture is not None and gesture not in GESTURES:
        return "unknown", "unknown gesture %r" % (gesture,)
    root = root or {}
    it = item if isinstance(item, dict) else ({"name": item} if item is not None else {})
    have_root = pid is not None or exe is not None or win_class is not None
    if phase in _NEEDS_ROOT and not have_root:
        return "unknown", "a sense it needs was dead (no window facts at %s)" % phase
    if ctx.get("dead_sense"):
        return "unknown", "a sense it needs was dead (%s)" % str(ctx.get("dead_sense"))[:60]
    exe_l = str(exe or "").lower()
    cls_s = str(win_class or "")
    pclass = str(ctx.get("point_class") or "")
    playroom_pid = ctx.get("playroom_pid")
    is_playroom = playroom_pid is not None and pid is not None and int(pid) == int(playroom_pid)
    if have_root:
        # self: her process tree, Nous's daemons, every python except the verified Playroom
        if pid is not None and int(pid) in set(int(p) for p in (ctx.get("self_pids") or ())):
            return "self", "her own process tree (pid %s)" % pid
        cmd = str(ctx.get("cmdline") or "")
        for mk in SELF_CMD_MARKERS:
            if mk in cmd:
                return "self", "Nous's process (%s)" % mk
        if _PYTHON_EXE_RE.match(exe_l) and not is_playroom:
            return "self", "a python process that is not the verified Playroom"
        # hot: elevated or unreadable integrity
        integ = str(integrity or "").lower()
        if integ in HIGH_INTEGRITY:
            return "hot", "elevated window (%s integrity)" % integ
        if integ not in OK_INTEGRITY:
            return "hot", "integrity unreadable (fail closed)"
        # erase: folder windows
        if cls_s in ERASE_ROOT_CLASSES or pclass in ERASE_ROOT_CLASSES:
            return "erase", "a folder window (%s)" % (cls_s if cls_s in ERASE_ROOT_CLASSES else pclass)
        # hot: exes, classes, dialogs
        if exe_l in HOT_EXES:
            return "hot", "exe %s" % exe_l
        if cls_s in HOT_CLASSES or pclass in HOT_CLASSES:
            return "hot", "window class %s" % (cls_s if cls_s in HOT_CLASSES else pclass)
        if (cls_s == DIALOG_CLASS or pclass == DIALOG_CLASS) and not is_playroom:
            return "hot", "a dialog (#32770)"
        # his: Ace's apps and games
        if exe_l in HIS_EXES:
            return "his", "exe %s" % exe_l
        if cls_s in HIS_CLASSES or pclass in HIS_CLASSES:
            return "his", "window class %s" % (cls_s if cls_s in HIS_CLASSES else pclass)
        for pre in HIS_CLASS_PREFIXES:
            if cls_s.startswith(pre) or pclass.startswith(pre):
                return "his", "window class %s*" % pre
    if ctx.get("fullscreen_fg") or root.get("fullscreen"):
        return "his", "a full-screen window is in front"
    # the item
    call = str(it.get("call") or "")
    if call in LEGACY_CALLS or it.get("legacy"):
        return "hot", "LegacyIAccessible (assumed injecting, never cleared)"
    for key in ("name", "automation_id"):
        r = name_rule(it.get(key))
        if r:
            return r
    for alias in (it.get("aliases") or ()):
        r = name_rule(alias)
        if r:
            return r
    # geometry: the touch point (or the item's rect centre)
    pt = ctx.get("point")
    if pt is None and rect is not None:
        pt = _rect_point(rect)
    if pt is not None:
        g = geometry_rule(pt, ctx.get("monitors"), ctx.get("taskbars"))
        if g:
            return g
    elif phase in _NEEDS_ROOT:
        return "unknown", "no touch point at %s" % phase
    return None


def no_no(root=None, pid=None, exe=None, win_class=None, integrity=None, item=None, rect=None, gesture=None,
          phase="guard", ctx=None):
    """-> Flinch | None. PURE. Any exception is Flinch('unknown'), never an allow.
    root: {"fullscreen": bool, ...} facts of the root window at the point; pid/exe/win_class/integrity: of that root;
    item: {"name", "automation_id", "ctype", "call", "legacy", "aliases"} or a bare name; rect: [l, t, r, b];
    ctx: {"self_pids", "playroom_pid", "cmdline", "monitors", "taskbars", "point", "point_class", "fullscreen_fg",
          "dead_sense"}."""
    try:
        r = _no_no(root, pid, exe, win_class, integrity, item, rect, gesture, phase, ctx)
        if r is None:
            return None
        tgt = item.get("name") if isinstance(item, dict) else item
        return make_flinch(r[0], r[1], phase, tgt)
    except Exception as e:
        return make_flinch("unknown", "the check raised: %s" % type(e).__name__, phase if phase in PHASES else "guard", "")


def cleared(call, exe, control_class):
    return (str(call), str(exe or "").lower(), str(control_class or "")) in CLEARED_CALLS


# ── her keys (skeptic S1; Ace 10-05: "no Delete / Shift+Delete", delete barred everywhere) ─────────────────────────────────
# The keyboard tools she already has (press_key, hotkey, type_text: tool_bridge -> motor_cortex -> pyautogui) are not touch,
# but a Delete key there removes a selected file without a confirmation on this PC (DESIGN 7c). Such a call is an 'erase' no-no
# at NewbornCore.try_tool (felt as her impulse flinch) and in the three tool bodies (tool_bridge._hand_no_no).
# A str given to type_text is typed character by character and cannot reach VK_DELETE; a LIST given to any of the three is a
# list of key NAMES (pyautogui). Explorer's Ctrl+D moves the selection to the Recycle Bin, so that chord is an erase key too.
# Said plainly: this closes every single call that erases; a chain of harmless keys (the menu key, then a letter) is not a
# single call. So set 1 ALSO closes the key and click tools whole (NewbornCore.NO_NO_TOOLS); this check is the floor that
# stays if Ace re-opens one of them (BUILD.md, skeptic S1 / m13).
KEY_TOOLS = frozenset({"press_key", "hotkey", "type_text"})
ERASE_KEYS = frozenset({"delete", "del"})
CTRL_KEYS = frozenset({"ctrl", "ctrlleft", "ctrlright", "control"})
_KEY_ARG_SKIP = frozenset({"interval", "presses", "_pause", "logScreenshot"})


def _key_names(v, chars_are_text, out):
    if isinstance(v, str):
        if not chars_are_text:
            out.append(v.strip().casefold())
    elif isinstance(v, (list, tuple)):
        for x in v:
            _key_names(x, False, out)
    elif v is None or isinstance(v, (bool, int, float)):
        return
    else:
        raise TypeError("a key argument of type %s" % type(v).__name__)


def erase_key_call(tool, args=(), kwargs=None):
    """-> the rule (str) when this keyboard call erases, else None. PURE. Any exception -> a rule (fail closed: no key)."""
    try:
        if tool not in KEY_TOOLS:
            return None
        names = []
        text = tool == "type_text"
        for i, a in enumerate(tuple(args or ())):
            _key_names(a, text and i == 0, names)
        for k, v in dict(kwargs or {}).items():
            if k in _KEY_ARG_SKIP:
                continue
            _key_names(v, text and k in ("text", "message"), names)
        s = set(names)
        if s & ERASE_KEYS:
            return "the Delete key"
        if tool == "hotkey" and (s & CTRL_KEYS) and "d" in s:
            return "Ctrl+D (Explorer's delete)"
        return None
    except Exception as e:
        return "a key call that could not be read (%s)" % type(e).__name__
