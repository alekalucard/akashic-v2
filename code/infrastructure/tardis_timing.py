"""tardis_timing.py -- L0 TIMING for her TARDIS save thread. 2026-10-15 (Nous, nous_builds/tardis_fix_1015).

WHAT IT ANSWERS: the main cortex's TARDIS writes one word-pair in 0.4-0.8 s live, but the existence scan in link() is only 23-37 ms
of that (ANSWER.md). L0 splits the rest, per step, in wall time AND thread-CPU time: upsert a, upsert b, link (and inside link:
existence scan / strengthen / new edge / header flush; inside upsert: shared read / shared write / new node). A step whose CPU is
a small share of its wall is WAITING (shared mmap object, page faults, CPU share among ~1.5k threads); a step whose CPU is most of
its wall is WORK. One ASCII line says which step bounds the pair: `bound=<step>(cpu NN%)`.

HOW: ONE Acc per flush thread, armed in two thread-locals (fairy.py's _TF_FTL and manifold_memory._TF_L0_TL) ONLY by the TARDIS
flush thread and ONLY while the l0_timing switch is ON. Every other thread (postal workers on the overflow path, the gate, the
interior) finds no accumulator and measures nothing. Switch OFF = one getattr per call, nothing measured, nothing printed.

NEVER RAISES. Every Acc/Window method is wrapped; an internal error is counted, and after ERR_LATCH of them L0 disarms itself for
the process (one line). L0 cannot turn a pair into a swallowed exception (fairy.py:6159 `except Exception: pass`).

LIMITERS (each has a floor; the table is in BUILD.md): at most one line per 10 s (floor 10); one line per 120 flushes (floor 1,
ceiling 10000); at least one line per 120 s WHILE PAIRS ARE BEING WRITTEN (floor 30, ceiling 600) -- that line is emitted from
pair(), mid-batch, so a 10-minute batch (boot P) cannot hide; a 256-sample reservoir of per-pair totals (floor 16).

HONEST LIMITS: Windows charges thread CPU at clock-tick granularity (~15.6 ms): per-call CPU is meaningless, the WINDOW sums over
hundreds of pairs are what the line prints. L0 splits work from waiting; it cannot split waiting three ways (lock / paging /
CPU share) -- `pf/s`, `ram` and `sys_cpu` are printed beside `bound=` for that reason. The line stays one physical line, ASCII.
"""
from __future__ import annotations

import random
import sys
import threading
import time

try:                                    # optional: pf/s, ram, sys_cpu are "n/a" without it
    import psutil as _psutil
except Exception:                       # pragma: no cover
    _psutil = None

TOP = ("upA", "upA_new", "upB", "upB_new", "link")
DEEP_LINK = ("l.scan", "l.str", "l.new", "l.hdr")
DEEP_UP = ("u.rd", "u.wr", "u.new")

CFG = {"min_gap_s": 10.0, "flushes_per_line": 120, "max_silence_s": 120.0, "reservoir": 256, "err_latch": 5}
FLOOR = {"min_gap_s": 10.0, "flushes_per_line": 1, "max_silence_s": 30.0, "reservoir": 16, "err_latch": 1}
CEIL = {"min_gap_s": None, "flushes_per_line": 10000, "max_silence_s": 600.0, "reservoir": 4096, "err_latch": None}


def cfg(name):
    """A limiter's value, clamped to its floor / ceiling (a limiter that can be set to zero is a kill switch)."""
    v = CFG[name]
    try:
        v = type(FLOOR[name])(v)
    except Exception:
        v = FLOOR[name]
    v = max(FLOOR[name], v)
    if CEIL[name] is not None:
        v = min(CEIL[name], v)
    return v


def _say(msg):
    try:
        print(msg, flush=True)
    except Exception:
        pass


class Acc:
    """Per-flush-thread accumulator. now()/add()/pair()/isnew() NEVER raise."""

    def __init__(self, window, perf=time.perf_counter, cpu=time.thread_time):
        self.window = window
        self._perf, self._cpu = perf, cpu
        self.errs = 0
        self.dead = False
        self.reset()

    def reset(self):
        self.w, self.c, self.n = {}, {}, {}
        self.pairs = 0
        self._pair_w = 0.0
        self.res = []
        self.res_seen = 0

    def _err(self):
        self.errs += 1
        if self.errs >= cfg("err_latch") and not self.dead:
            self.dead = True
            _say("[TardisFix] L0 timing: %d internal errors -> L0 OFF for this process (pairs are unaffected)" % self.errs)

    def now(self):
        try:
            return (self._perf(), self._cpu())
        except Exception:
            self._err()
            return None

    def add(self, name, stamp):
        """Add (now - stamp) to `name`; return the new stamp. A None stamp (an earlier error) just restarts the chain."""
        try:
            if self.dead:
                return None
            p, c = self._perf(), self._cpu()
            if stamp is not None:
                dw, dc = p - stamp[0], c - stamp[1]
                self.w[name] = self.w.get(name, 0.0) + dw
                self.c[name] = self.c.get(name, 0.0) + dc
                self.n[name] = self.n.get(name, 0) + 1
                if name in TOP:
                    self._pair_w += dw
            return (p, c)
        except Exception:
            self._err()
            return None

    def isnew(self, region, key):
        try:
            return not region.has_node(key)
        except Exception:
            return False

    def pair(self):
        """One pair finished: count it, sample its total, and give the window its mid-batch chance to speak."""
        try:
            self.pairs += 1
            pw, self._pair_w = self._pair_w, 0.0
            self.res_seen += 1
            cap = cfg("reservoir")
            if len(self.res) < cap:
                self.res.append(pw)
            else:
                j = random.randrange(self.res_seen)
                if j < cap:
                    self.res[j] = pw
            w = self.window
            if w is not None:
                w.tick(self)
        except Exception:
            self._err()


def _pct(vals, q):
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


class Window:
    """Owns the Acc, the counter snapshots and the line. Used on the flush thread only."""

    def __init__(self, owner=None, perf=time.perf_counter, cpu=time.thread_time, mono=time.monotonic, out=None):
        self.owner = owner
        self._perf, self._cpu, self.mono = perf, cpu, mono
        self.out = out or _say
        self.acc = Acc(self, perf, cpu)
        self.tid = threading.get_ident()
        self.lines = 0
        self.last_line = None
        self.t_last_emit = self.mono()
        self.t_win0 = self.t_last_emit
        self.flushes = 0
        self.items = 0
        self.wall_sum = 0.0
        self.cpu_sum = 0.0
        self.seg_t0 = None
        self.seg_c0 = None
        self.cur_items = 0
        self.c0 = self._counters()
        self._ps = None
        self._pf0 = None
        self._cpu0 = None
        self._prime_psutil()

    # ---- counters / psutil -------------------------------------------------------------------------------------------
    def _counters(self):
        cx = self.owner
        d = {"q": 0, "queued": 0, "drops": 0, "flushed": 0, "fast": 0, "fb": 0}
        try:
            q = getattr(cx, "_tardis_bind_queue", None)
            d["q"] = q.qsize() if q is not None else 0
            d["queued"] = int(getattr(cx, "_tardis_binds_queued", 0))
            d["drops"] = int(getattr(cx, "_tardis_drops", 0))
            d["flushed"] = int(getattr(cx, "_tardis_binds_flushed", 0))
        except Exception:
            pass
        try:
            mm = _mm_module(cx)
            a1 = getattr(mm, "_TF_A1", None) if mm is not None else None
            if a1:
                d["fast"], d["fb"] = int(a1.get("fast", 0)), int(a1.get("fallback", 0))
        except Exception:
            pass
        return d

    def _prime_psutil(self):
        try:
            if _psutil is not None:
                self._ps = _psutil.Process()
                self._pf0 = self._pf()
                self._cpu0 = self._cpu_times()
        except Exception:
            self._ps = None

    def _pf(self):
        try:
            return int(self._ps.memory_info().num_page_faults)
        except Exception:
            return None

    def _cpu_times(self):
        try:
            t = _psutil.cpu_times()
            idle = getattr(t, "idle", 0.0)
            return (sum(t) - idle, sum(t))
        except Exception:
            return None

    # ---- batch protocol ----------------------------------------------------------------------------------------------
    def begin(self, n_items):
        try:
            if self.acc.dead:
                return None
            now = self.mono()
            if self.flushes == 0 and self.acc.pairs == 0 and self.seg_t0 is None:
                self.t_win0 = now            # restart the clock at the first activity: an idle gap is not a rate
                self.c0 = self._counters()
                self._pf0 = self._pf() if self._ps is not None else None
                self._cpu0 = self._cpu_times() if self._ps is not None else None
            self.seg_t0, self.seg_c0 = now, self._cpu()
            self.cur_items = int(n_items)
            self.items += int(n_items)
            return self
        except Exception:
            self.acc._err()
            return None

    def end(self):
        try:
            now = self.mono()
            if self.seg_t0 is not None:
                self.wall_sum += now - self.seg_t0
                self.cpu_sum += self._cpu() - self.seg_c0
            self.seg_t0 = None
            self.cur_items = 0
            self.flushes += 1
            el = now - self.t_last_emit
            if self.acc.pairs > 0 and el >= cfg("min_gap_s") and (
                    self.flushes >= cfg("flushes_per_line") or el >= cfg("max_silence_s")):
                self.emit("batch")
        except Exception:
            self.acc._err()

    def tick(self, acc):
        """Called from Acc.pair(): the mid-batch line. One monotonic compare per pair."""
        now = self.mono()
        el = now - self.t_last_emit
        if el >= cfg("max_silence_s") and el >= cfg("min_gap_s") and acc.pairs > 0 and self.seg_t0 is not None:
            self.wall_sum += now - self.seg_t0
            self.cpu_sum += self._cpu() - self.seg_c0
            self.seg_t0, self.seg_c0 = now, self._cpu()
            self.emit("interim")

    # ---- the line ----------------------------------------------------------------------------------------------------
    def stats(self):
        """Pure arithmetic over the window so far (tests read this): per-step ms/pair, bound, other."""
        a = self.acc
        n = max(1, a.pairs)
        w, c = a.w, a.c
        S = lambda d, *ks: sum(d.get(k, 0.0) for k in ks)           # noqa: E731
        top_w = S(w, *TOP)
        top_c = S(c, *TOP)
        other_w = max(0.0, self.wall_sum - top_w)
        other_c = max(0.0, self.cpu_sum - top_c)
        steps = {
            "upA": (S(w, "upA", "upA_new"), S(c, "upA", "upA_new")),
            "upB": (S(w, "upB", "upB_new"), S(c, "upB", "upB_new")),
            "link": (S(w, "link"), S(c, "link")),
            "other": (other_w, other_c),
        }
        deep_l = {k: (w.get(k, 0.0), c.get(k, 0.0)) for k in DEEP_LINK if k in w}
        deep_u = {k: (w.get(k, 0.0), c.get(k, 0.0)) for k in DEEP_UP if k in w}
        cand = {}
        cand["other"] = steps["other"]
        if deep_l:
            for k, v in deep_l.items():
                cand[k] = v
            cand["link.rest"] = (max(0.0, steps["link"][0] - sum(v[0] for v in deep_l.values())),
                                 max(0.0, steps["link"][1] - sum(v[1] for v in deep_l.values())))
        else:
            cand["link"] = steps["link"]
        if deep_u:
            for k, v in deep_u.items():
                cand[k] = v
            up_w = steps["upA"][0] + steps["upB"][0]
            up_c = steps["upA"][1] + steps["upB"][1]
            cand["up.rest"] = (max(0.0, up_w - sum(v[0] for v in deep_u.values())),
                               max(0.0, up_c - sum(v[1] for v in deep_u.values())))
        else:
            cand["upA"], cand["upB"] = steps["upA"], steps["upB"]
        bound = max(cand.items(), key=lambda kv: kv[1][0]) if cand else ("none", (0.0, 0.0))
        bw, bc = bound[1]
        cpu_share = min(100.0, (100.0 * bc / bw)) if bw > 0 else 0.0     # tick-granular thread time can exceed wall in a tiny window: cap at 100
        return {
            "pairs": a.pairs, "n": n, "steps_ms": {k: (v[0] * 1000.0 / n, v[1] * 1000.0 / n) for k, v in steps.items()},
            "deep_l_ms": {k: (v[0] * 1000.0 / n, v[1] * 1000.0 / n) for k, v in deep_l.items()},
            "deep_u_ms": {k: (v[0] * 1000.0 / n, v[1] * 1000.0 / n) for k, v in deep_u.items()},
            "total_ms": (self.wall_sum * 1000.0 / n, self.cpu_sum * 1000.0 / n),
            "sum_check": (top_w + other_w, self.wall_sum),
            "bound": bound[0], "bound_cpu_pct": cpu_share,
            "new_up": a.n.get("upA_new", 0) + a.n.get("upB_new", 0),
            "new_up_ms": ((S(w, "upA_new", "upB_new") * 1000.0 / max(1, a.n.get("upA_new", 0) + a.n.get("upB_new", 0))),
                          (S(c, "upA_new", "upB_new") * 1000.0 / max(1, a.n.get("upA_new", 0) + a.n.get("upB_new", 0)))),
            "p50": _pct(a.res, 0.50) * 1000.0, "p95": _pct(a.res, 0.95) * 1000.0,
        }

    def line(self, reason="batch"):
        s = self.stats()
        now = self.mono()
        el = max(1e-6, now - self.t_win0)
        c1 = self._counters()
        c0 = self.c0
        cx = self.owner
        name = getattr(cx, "ACTOR_NAME", "AssociationCortexFairy")
        arr = (c1["queued"] - c0["queued"]) + (c1["drops"] - c0["drops"])
        out = c1["flushed"] - c0["flushed"]
        f = lambda t: "%.1f(%.1f)" % (t[0], t[1])                                  # noqa: E731
        st = s["steps_ms"]
        parts = [
            "[%s] TARDIS-L0 tid=%d win=%ds fl=%d items=%d pairs=%d pairs/s=%.1f q=%d inflight=%d"
            % (name, self.tid, int(el), self.flushes, self.items, s["pairs"], s["pairs"] / el, c1["q"], self.cur_items),
            "in/min=%.1f out/min=%.1f drops=%d%s" % (arr * 60.0 / el, out * 60.0 / el, c1["drops"],
                                                    " (interim)" if reason == "interim" else ""),
            "ms/pair wall(cpu): upA %s upB %s newup %d%% %s link %s" % (
                f(st["upA"]), f(st["upB"]), int(100.0 * s["new_up"] / max(1, 2 * s["pairs"])), f(s["new_up_ms"]), f(st["link"])),
        ]
        if s["deep_l_ms"]:
            parts[-1] += " [" + " ".join("%s %s" % (k, f(v)) for k, v in s["deep_l_ms"].items()) + "]"
        if s["deep_u_ms"]:
            parts[-1] += " [" + " ".join("%s %s" % (k, f(v)) for k, v in s["deep_u_ms"].items()) + "]"
        parts[-1] += " other %s = %s" % (f(st["other"]), f(s["total_ms"]))
        parts.append("p50 %.1f p95 %.1f" % (s["p50"], s["p95"]))
        parts.append("bound=%s(cpu %d%%)%s" % (s["bound"], int(s["bound_cpu_pct"]), " [short window: cpu% is tick-granular]" if self.wall_sum < 1.0 else ""))
        parts.append(self._sys(el))
        a1on = False
        try:
            from infrastructure import tardis_fix as _tf
            a1on = _tf.on("a1_fastlink")
        except Exception:
            pass
        parts.append("a1=%s fast=%d fb=%d" % ("on" if a1on else "off", c1["fast"] - c0["fast"], c1["fb"] - c0["fb"]))
        b = getattr(cx, "_tf_b", None)
        if b is not None:
            try:
                parts.append("b=" + b.status_text())
            except Exception:
                parts.append("b=armed")
        else:
            parts.append("b=off")
        txt = " | ".join(parts)
        return txt.encode("ascii", "replace").decode("ascii")

    def _sys(self, el):
        try:
            if _psutil is None or self._ps is None:
                return "pf/s=n/a ram=n/a sys_cpu=n/a"
            pf1 = self._pf()
            pf = ("%.3g" % ((pf1 - self._pf0) / el)) if (pf1 is not None and self._pf0 is not None) else "n/a"
            ram = "%d%%" % int(_psutil.virtual_memory().percent)
            ct = self._cpu_times()
            if ct is not None and self._cpu0 is not None and ct[1] > self._cpu0[1]:
                sc = "%d%%" % int(100.0 * (ct[0] - self._cpu0[0]) / (ct[1] - self._cpu0[1]))
            else:
                sc = "n/a"
            return "pf/s=%s ram=%s sys_cpu=%s" % (pf, ram, sc)
        except Exception:
            return "pf/s=n/a ram=n/a sys_cpu=n/a"

    def emit(self, reason="batch"):
        """Print one line and roll the window. The reset comes BEFORE the write (a failed write must not pin the window open)."""
        try:
            txt = self.line(reason)
        except Exception:
            self.acc._err()
            txt = None
        now = self.mono()
        self.lines += 1
        self.last_line = txt
        self.acc.reset()
        self.wall_sum = self.cpu_sum = 0.0
        self.flushes = 0
        self.items = 0
        self.t_last_emit = self.t_win0 = now
        self.c0 = self._counters()
        if self._ps is not None:
            self._pf0 = self._pf()
            self._cpu0 = self._cpu_times()
        if txt:
            try:
                self.out(txt)
            except Exception:
                pass


# ---- thread-local plumbing (called by the thin fairy.py hooks) -------------------------------------------------------------
def _mm_module(cx):
    try:
        region = getattr(cx, "_akashic_cortex_region", None)
        if region is None:
            return None
        return sys.modules.get(type(region).__module__)
    except Exception:
        return None


def _mm_tl(cx):
    mod = _mm_module(cx)
    return getattr(mod, "_TF_L0_TL", None) if mod is not None else None


def begin(cx, ftl, n_items):
    """Arm both thread-locals for this batch. Returns the Window (the token for end()) or None. Never raises."""
    try:
        w = getattr(cx, "_tf_l0_w", None)
        if w is None:
            w = Window(owner=cx)
            cx._tf_l0_w = w
        if w.begin(n_items) is None:
            return disarm(cx, ftl)
        ftl.acc = w.acc
        tl = _mm_tl(cx)
        if tl is not None:
            tl.acc = w.acc
        cx._tf_l0_armed = True
        return w
    except Exception:
        return None


def end(cx, ftl, token):
    try:
        ftl.acc = None
        tl = _mm_tl(cx)
        if tl is not None:
            tl.acc = None
        if token is not None:
            token.end()
    except Exception:
        pass


def disarm(cx, ftl):
    """l0_timing is OFF (or L0 latched off): clear any stale arm so no lap is taken. Returns None."""
    try:
        if getattr(cx, "_tf_l0_armed", False):
            ftl.acc = None
            tl = _mm_tl(cx)
            if tl is not None:
                tl.acc = None
            cx._tf_l0_armed = False
    except Exception:
        pass
    return None
