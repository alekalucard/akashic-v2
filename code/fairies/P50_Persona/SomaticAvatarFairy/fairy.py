"""
SomaticAvatarFairy -- her self-image: the display engine inside, a recogniser that can say no, her look as facts.

2026-10-05 (Nous; avatar_identity build, Ace's decisions 10-05). nous_builds/avatar_identity/{TRACE,SKEPTIC,PROPOSAL}.md:
from ~03-10 to Boot G the registry booted the display engine (avatar/somatic_avatar_fairy.py) STANDALONE in place of
this file -- both say ACTOR_NAME "SomaticAvatarFairy" and the early scan keeps the first one it finds
(server.py:4955-4961; 'avatar\\' sorts first). This file never ran. Its old matcher (keyword substrings, threshold 1 on
'sourpatches') would have said "I see myself on screen" on ~980 of Boot G's 1,391 screen reads, so it was replaced
BEFORE the one-line switch that lets this file boot (avatar/somatic_avatar_fairy.py:94, applied last).

THE SWITCH: state/avatar_identity.json, read by self_image.read_switch. Absent, unreadable, or "on" not true = OFF.
  OFF  = TODAY'S BEHAVIOUR. The display engine is built exactly as the registry built it, AV(fabric) with its defaults
         (it subscribes, prints, and runs its old name counter to 'avatar.self_recognized', which nobody reads). This
         shell starts nothing, reads nothing from the folder, writes nothing, publishes nothing.
  ON   = the engine inside, silent (auto_subscribe=False: its substring matcher never runs) and its emotion->named-costume
         selector OFF (enable_form_switching=False; later she picks her own costume as a deed). One thread of ours:
           * her pictures indexed (self_image.PictureIndex, read only); calibration.json read for the log only --
             no fact is taken from it (its flower crown / corset dress are in none of her pictures);
           * her look written ONCE as facts in Ace's words (self_facts.FactWriter: self:look*, TRACE_SEEDED), retried
             until her cortex is up; "facts": "undo" blanks them. A memory of ACE SAYING it (self_facts.ACE_TURN,
             rendered "You remember Ace said ...") is woven only with "ace_turn": true -- his yes to those exact words;
           * every cycle_s (and on a front-window change): self_image.Recogniser -- T0 her name in a window title that
             is not hers, T1 her pictures by fingerprint, T2 a grounded hair region's colour (SHADOW ONLY, always);
             ONE score that decays on the clock; hits AND misses counted;
           * every report_s: one counts line + state/avatar_identity_report.json.
         "mode": "shadow" (what the installer writes; the FIRST boot, Ace 10-05) -- counted and logged, NOTHING
         published: no 'self.visual.recognition', no 'consciousness.working', no 'cortex.bind', nothing said.
         "mode": "live" (Ace edits it after reviewing the counts; read live) -- a T1 picture hit publishes ONE
         'self.visual.recognition' (type self_recognition, confidence 0.9, source picture:<stem>) per picture per
         republish_s; a T0 name publishes 'self.text.reference' (never "I see myself"); T2 never publishes.
         "on" itself is read at boot (it decides how the engine is built) and every cycle (off = the cycle idles).
  The thread starts from __init__ ("start_in_coma", default true): her launcher boots with AKASHIC_COMA=1 and only
  AKASHIC_WAKE / AKASHIC_WAKE_PLANES=P20 fairies run on_boot (Organ_Template_0_3_0.py:3426-3477, :3571-3580). P50's
  SomaticAvatarFairy is in neither, so an on_boot-only start would leave this file booted and silent -- the display
  engine has always done its work in __init__, and this keeps that. on_boot starts it too (idempotent).
"""

import sys
import json
import os
import time
import importlib.util
import threading
from pathlib import Path

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# ═══════════════════════════════════════════════════════════════════════════════
# LOAD THE REAL MODULE (flat name -- avoids package resolution / relative imports)
# ═══════════════════════════════════════════════════════════════════════════════

_avatar_dir = Path(__file__).parent.parent / "avatar"
_real_path = _avatar_dir / "somatic_avatar_fairy.py"

_flat_name = "_somatic_avatar_impl"
_RealClass = None

if _real_path.exists():
    try:
        if _flat_name not in sys.modules:
            _spec = importlib.util.spec_from_file_location(_flat_name, str(_real_path))
            _mod = importlib.util.module_from_spec(_spec)
            sys.modules[_flat_name] = _mod
            _spec.loader.exec_module(_mod)
        else:
            _mod = sys.modules[_flat_name]
        _RealClass = getattr(_mod, "SomaticAvatarFairy", None)
    except Exception as _e:
        print(f"[SomaticAvatarFairy] Could not load real module: {_e}")
        _RealClass = None


# ═══════════════════════════════════════════════════════════════════════════════
# AVATAR IDENTITY (2026-10-05): switch, helpers, paths
# ═══════════════════════════════════════════════════════════════════════════════

_ASSETS = _avatar_dir / "assets" / "sourpatches"
_SWITCH_PATH = ROOT / "state" / "avatar_identity.json"
_JOURNAL_PATH = ROOT / "state" / "avatar_identity_facts.json"
_REPORT_PATH = ROOT / "state" / "avatar_identity_report.json"


def _load_flat(name, path):
    """The engine's own loading pattern (above): a flat module name, never a package import."""
    mod = sys.modules.get(name)
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


def _helpers():
    return (_load_flat("_avatar_self_image", _avatar_dir / "self_image.py"),
            _load_flat("_avatar_self_facts", _avatar_dir / "self_facts.py"))


def switch_now(path=None):
    """None = OFF (today's behaviour). Any failure, including a missing helper file, reads as OFF."""
    try:
        si, _sf = _helpers()
        return si.read_switch(str(path or _SWITCH_PATH))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class SomaticAvatarFairyShadow:
    """Shadow for SomaticAvatarFairy — monitors self-image health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "SomaticAvatarFairyShadow"
    SHADOW_VERSION = "0.3.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        a = self.actor
        tests = []
        tests.append(("identity_on", getattr(a, '_identity', None) is not None))
        tests.append(("calibration_loaded", bool(getattr(a, '_calibration', None))))
        tests.append(("pictures_indexed", len(getattr(a, '_index', None) or [])))
        tests.append(("facts", str((getattr(a, '_facts_result', None) or {}).get("result", "-"))))
        tests.append(("cycles", getattr(a, '_cycles', 0)))
        tests.append(("published", getattr(a, '_pubs', 0)))
        tests.append(("engine_loaded", getattr(a, '_engine', None) is not None))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class SomaticAvatarFairyV3(Fairy):
    """
    Her self-image. The display engine runs inside; when the avatar identity is ON, a recogniser that can fail
    (her name, her pictures, a shadow hair check; one decaying score) and her look as facts in Ace's words.
    """

    ACTOR_NAME = "SomaticAvatarFairy"
    ACTOR_VERSION = "3.0.0"
    ACTOR_PLANE = "P50"
    ACTOR_CHANNEL = "persona.avatar"

    PURPOSE = "Visual self-image -- know what I look like, and know when it is really me on the screen"
    MANTRA = "I know my own face"
    LORE = "The mirror of the soul - seeing yourself in the world trains the felt sense of self"

    SHADOW_CLASS = SomaticAvatarFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 4  # Every 4th heartbeat
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None
        self._calibration = {}
        self._identity = None                 # the switch as read at boot (None = OFF = today's behaviour)
        self._started = False
        self._start_lock = threading.Lock()
        self._stop = threading.Event()
        self._index = None
        self._recog = None
        self._facts = None
        self._facts_result = None
        self._facts_next = 0.0
        self._facts_undone = False
        self._facts_wait_log = 0.0
        self._screen = None                   # self_image.LiveScreen (tests inject a fake)
        self._cortex_fn = None                # self_facts.cortex_handle (tests inject a temp manifold)
        self._cycles = 0
        self._pubs = 0
        self._rec_n = 0                       # live self-recognitions actually published (tool_bridge's "#n")
        self._t2_log = 0.0
        self._identity = switch_now()
        if self._identity is None:
            # OFF = TODAY'S BEHAVIOUR: the display engine exactly as the registry built it from 03-10 to Boot G,
            # AV(fabric) with its defaults. Nothing else.
            if _RealClass is not None:
                try:
                    self._engine = _RealClass(fabric)
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] display engine unavailable (non-fatal): {e}", flush=True)
            return
        if _RealClass is not None:
            try:
                base_img = _ASSETS / "sourpatches_base.jpg"
                self._engine = _RealClass(
                    image_path=str(base_img) if base_img.exists() else "",
                    name="Sourpatches",
                    auto_subscribe=False,             # its old substring matcher never runs (AV:136-137, :171-216)
                    enable_form_switching=False,      # the emotion->named-costume selector is OFF (AV:103, :139-141)
                )
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] display engine unavailable (non-fatal): {e}", flush=True)
        if self._identity.get("start_in_coma", True):
            self._start("init")

    def on_boot(self) -> bool:
        super().on_boot()
        if self._identity is None:
            print(f"[{self.ACTOR_NAME}] avatar identity OFF (state/avatar_identity.json absent or off): "
                  f"the display engine runs as before", flush=True)
            return True
        self._start("on_boot")
        return True

    def _start(self, why: str) -> bool:
        with self._start_lock:
            if self._started:
                return False
            self._started = True
        try:
            si, _sf = _helpers()
            if not si.claim_runner(id(self)):
                print(f"[{self.ACTOR_NAME}] avatar identity already runs in another copy of this fairy in this "
                      f"process; this copy stays quiet", flush=True)
                return False
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] avatar identity helpers did not load ({e}): nothing runs", flush=True)
            return False
        mode = (self._identity or {}).get("mode", "shadow")
        print(f"[{self.ACTOR_NAME}] avatar identity ON ({mode}{': counted, nothing said' if mode != 'live' else ''})"
              f" -- starting from {why}", flush=True)
        threading.Thread(target=self._run, daemon=True, name="avatar-identity").start()
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # the one thread
    # ─────────────────────────────────────────────────────────────────────────

    def _run(self, clock=time.time):
        k = self._identity or {}
        if self._stop.wait(float(k.get("start_delay_s", 3.0))):
            return
        try:
            si, sf = _helpers()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] avatar identity helpers did not load ({e}): nothing runs", flush=True)
            return
        self._load_calibration()
        try:
            self._index = si.PictureIndex(str(_ASSETS))
            print(f"[{self.ACTOR_NAME}] her pictures: {len(self._index)} indexed by fingerprint; the nearest two are "
                  f"{self._index.min_pair_bits()} of 64 bits apart (a hit is <= {k.get('t1_max_bits')})"
                  + (f"; NOT indexed (not her 11 pinned pictures): {self._index.skipped[:6]}" if self._index.skipped else ""),
                  flush=True)
        except Exception as e:
            self._index = None
            print(f"[{self.ACTOR_NAME}] her pictures could not be indexed ({e}): T1 is off this boot", flush=True)
        self._recog = si.Recogniser(self._index, k)
        self._facts = sf.FactWriter(str(_JOURNAL_PATH), [it[0] for it in (self._index.items if self._index else [])])
        if self._screen is None:
            self._screen = si.LiveScreen(str(ROOT))
        last_cycle, last_poll, last_front, last_report = 0.0, 0.0, None, clock()
        while not self._stop.is_set():
            try:
                now = clock()
                sw = switch_now()
                if sw is None:                       # turned off live: no grabs, no writes, no publishes
                    self._stop.wait(2.0)
                    continue
                self._recog.set_knobs(sw)
                self._facts_step(sf, sw, now)
                if now - last_poll >= sw["front_poll_s"]:
                    last_poll = now
                    wins = self._screen.windows()
                    front = next((w.get("title") for w in wins if w.get("front")), None)
                    if now - last_cycle >= sw["cycle_s"] or front != last_front:
                        last_cycle, last_front = now, front
                        self._cycle(si, sf, now, wins, sw)
                if now - last_report >= sw["report_s"]:
                    last_report = now
                    self._report(sf, now, sw)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] avatar identity cycle error (non-fatal): {e}", flush=True)
            self._stop.wait(0.5)

    def _load_calibration(self):
        """Read only, for the log. No fact is taken from it (Ace 10-05)."""
        try:
            with open(_ASSETS / "calibration.json", "r", encoding="utf-8") as f:
                self._calibration = json.load(f)
            print(f"[{self.ACTOR_NAME}] Calibration loaded (read only): {len(self._calibration)} fields; her look comes "
                  f"from Ace's words, not this file", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Calibration not loaded ({e})", flush=True)

    def _cortex(self, sf):
        return (self._cortex_fn or sf.cortex_handle)()

    def _facts_step(self, sf, sw, now):
        want = sw.get("facts", True)
        if want is False or self._facts is None:
            return
        want_turn = sw.get("ace_turn") is True
        if want == "undo":
            if self._facts_undone:
                return
            am = self._cortex(sf)
            if am is None:
                return
            r = self._facts.undo(am, now)
            self._facts_undone = True
            self._facts_result = r
            print(f"[{self.ACTOR_NAME}] SELF-FACTS undo: {r}", flush=True)
            return
        d = self._facts.done
        if now < self._facts_next or (d is not None and (not want_turn or d.get("turn")
                                                          or d.get("result") == "revised_by_her")):
            return
        am = self._cortex(sf)
        if am is None:
            self._facts_next = now + 5.0
            if now - self._facts_wait_log >= 60.0:
                self._facts_wait_log = now
                print(f"[{self.ACTOR_NAME}] SELF-FACTS waiting for her cortex", flush=True)
            return
        r = self._facts.write(am, now, ace_turn=want_turn)
        self._facts_result = r
        if r.get("result") not in ("written", "in_place", "revised_by_her") or (want_turn and not r.get("turn")
                                                                                and r.get("result") != "revised_by_her"):
            self._facts_next = now + 60.0
        print(f"[{self.ACTOR_NAME}] SELF-FACTS {r.get('result')}: {self._facts_line(r)}", flush=True)

    @staticmethod
    def _turn_words(r):
        if r.get("turn"):
            return "Ace's approved words woven as %s" % r.get("turn")
        return "no memory of Ace saying it (\"ace_turn\" is off until Ace approves the words)"

    @classmethod
    def _facts_line(cls, r):
        if r.get("result") == "written":
            return ("%d of %d nodes, %d of %d typed edges; %s%s"
                    % (r.get("nodes", 0), r.get("nodes_planned", 0), r.get("edges_ok", 0), r.get("edges_planned", 0),
                       cls._turn_words(r), (" -- REFUSED: %s" % ", ".join(r["refused"])) if r.get("refused") else ""))
        if r.get("result") == "in_place":
            return "already in her memory (journal + her self:look node agree); %s" % cls._turn_words(r)
        if r.get("result") == "revised_by_her":
            return "her own memory has rewritten it (owner %s); left alone" % r.get("owner")
        return str(r)

    def _cycle(self, si, sf, now, wins, sw):
        mode = sw.get("mode", "shadow")
        grab = None
        try:
            if any(not si.own_window(w.get("title", ""), w.get("cls", "")) for w in wins):
                grab = self._screen.grab()                     # in memory only; dropped below
            look = self._screen.hair_look()
            strip = self._screen.strip_active()
            d = self._recog.observe(now, wins, grab, look, strip)
        finally:
            grab = None
        self._cycles += 1
        said = "" if mode == "live" else " -- counted, not said"
        for p in d["publish"]:
            if p["topic"] == "self.visual.recognition":
                print(f"[{self.ACTOR_NAME}] SELF-IMAGE {mode} T1 #{p['n']}: picture match '{p['stem']}' at {p['bits']} "
                      f"bits in {p['window']} (score {p['score']:.2f}){said}", flush=True)
            else:
                print(f"[{self.ACTOR_NAME}] SELF-IMAGE {mode} T0: name match in title '{p['title'][:80]}' (a reference, "
                      f"not a sighting){said}", flush=True)
        t2 = d["analysis"].get("t2")
        if t2 and t2.get("evidence") and now - self._t2_log >= 60.0:
            self._t2_log = now
            print(f"[{self.ACTOR_NAME}] SELF-IMAGE T2 (shadow, never said): a hair region is {t2.get('why')}", flush=True)
        if mode == "live":
            for p in d["publish"]:
                self._publish(sf, p, now)

    def _publish(self, sf, p, now):
        if not self.post:
            return
        try:
            if p["topic"] == "self.visual.recognition":
                self._rec_n += 1
                self.post.publish("self.visual.recognition", {
                    "type": "self_recognition",
                    "source": "picture:%s" % p["stem"],
                    "confidence": 0.9,
                    "description": "one of your own pictures (%s) is open on the screen, in %s" % (p["stem"], p["window"]),
                    "matched_keywords": 0,
                    "scene_type": "picture",
                    "recognition_number": self._rec_n,
                    "timestamp": now,
                    "actor": self.ACTOR_NAME,
                    "bits": p["bits"],
                    "via_own_deed": False,
                })
                try:
                    am = self._cortex(sf)
                    if am is not None:
                        am.touch_node(sf.picture_key(p["stem"]), 0.3)   # the picture lights its node -> her features
                except Exception:
                    pass
            elif p["topic"] == "self.text.reference":
                self.post.publish("self.text.reference", {
                    "type": "name_reference", "title": p["title"][:120], "window": p.get("window", ""),
                    "ts": now, "actor": self.ACTOR_NAME,
                })
            self._pubs += 1
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] publish error: {e}", flush=True)

    def _report(self, sf, now, sw):
        line, rec = self._recog.report(now, sw.get("mode", "shadow"))
        rec["facts"] = self._facts_result
        rec["published"] = self._pubs
        print(f"[{self.ACTOR_NAME}] {line}", flush=True)
        try:
            sf._atomic_json(str(_REPORT_PATH), rec)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] report file not written: {e}", flush=True)

    # ─────────────────────────────────────────────────────────────────────────
    # HEARTBEAT / SHUTDOWN
    # ─────────────────────────────────────────────────────────────────────────

    def on_tick(self, beat):
        """Liveness only: our work runs on our own thread (a comatose fairy's ticks never fire)."""
        pass

    def _release(self):
        self._stop.set()
        try:
            _helpers()[0].release_runner(id(self))
        except Exception:
            pass

    def on_shutdown(self) -> bool:
        self._release()
        return super().on_shutdown()

    def on_die(self):
        """Clean shutdown."""
        self._release()
        if self._engine and hasattr(self._engine, 'stop'):
            try:
                self._engine.stop()
            except Exception:
                pass
        try:
            super().on_die()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

ACTOR_NAME = "SomaticAvatarFairy"
FAIRY_CLASS = SomaticAvatarFairyV3
