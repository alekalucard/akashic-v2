"""bridge_auth -- the shared-secret check for her PostalHTTPBridge (:8081). 2026-09-30 (Nous, security hole 2).

WHY. http_bridge.py bound 0.0.0.0:8081 with no check and CORS "*". Anyone on the LAN, or any web page open on
PC1, could POST /route {"topic": "ace.message", "payload": {"sender": "Ace", ...}} and she would take it as Ace
speaking; a payload with speaker="ace" pins her attention at 0.9 (InnerNarrator :1306-1314, :1423-1440); and
/intent calls any fairy intent directly.

WHAT. A request that (a) calls /intent, (b) routes a chat-class topic, (c) carries a claim of who spoke anywhere in
its body, or (d) comes from a browser, must carry ONE header

    X-Akashic-Auth: v1:<unix seconds>:<nonce, 32 hex>:<HMAC-SHA256(key, canonical), 64 hex>
    canonical = b"v1\\n" + ts + b"\\n" + nonce + b"\\n" + METHOD + b"\\n" + request-target + b"\\n" + body bytes

The key never crosses the wire. It is 32 random bytes written as 64 hex characters on one line in KEY_FILE
(C:\\Users\\<user>\\.akashic\\bridge_8081.key -- outside every repo), created by apply_her_8081.py. A missing or
malformed key means every privileged request is REFUSED (fail closed); open requests still work.
A signature is valid for MAX_SKEW_S seconds either side of the receiver's clock and only ONCE (nonce cache).

Everything else (satellite telemetry, the room relay's numbers-only records, heartbeats, reads) stays open, so a
sender that does not know about this file keeps working unless it claims a speaker or talks on a chat topic.

stdlib only, no import from her tree: the MCP side loads this file by path (postal_tunnel.py) and the satellite
client imports it next to itself.
"""
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from pathlib import Path

HEADER = "X-Akashic-Auth"
VERSION = "v1"
KEY_FILE = Path.home() / ".akashic" / "bridge_8081.key"
MAX_SKEW_S = 120                 # a signature is accepted within +-120 s of the receiver's clock
NONCE_CACHE_MAX = 8192
SCAN_MAX_DEPTH = 12              # deeper payloads are not vetted, so they need the key
SCAN_MAX_NODES = 20000

# ---------------------------------------------------------------------------------------------- key
_key_cache = {}                  # path -> (mtime_ns, size, key bytes or None)
_key_lock = threading.Lock()


def load_key(path=None):
    """The 32-byte key, or None when the file is missing, unreadable or not exactly 64 hex characters.
    Re-read when the file's mtime or size changes, so a rotated key needs no restart."""
    p = Path(path) if path is not None else KEY_FILE
    try:
        st = p.stat()
    except OSError:
        with _key_lock:
            _key_cache.pop(str(p), None)
        return None
    sig = (st.st_mtime_ns, st.st_size)
    with _key_lock:
        hit = _key_cache.get(str(p))
        if hit is not None and hit[:2] == sig:
            return hit[2]
    key = None
    try:
        txt = p.read_bytes().decode("ascii").strip()
        if re.fullmatch(r"[0-9a-fA-F]{64}", txt):
            key = bytes.fromhex(txt)
    except Exception:
        key = None
    with _key_lock:
        _key_cache[str(p)] = (sig[0], sig[1], key)
    return key


def new_key_hex():
    return secrets.token_hex(32)


# ------------------------------------------------------------------------------------------ signing
def _canonical(ts, nonce, method, target, body):
    return b"\n".join([VERSION.encode("ascii"), str(ts).encode("ascii"), nonce.encode("ascii"),
                       method.upper().encode("ascii"), target.encode("utf-8")]) + b"\n" + (body or b"")


def sign(key, method, target, body, ts=None, nonce=None):
    """Header value for one request. `target` is the request-target exactly as sent (e.g. "/route")."""
    ts = int(time.time()) if ts is None else int(ts)
    nonce = secrets.token_hex(16) if nonce is None else nonce
    mac = hmac.new(key, _canonical(ts, nonce, method, target, body), hashlib.sha256).hexdigest()
    return "%s:%d:%s:%s" % (VERSION, ts, nonce, mac)


def auth_headers(method, target, body, key_file=None):
    """{HEADER: value} when a key is available here, else {} (the request then goes out unsigned)."""
    key = load_key(key_file)
    if not key:
        return {}
    return {HEADER: sign(key, method, target, body)}


class Verifier:
    """Checks X-Akashic-Auth. verify() -> (True, "ok") or (False, reason). Thread-safe."""

    def __init__(self, key_file=None, max_skew_s=MAX_SKEW_S, clock=time.time):
        self.key_file = key_file
        self.max_skew_s = max_skew_s
        self.clock = clock
        self._seen = {}              # nonce -> ts
        self._lock = threading.Lock()

    def key_present(self):
        return load_key(self.key_file) is not None

    def verify(self, value, method, target, body):
        key = load_key(self.key_file)
        if not key:
            return False, "bridge key missing on this machine (%s)" % (self.key_file or KEY_FILE)
        if not isinstance(value, str):
            return False, "auth header is not text"
        parts = value.strip().split(":")
        if len(parts) != 4 or parts[0] != VERSION:
            return False, "auth header is not v1:ts:nonce:mac"
        _v, ts_s, nonce, mac = parts
        if not re.fullmatch(r"[0-9]{1,12}", ts_s) or not re.fullmatch(r"[0-9a-f]{32}", nonce) \
                or not re.fullmatch(r"[0-9a-fA-F]{64}", mac):
            return False, "auth header fields are malformed"
        ts = int(ts_s)
        now = self.clock()
        if abs(now - ts) > self.max_skew_s:
            return False, "auth timestamp is %+.0f s from this clock (limit %d s)" % (ts - now, self.max_skew_s)
        want = hmac.new(key, _canonical(ts, nonce, method, target, body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(want, mac.lower()):
            return False, "bad signature"
        with self._lock:
            if nonce in self._seen:
                return False, "replayed nonce"
            self._seen[nonce] = ts
            if len(self._seen) > 1024:
                floor = now - 2 * self.max_skew_s
                for n in [n for n, t in self._seen.items() if t < floor]:
                    del self._seen[n]
                while len(self._seen) > NONCE_CACHE_MAX:
                    del self._seen[min(self._seen, key=self._seen.get)]
        return True, "ok"


# ------------------------------------------------------------------------------------------- policy
# A topic is CHAT-CLASS when any of its tokens (split on anything not a letter or digit, camelCase split too) is
# one of these, or starts with one of the prefixes. Over-broad on purpose: a false positive only means that
# sender must sign; a false negative is the hole. Every chat/Ace topic subscribed in her tree on 2026-09-30 is
# covered (ace.message, ace.conversation_event, system.chat.message, ace.inbox, gui.user_message,
# chat.user_input, conversation.message, claudefairy.*, wmh.chat.input, sensory.chat.observation,
# audio.speech.transcription, sensory.audio.speech, narrator.*, inner_voice.stream, cognition.input, user.presence,
# ace.presence, nous.inbox, gm.inject_tracer, boot.command, ...) -- see tests/test_her_8081.py.
CHAT_TOKENS = frozenset("""
ace aleka alekalucard chat chats user users human humans person people conversation conversations convo message
messages msg msgs inbox outbox dm dms say says said speech speak speaks speaking speaker spoke voice voices utterance
utterances transcript transcripts transcription stt tts input inputs prompt prompts reply replies question questions
ask asks asked narrator inject injected injection command commands cmd presence hear heard hearing talk talks talking
whisper mention mentions broadcast claudefairy sourpatches sour nous gui typed typing keyboard greeting greet
""".split())
# (no "hear" prefix: it would catch "heartbeat"; hear/heard/hearing are exact tokens above)
CHAT_PREFIXES = ("chat", "convers", "messag", "speak", "speech", "transcri", "utter", "inbox", "outbox", "repl",
                 "narrat", "inject", "command", "prompt", "whisper", "mention", "aleka", "claudefairy", "sourpatch",
                 "voice", "talk", "question", "greet")

# Keys that say WHO spoke. Unsigned requests may not carry them at all, at any depth, whatever the value.
SPEAKER_KEYS = frozenset("""
speaker sender author from from_user user username user_name said_by speaker_id speaker_name speaker_confidence
sender_id sender_name author_id author_name human person who requested_by requester on_behalf_of from_who
""".split())
# Keys that may name a source. Unsigned requests may carry them unless the value names Ace or a human.
SOURCE_KEYS = frozenset("""
source origin name actor identity owner by role voice from_name source_name origin_name
""".split())
ACE_VALUE_TOKENS = frozenset("ace aleka alekalucard human humans user users".split())
ACE_KEY_TOKENS = frozenset("ace aleka alekalucard".split())     # is_ace, from_ace, ace_present, aceSpoke ...
TRACE_KEYS = frozenset("tracer_id tracer trace_id trace".split())
TRACE_ACE = 8                    # infrastructure/manifold_memory.py:185 -- Ace's direct input (chat, voice)
BROWSER_HEADERS = ("Origin", "Referer", "Sec-Fetch-Site", "Sec-Fetch-Mode", "Sec-Fetch-Dest", "Sec-Fetch-User")

_CAMEL = re.compile(r"([a-z0-9])([A-Z])")
_SPLIT = re.compile(r"[^a-z0-9]+")


def tokens(text):
    return [t for t in _SPLIT.split(_CAMEL.sub(r"\1_\2", str(text)).lower()) if t]


def _norm_key(k):
    return "_".join(tokens(k))


def chat_topic_reason(topic):
    """None, or why this topic is chat-class."""
    for t in tokens(topic):
        if t in CHAT_TOKENS:
            return "chat-class topic (token %r)" % t
        for p in CHAT_PREFIXES:
            if t.startswith(p):
                return "chat-class topic (token %r)" % t
    return None


# ----------------------------------------------------------------------------------- the door (2026-10-06, senses_hub)
# Monday item 7 (the 8081 allow-list) + Ace's decision 14 (sense messages are SIGNED; no firewall rule, the LAN stays
# open). An UNSIGNED /route may carry ONLY the open topics below: the .74 satellite's forwards
# (satellite_postal_client.FORWARDED_TOPICS) and its heartbeat. Everything else needs X-Akashic-Auth: control topics
# (system.shutdown_request, system.emergency_shutdown, motor.execute, memory.working.tracer -- the 09-30 verifier note)
# and EVERY sense topic (sensory.*: a startle jolts her, a frame sets her loudness and frustration). The senses hub
# signs; a LAN host without the key gets 403. Read live from <her root>/state/senses_hub.json "door": "strict" (the
# default -- absent, unreadable or malformed is strict: it FAILS CLOSED) or "open" (exactly the 10-01 policy, a
# no-reboot rollback). Only /route topics are affected; /query, /satellite/* and GETs are unchanged.
UNSIGNED_OPEN_TOPICS = frozenset((
    "consciousness.surfacing", "consciousness.collision", "consciousness.collision.system", "memory.ingested",
    "cognition.output", "cognition.inference.complete", "satellite.status", "satellite.heartbeat",
))
# Skeptic F1 (privacy review, 10-06): the 8 open topics carry free text (memory.ingested is an ingest beam), so they
# pass UNSIGNED only from the .74 satellite's own address -- never from loopback or any other LAN host. The switch key
# "open_topics_from" (a list of IP addresses, <= 8) overrides it; [] closes them to everyone (Ace's option (a): once
# the key is copied to .74, its satellite signs and needs no open topic). Absent or malformed = this default.
UNSIGNED_OPEN_FROM = ("192.168.1.74",)
SIGNED_ONLY_PREFIXES = ("sensory.",)
_door_cache = {}


def _door_file():
    try:
        return Path(__file__).resolve().parents[3] / "state" / "senses_hub.json"
    except Exception:
        return None


def _ip_list(v):
    """A list of IP address strings (<= 8) -> tuple; anything else -> None (the caller keeps the default)."""
    if not isinstance(v, list) or len(v) > 8:
        return None
    try:
        import ipaddress as _ipa
        return tuple(str(_ipa.ip_address(x)) for x in v if isinstance(x, str)) if all(isinstance(x, str) for x in v) else None
    except Exception:
        return None


def door_policy(path=None):
    """("strict" | "open", addresses the open topics may come from unsigned). Anything but a readable
    {"door": "open"} is strict; a missing or malformed "open_topics_from" is UNSIGNED_OPEN_FROM."""
    p = Path(path) if path is not None else _door_file()
    if p is None:
        return "strict", UNSIGNED_OPEN_FROM
    try:
        st = p.stat()
    except OSError:
        return "strict", UNSIGNED_OPEN_FROM
    sig = (st.st_mtime_ns, st.st_size)
    with _key_lock:
        hit = _door_cache.get(str(p))
        if hit is not None and hit[:2] == sig:
            return hit[2], hit[3]
    mode, frm = "strict", UNSIGNED_OPEN_FROM
    try:
        import json as _json
        d = _json.loads(p.read_bytes()[:65536].decode("utf-8-sig"))
        if isinstance(d, dict):
            if d.get("door") == "open":
                mode = "open"
            f = _ip_list(d.get("open_topics_from"))
            if f is not None:
                frm = f
    except Exception:
        mode, frm = "strict", UNSIGNED_OPEN_FROM
    with _key_lock:
        _door_cache[str(p)] = (sig[0], sig[1], mode, frm)
    return mode, frm


def door_mode(path=None):
    """"strict" or "open". Anything but a readable {"door": "open"} is strict."""
    return door_policy(path)[0]


def door_reasons(topic, path=None, client_ip=None):
    """Why an UNSIGNED /route of this topic from client_ip is refused by the door. [] = it may pass unsigned.
    An unknown sender address (client_ip None) never passes an open topic (fails closed)."""
    mode, frm = door_policy(path)
    if mode == "open":
        return []
    t = str(topic)
    if t.strip().lower().startswith(SIGNED_ONLY_PREFIXES):
        return ["sense topic %r is signed-only (senses hub, X-Akashic-Auth v1)" % t[:80]]
    if t not in UNSIGNED_OPEN_TOPICS:
        return ["topic %r is not on the unsigned allow-list" % t[:80]]
    ip = str(client_ip or "").strip()
    if ip.lower().startswith("::ffff:"):
        ip = ip[7:]
    if not ip or ip not in frm:
        return ["topic %r passes unsigned only from %s, not from %s" % (t[:80], ", ".join(frm) or "nowhere",
                                                                      ip[:40] or "an unknown address")]
    return []


def _truthy(v):
    if isinstance(v, str):
        return v.strip().lower() not in ("", "0", "false", "no", "none", "null", "off")
    return bool(v)


def identity_claims(obj):
    """Every place in a decoded JSON body that claims who spoke. [] = none. Fails closed on huge/deep bodies."""
    found = []
    stack = [(obj, 0, "")]
    nodes = 0
    while stack:
        cur, depth, where = stack.pop()
        nodes += 1
        if nodes > SCAN_MAX_NODES:
            return found + ["body has more than %d nodes (not vetted)" % SCAN_MAX_NODES]
        if depth > SCAN_MAX_DEPTH:
            return found + ["body nests deeper than %d (not vetted)" % SCAN_MAX_DEPTH]
        if isinstance(cur, dict):
            for k, v in cur.items():
                nk = _norm_key(k)
                here = "%s.%s" % (where, nk) if where else nk
                if nk in SPEAKER_KEYS and v not in (None, "", [], {}):
                    found.append("speaker key %r" % here)
                elif nk in SOURCE_KEYS and isinstance(v, str) and ACE_VALUE_TOKENS.intersection(tokens(v)):
                    found.append("source key %r names a person" % here)
                elif ACE_KEY_TOKENS.intersection(tokens(k)) and _truthy(v):
                    found.append("Ace flag %r" % here)
                elif nk in TRACE_KEYS and str(v).strip() == str(TRACE_ACE):
                    found.append("TRACE_ACE tracer %r" % here)
                if isinstance(v, (dict, list, tuple)):
                    stack.append((v, depth + 1, here))
        elif isinstance(cur, (list, tuple)):
            for i, v in enumerate(cur):
                if isinstance(v, (dict, list, tuple)):
                    stack.append((v, depth + 1, "%s[%d]" % (where, i)))
    return found


def browser_marks(headers):
    """Names of browser-only headers present (a browser can never sign: it does not have the key)."""
    out = []
    for h in BROWSER_HEADERS:
        try:
            if headers.get(h) is not None:
                out.append(h)
        except Exception:
            pass
    return out


def privileged_reasons(method, path, headers, body, client_ip=None):
    """Why this POST needs the key. [] = open. `path` without the query string; `body` = the decoded JSON dict
    the handler will act on (non-dict bodies are treated as {} by the handler)."""
    reasons = []
    marks = browser_marks(headers)
    if marks:
        reasons.append("browser request (%s)" % ", ".join(marks))
    if path == "/intent":
        reasons.append("/intent calls fairy intents directly")
    if path == "/route":
        topic = body.get("topic") if isinstance(body, dict) else None
        if topic is not None and not isinstance(topic, str):
            reasons.append("topic is not a string")
        elif isinstance(topic, str):
            r = chat_topic_reason(topic)
            if r:
                reasons.append(r)
            reasons.extend(door_reasons(topic, client_ip=client_ip))   # 2026-10-06 senses_hub: the door
    # `_intent` is the fabric's own routing field: a bare base-topic envelope is re-targeted by payload["_intent"]
    # on the receiving side (postal_core/tensor_fabric.py:265-270). publish() overwrites it today (:333-338), but
    # no outside sender has a reason to set it, so an unsigned request may not.
    carried = (body.get("payload") if path == "/route" else body) if isinstance(body, dict) else None
    if path in ("/route", "/satellite/heartbeat") and isinstance(carried, dict) and "_intent" in carried:
        reasons.append("payload sets the internal routing key _intent")
    if path in ("/route", "/satellite/heartbeat", "/intent"):
        reasons.extend(identity_claims(body))
    return reasons
