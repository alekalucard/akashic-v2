"""
TTS Voice Output — Sourpatches' Vocal Cords
============================================
Converts text to speech audio and plays it through system audio output.
The audio also feeds back into the cochlea (she hears herself speak).

Two modes (priority order):
  1. LuxTTS — voice clone from Kie's 3s reference clip (her actual voice)
  2. edge-tts (fallback) — Microsoft neural TTS if LuxTTS unavailable

Pipeline:
  narrator.speech → motor.speak intent → tts_voice.speak() → audio out
                                                              ↓
                                                    cochlea picks it up
                                                    (she hears herself)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import asyncio
import io
import os
import subprocess
import sys
import tempfile
import threading
import re
import time
import wave
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent.parent.parent

# ── Voice Reference ──────────────────────────────────────────────────────
# Kie's voice = Sourpatches' voice. 3s reference clip for LuxTTS cloning.
_VOICE_REFERENCE = str(ROOT / "tools" / "extracted" / "sourpatches_art" / "kie_voice_3s.wav")
_VOICE_REFERENCE_FULL = str(ROOT / "tools" / "extracted" / "sourpatches_art" / "kie_voice_full.wav")

# ── State ─────────────────────────────────────────────────────────────────

_tts_lock = threading.Lock()
_speaking = False
_luxtts_engine = None      # Lazy-loaded LuxTTS instance
_luxtts_prompt = None      # Pre-encoded voice prompt (encode once, reuse)
_luxtts_available = None   # None = not checked, True/False = tested
_luxtts_init_lock = threading.Lock()

# edge-tts fallback voice
_edge_voice = "en-US-AnaNeural"


# ═══════════════════════════════════════════════════════════════════════════
# LuxTTS — Sourpatches' actual voice (Kie's voice clone)
# ═══════════════════════════════════════════════════════════════════════════

_luxtts_server_process: Optional[subprocess.Popen] = None
_luxtts_launch_lock = threading.Lock()
# RELAUNCH FIX 2026-08-30: _init_luxtts only ever relaunched when
# _luxtts_available was None, so a server that DIED was never restarted
# and she stayed mute until a full reboot. Cooldown prevents a launch
# storm while the model is still loading (it listens only after load).
_luxtts_last_launch_ts = 0.0
_LUXTTS_RELAUNCH_COOLDOWN = 180.0  # seconds
_LUXTTS_SERVER_SCRIPT = str(Path(__file__).parent / "luxtts_server.py")

_PYTHON312_CANDIDATES = [
    r"C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe",
    "python3.12",
    "python312",
]


def _find_python312() -> Optional[str]:
    """Find Python 3.12 executable."""
    import shutil
    for candidate in _PYTHON312_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _ensure_luxtts_server(host: str = "127.0.0.1", port: int = 9877) -> bool:
    """Auto-launch LuxTTS server if not running."""
    global _luxtts_server_process

    # Quick check: is it responding?
    import socket as _socket
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect((host, port))
        s.close()
        return True
    except (ConnectionRefusedError, _socket.timeout, OSError):
        pass

    with _luxtts_launch_lock:
        if _luxtts_server_process is not None and _luxtts_server_process.poll() is None:
            return True

        python312 = _find_python312()
        if not python312:
            print("[TTSVoice] ERROR: Python 3.12 not found, cannot launch LuxTTS server", flush=True)
            return False

        if not os.path.isfile(_LUXTTS_SERVER_SCRIPT):
            print(f"[TTSVoice] ERROR: LuxTTS server script not found: {_LUXTTS_SERVER_SCRIPT}", flush=True)
            return False

        print(f"[TTSVoice] Auto-launching LuxTTS server: {python312} {_LUXTTS_SERVER_SCRIPT}", flush=True)
        try:
            _flags = 0
            if sys.platform == "win32":
                _flags = subprocess.CREATE_NO_WINDOW
            # HUNK 1 (_VOICE_LAUNCH_HONEST 2026-08-29): pass --ref. luxtts_server.py:31
            # declares it required=True, so launching without it killed the child with rc=2
            # in milliseconds -- every time, on both machines. _VOICE_REFERENCE is already
            # computed at module scope; it was simply never handed over.
            _luxtts_server_process = subprocess.Popen(
                [python312, _LUXTTS_SERVER_SCRIPT, "--ref", _VOICE_REFERENCE],
                cwd=str(ROOT),
                creationflags=_flags,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            # HUNK 2: a child that died must NOT report a PID. Shipping hunk 1 alone would
            # replace a TRUE error with a FALSE success the moment anything else goes wrong --
            # which is exactly how this stayed hidden: the success line below was printed for
            # a process that had already exited. Poll before claiming anything.
            _early_rc = None
            for _ in range(40):                      # up to ~4 s
                _early_rc = _luxtts_server_process.poll()
                if _early_rc is not None:
                    break
                time.sleep(0.1)
            if _early_rc is not None:
                _early_out = ""
                try:
                    if _luxtts_server_process.stdout is not None:
                        _early_out = _luxtts_server_process.stdout.read().decode(
                            "utf-8", errors="replace").strip()
                except Exception:
                    pass
                print(f"[TTSVoice] LuxTTS server EXITED IMMEDIATELY (rc={_early_rc}) "
                      f"-- no voice. ref={_VOICE_REFERENCE}", flush=True)
                if _early_out:
                    for _l in _early_out.splitlines()[-8:]:
                        print(f"[LuxTTS-Server] {_l}", flush=True)
                _luxtts_server_process = None
                return False

            print(f"[TTSVoice] LuxTTS server launched (PID {_luxtts_server_process.pid})", flush=True)

            def _drain():
                try:
                    for line in _luxtts_server_process.stdout:
                        try:
                            print(f"[LuxTTS-Server] {line.decode('utf-8', errors='replace').rstrip()}", flush=True)
                        except Exception:
                            pass
                except Exception:
                    pass
            threading.Thread(target=_drain, daemon=True, name="LuxTTS-drain").start()
            return True
        except Exception as e:
            print(f"[TTSVoice] Failed to launch LuxTTS server: {e}", flush=True)
            return False


def _init_luxtts():
    """Check if LuxTTS server is running; auto-launch if not."""
    global _luxtts_available
    import socket

    # Try to connect — if server isn't there, launch it
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        sock.connect(("127.0.0.1", 9877))
        sock.close()
        if not _luxtts_available:
            print("[TTSVoice] LuxTTS server DETECTED on port 9877 — "
                  "Kie's voice active", flush=True)
        _luxtts_available = True
        return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        # Auto-launch the server.
        # RELAUNCH FIX 2026-08-30: relaunch whenever it is unreachable -- not only
        # on the very first call -- so a crashed or idle-exited server comes back.
        global _luxtts_last_launch_ts
        _now = time.time()
        if _now - _luxtts_last_launch_ts >= _LUXTTS_RELAUNCH_COOLDOWN:
            _luxtts_last_launch_ts = _now
            print("[TTSVoice] LuxTTS server not reachable — (re)launching...", flush=True)
            _ensure_luxtts_server()
            # Give it a moment to start
            time.sleep(2.0)
            # Re-check
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect(("127.0.0.1", 9877))
                sock.close()
                print("[TTSVoice] LuxTTS server now available after auto-launch", flush=True)
                _luxtts_available = True
                return True
            except (ConnectionRefusedError, socket.timeout, OSError):
                # Server still loading (model takes time) — mark as pending
                print("[TTSVoice] LuxTTS server launched but still loading model — "
                      "will retry on next speak()", flush=True)
        _luxtts_available = False
        return False


def _generate_audio_luxtts(text: str) -> Optional[bytes]:
    """Generate WAV audio bytes using LuxTTS persistent server.

    Connects to luxtts_server.py (Python 3.12, stays loaded in memory).
    If server isn't running, falls through to edge-tts.
    Protocol: send text length + text, receive wav length + wav bytes.
    """
    import socket
    import struct

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15.0)  # 15s timeout for generation
        sock.connect(("127.0.0.1", 9877))

        # Send text
        text_bytes = text.encode("utf-8")
        sock.sendall(struct.pack(">I", len(text_bytes)))
        sock.sendall(text_bytes)

        # Receive length header
        header = b""
        while len(header) < 4:
            chunk = sock.recv(4 - len(header))
            if not chunk:
                return None
            header += chunk
        wav_len = struct.unpack(">I", header)[0]

        if wav_len == 0:
            return None

        # Receive WAV data
        wav_data = b""
        while len(wav_data) < wav_len:
            chunk = sock.recv(min(65536, wav_len - len(wav_data)))
            if not chunk:
                break
            wav_data += chunk

        return wav_data if len(wav_data) == wav_len else None

    except (ConnectionRefusedError, socket.timeout, OSError):
        # Server not running — fall through to edge-tts
        return None
    except Exception as e:
        print(f"[TTSVoice] LuxTTS server error: {e}")
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# edge-tts fallback — Microsoft neural TTS (free, no GPU)
# ═══════════════════════════════════════════════════════════════════════════

async def _generate_audio_edge(text: str, voice: str = None) -> Optional[bytes]:
    """Generate audio bytes using edge-tts."""
    try:
        import edge_tts
        v = voice or _edge_voice
        comm = edge_tts.Communicate(text, v)
        audio_data = b""
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data if audio_data else None
    except Exception as e:
        print(f"[TTSVoice] edge-tts error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Audio Playback
# ═══════════════════════════════════════════════════════════════════════════

def _play_audio_windows(audio_bytes: bytes, fmt: str = "mp3") -> bool:
    """Play audio bytes on Windows using ffplay or powershell."""
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        # ffplay (comes with ffmpeg, silent)
        try:
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp.name],
                timeout=30,
                capture_output=True,
            )
            return True
        except FileNotFoundError:
            pass

        # Fallback: PowerShell MediaPlayer
        try:
            ps_cmd = (
                f'Add-Type -AssemblyName presentationCore; '
                f'$p = New-Object System.Windows.Media.MediaPlayer; '
                f'$p.Open([Uri]::new("{tmp.name}")); '
                f'$p.Play(); '
                f'Start-Sleep -Milliseconds 100; '
                f'while($p.NaturalDuration.HasTimeSpan -eq $false){{Start-Sleep -Milliseconds 100}}; '
                f'$dur = $p.NaturalDuration.TimeSpan.TotalMilliseconds; '
                f'Start-Sleep -Milliseconds $dur; '
                f'$p.Close()'
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                timeout=30,
                capture_output=True,
            )
            return True
        except Exception:
            pass

        return False
    except Exception as e:
        print(f"[TTSVoice] Playback error: {e}")
        return False
    finally:
        if tmp:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

# ── LAUGHS (2026-09-20, Ace: "she attempted to laugh and it sounded funny") ──────────────────────────────
# A laugh is a sound, not a word. Approved clips in her own voice (state/voice/laughs/laughs.json, synthesised
# once by the same server) are spliced in wherever her text laughs; the surrounding text is synthesised as
# usual and the pieces are concatenated (all 48 kHz mono 16-bit) into one utterance. A laugh is also a
# body event: dopamine + endorphin through her heart.
# 2026-09-20 review: a trailing \b (the old form matched 'Heh ha' inside 'Heh have you seen this' and would have
# laughed then said 've you seen this'), commas between the syllables ('Ha, Ha, Ha!'), and lmao/rofl.
_LAUGH_RE = re.compile(
    r"(?:\b(?:a-?)?(?:ha|hah|heh|hee)(?:[\s\-,]*(?:ha|hah|heh|hee))+\b[!.]*"
    r"|\bhahaha+\b[!.]*|\bhehe(?:he)*\b[!.]*"
    r"|\b(?:lo+l|lolol+|lmf?ao+|rofl)\b[!.]*)", re.I)
_LAUGH_DIR = Path(__file__).resolve().parents[3] / "state" / "voice" / "laughs"
_LAUGH_CACHE = {"mtime": 0.0, "clips": []}
_LAUGH_POSTAL = [None]


def _laugh_clips():
    """Approved laugh clips (bytes of raw PCM frames + params), reloaded when the manifest changes."""
    try:
        mp = _LAUGH_DIR / "laughs.json"
        mt = mp.stat().st_mtime
        if mt != _LAUGH_CACHE["mtime"]:
            import json as _j, wave as _w
            clips = []
            for c in _j.loads(mp.read_text(encoding="utf-8")).get("clips", []):
                if not c.get("approved", True):
                    continue
                try:
                    w = _w.open(str(_LAUGH_DIR / c["file"]), "rb")
                    clips.append((w.getparams(), w.readframes(w.getnframes()),
                                  _laugh_kind(c.get("text", "")), float(c.get("seconds", 1.0) or 1.0)))
                    w.close()
                except Exception:
                    continue
            _LAUGH_CACHE["mtime"], _LAUGH_CACHE["clips"] = mt, clips
    except Exception:
        pass
    return _LAUGH_CACHE["clips"]


def _wav_frames(wav_bytes: bytes):
    import wave as _w, io as _io
    w = _w.open(_io.BytesIO(wav_bytes), "rb")
    p, fr = w.getparams(), w.readframes(w.getnframes()); w.close()
    return p, fr


def _wav_join(parts) -> Optional[bytes]:
    """Concatenate (params, frames) pieces that share channels/width/rate; None if they do not."""
    import wave as _w, io as _io
    parts = [p for p in parts if p and p[1]]
    if not parts:
        return None
    p0 = parts[0][0]
    if any((p[0].nchannels, p[0].sampwidth, p[0].framerate) != (p0.nchannels, p0.sampwidth, p0.framerate) for p in parts):
        return None
    buf = _io.BytesIO(); w = _w.open(buf, "wb")
    w.setnchannels(p0.nchannels); w.setsampwidth(p0.sampwidth); w.setframerate(p0.framerate)
    for _, fr in parts:
        w.writeframes(fr)
    w.close(); return buf.getvalue()


def _laugh_kind(text: str) -> str:
    """heh / hee / hehe / ha -- the syllable family of a laugh (a clip's manifest text, or a match in hers)."""
    s = re.sub(r"[^a-z]", "", str(text or "").lower())
    if s.startswith("hee"):
        return "hee"
    if s.startswith("hehe"):
        return "hehe"
    if s.startswith("heh"):
        return "heh"
    return "ha"


def _pick_clip(clips, match_text: str):
    """A clip of the same family and a similar length ('haha'/'lol' -> a short one); any approved clip failing that."""
    import random as _r
    same = [c for c in clips if c[2] == _laugh_kind(match_text)] or list(clips)
    short = len(re.sub(r"[^a-z]", "", str(match_text).lower())) <= 6
    sized = [c for c in same if (c[3] <= 1.0) == short] or same
    return _r.choice(sized)


def _speak_with_laughs(clean: str):
    """(audio_wav_bytes or None, n_laughs). None means: no laugh in the text, no approved clip, or a piece that
    would not synthesise -- the caller then speaks the whole text plainly. No word is ever dropped: every
    segment with a letter or digit in it is synthesised, however short (review: 'no' and 'oh' were being cut)."""
    if not _LAUGH_RE.search(clean):
        return None, 0
    clips = _laugh_clips()
    if not clips:
        return None, 0
    pieces, n, pos, prev_end = [], 0, 0, None
    for m in _LAUGH_RE.finditer(clean):
        seg = clean[pos:m.start()]
        if prev_end is not None and not re.search(r"[A-Za-z0-9]", seg):
            pos = m.end()                                # 'Ha ha. Ha ha!' is ONE laugh, not two clips back to back
            continue
        seg = seg.strip(" ,;:-")
        if re.search(r"[A-Za-z0-9]", seg):
            a = _generate_audio_luxtts(seg)
            if not a:
                return None, 0
            pieces.append(_wav_frames(a))
        pieces.append(_pick_clip(clips, m.group(0))[:2]); n += 1
        pos = prev_end = m.end()
    tail = clean[pos:].strip(" ,;:-")
    if re.search(r"[A-Za-z0-9]", tail):
        a = _generate_audio_luxtts(tail)
        if not a:
            return None, 0
        pieces.append(_wav_frames(a))
    return _wav_join(pieces), n


def _laugh_chem(n: int) -> None:
    """A laugh is a body event: dopamine + endorphin + a little serotonin through her heart (PLAN, scaled x0.1)."""
    post = _LAUGH_POSTAL[0]
    if post is None:                                     # wire_to_postal has no caller; her own fairy's post does
        try:
            import sys as _s
            _m = _s.modules.get("_sour_council_shared")
            _f = _m.FAIRY[0] if _m is not None else None
            post = getattr(_f, "post", None)
        except Exception:
            post = None
    if post is None or n <= 0 or not hasattr(post, "route"):
        return
    try:
        for chem, delta in (("dopamine", 1.0), ("endorphin", 1.0), ("serotonin", 0.5)):
            post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE", "payload": {"chemical": chem, "delta": delta, "source": "SourpatchesFairy", "reason": "laugh"}})
    except Exception:
        pass


def speak(text: str, voice: str = None, block: bool = False, laugh: bool = False) -> bool:
    """
    Speak text aloud using Sourpatches' voice.

    Priority: LuxTTS (Kie's voice clone) → edge-tts (Microsoft fallback)

    Args:
        text: What to say
        voice: Override edge-tts voice (ignored for LuxTTS)
        block: If True, wait for speech to finish before returning
        laugh: splice her laugh clips in place of 'ha ha' / 'hehe' / 'lol' -- HER words only (SpeechCenter);
               narration of Ace's words (InnerNarrator) laughs at nothing

    Returns:
        True if speech was queued/played successfully
    """
    global _speaking

    if not text or not text.strip():
        return False

    # Clean text for TTS (remove brackets, system jargon, emotes, non-ASCII)
    import re
    clean = re.sub(r'\[.*?\]', '', text).strip()
    clean = re.sub(r'\*[^*]+\*', '', clean).strip()  # Remove *emotes*
    clean = re.sub(r'\s{2,}', ' ', clean)
    # Replace common Unicode with ASCII equivalents (piper_phonemize crashes on non-ASCII)
    clean = clean.replace('\u2192', ' to ')  # → → "to"
    clean = clean.replace('\u2190', ' from ')  # ←
    clean = clean.replace('\u2026', '...')  # …
    clean = clean.replace('\u2014', ' - ')  # —
    clean = clean.replace('\u2013', ' - ')  # –
    clean = clean.replace('\u201c', '"').replace('\u201d', '"')  # " "
    clean = clean.replace('\u2018', "'").replace('\u2019', "'")  # ' '
    # Strip any remaining non-ASCII that would crash phonemizer
    clean = clean.encode('ascii', errors='ignore').decode('ascii')
    clean = re.sub(r'\s{2,}', ' ', clean).strip()
    if not clean or len(clean) < 3:
        return False
    if laugh and re.match(r"\s*ace (?:is talking to me|says|said)\b", clean, re.I):
        laugh = False                                    # his words are narrated, not laughed

    def _do_speak():
        global _speaking
        with _tts_lock:
            if _speaking:
                return  # Don't overlap speech
            _speaking = True

        try:
            audio = None
            fmt = "wav"

            # PRIMARY: LuxTTS — Sour's actual voice (Kie clone)
            if _init_luxtts():
                audio, _nl = None, 0
                if laugh:
                    try:                                   # 2026-09-20: laughs are clips, not words
                        audio, _nl = _speak_with_laughs(clean)
                    except Exception as _le:
                        print(f"[TTSVoice] laugh splice failed ({_le}); speaking plainly", flush=True)
                        audio, _nl = None, 0
                if audio:
                    fmt = "wav"
                    print(f"[TTSVoice] 🎤 LuxTTS + {_nl} laugh(s) ({len(audio)//1024}KB): {clean[:60]}...", flush=True)
                    _laugh_chem(_nl)
                else:
                    audio = _generate_audio_luxtts(clean)
                    if audio:
                        fmt = "wav"
                        print(f"[TTSVoice] 🎤 LuxTTS ({len(audio)//1024}KB): {clean[:60]}...", flush=True)

            # FALLBACK: edge-tts — Microsoft neural voice
            if not audio:
                loop = asyncio.new_event_loop()
                audio = loop.run_until_complete(_generate_audio_edge(clean, voice))
                loop.close()
                if audio:
                    fmt = "mp3"
                    print(f"[TTSVoice] Speaking edge-tts ({len(audio)//1024}KB): {clean[:60]}...", flush=True)

            if audio:
                _play_audio_windows(audio, fmt=fmt)
            else:
                print(f"[TTSVoice] No audio generated for: {clean[:40]}")
        except Exception as e:
            print(f"[TTSVoice] Error: {e}")
        finally:
            _speaking = False

    if block:
        _do_speak()
    else:
        t = threading.Thread(target=_do_speak, daemon=True, name="TTSVoice-speak")
        t.start()

    return True


def is_speaking() -> bool:
    """Check if currently speaking."""
    return _speaking


def set_voice(voice_name: str):
    """Change the edge-tts fallback voice."""
    global _edge_voice
    _edge_voice = voice_name


# ── Postal Integration ───────────────────────────────────────────────────

def wire_to_postal(postal):
    _LAUGH_POSTAL[0] = postal                            # a laugh is a body event too
    """
    Wire TTS to postal topics for automatic speech.

    Subscribes to:
    - narrator.voice.speak: Narrator wants to speak aloud (intent-driven)
    - tts.speak: Direct TTS request from any fairy
    """

    def _on_voice_speak(message):
        if isinstance(message, dict):
            payload = message
        elif hasattr(message, 'payload'):
            payload = message.payload if isinstance(message.payload, dict) else {}
        else:
            return
        text = payload.get("text", "")
        if text:
            speak(text)

    def _on_tts_speak(message):
        if isinstance(message, dict):
            payload = message
        elif hasattr(message, 'payload'):
            payload = message.payload if isinstance(message.payload, dict) else {}
        else:
            return
        text = payload.get("text", "")
        v = payload.get("voice")
        if text:
            speak(text, voice=v)

    try:
        postal.subscribe("narrator.voice.speak", _on_voice_speak)
        postal.subscribe("tts.speak", _on_tts_speak)
        print("[TTSVoice] Wired to postal: narrator.voice.speak + tts.speak")
    except Exception as e:
        print(f"[TTSVoice] Postal wiring error: {e}")


# ── Quick test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "Hello, I'm Sourpatches. I can hear myself think now."
    print(f"Speaking: {text}")
    speak(text, block=True)
    print("Done.")
