"""
LuxTTS Persistent Server — Runs under Python 3.12.

Stays loaded in memory so the model doesn't need to reload every utterance.
Listens on a simple socket for text, returns WAV bytes.

Protocol (TCP localhost:9877):
  Client sends: LENGTH(4 bytes big-endian) + TEXT(utf-8)
  Server sends: LENGTH(4 bytes big-endian) + WAV_BYTES
  If error:     LENGTH=0 (4 zero bytes)

Start: python312 luxtts_server.py --ref kie_voice_3s.wav
"""

import argparse
import io
import os
import socket
import struct
import sys
import time
import threading
import wave


PORT = 9877


def _tensor_to_wav_bytes(wav, rate=48000):
    """Encode a [channels, samples] float tensor to WAV bytes using the stdlib.

    WAV FIX 2026-08-30: torchaudio 2.10's save() delegates to TorchCodec, which is
    not installed here. That raised on EVERY utterance she ever attempted -- 3,403
    consecutive failures in state/luxtts_error.log, newest 08:24:52 today. The model
    generated her voice correctly and the encode step threw it away, so the handler
    returned LENGTH=0 and the client fell through to an edge-tts that is also absent.

    `wave` is stdlib and numpy already ships with torch, so this path has no
    third-party dependency and cannot regress if torchaudio changes backends again.
    Proven by test_wav_encoder.py: 15 checks including interleaving, clipping
    saturation, float64 input, and a control asserting torchaudio.save DOES raise.
    """
    import numpy as np

    a = wav.detach().cpu().numpy()
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if a.dtype != np.int16:
        a = np.clip(a, -1.0, 1.0)
        a = (a * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(a.shape[0])
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(a.T.copy(order="C").tobytes())
    return buf.getvalue()

HOST = "127.0.0.1"


def main():
    parser = argparse.ArgumentParser(description="LuxTTS persistent server")
    parser.add_argument("--ref", required=True, help="Voice reference WAV file")
    parser.add_argument("--port", type=int, default=PORT, help="Listen port")
    parser.add_argument("--device", default="cuda", help="Device: cuda, cpu")
    parser.add_argument("--idle-exit", type=float, default=1800,
                        help="Exit after N seconds with no synthesis "
                             "(0 = stay loaded forever). Frees ~3 GB RSS / "
                             "~7.8 GB commit; tts_voice relaunches on demand.")
    args = parser.parse_args()

    # Add LuxTTS to path
    _luxtts_dir = "F:/Sandbox/LuxTTS"
    sys.path.insert(0, _luxtts_dir)

    import torch
    import torchaudio
    from zipvoice.luxvoice import LuxTTS

    if args.device == "cuda" and not torch.cuda.is_available():
        args.device = "cpu"

    print(f"[LuxTTS-Server] Loading model on {args.device}...", flush=True)
    t0 = time.perf_counter()
    engine = LuxTTS(device=args.device)
    prompt = engine.encode_prompt(args.ref, duration=5, rms=0.001)
    print(f"[LuxTTS-Server] Model loaded in {time.perf_counter()-t0:.1f}s", flush=True)

    # Start TCP server
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, args.port))
    srv.listen(2)
    print(f"[LuxTTS-Server] Listening on {HOST}:{args.port}", flush=True)

    # IDLE EXIT 2026-08-30: one-element list so the closure can write it
    # without `nonlocal`. Starts now, so model-load time is not counted idle.
    _last_req = [time.time()]

    # Write PID file for discovery
    _pid_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "state", "luxtts_server.pid"
    )
    _pid_path = os.path.normpath(_pid_path)
    try:
        with open(_pid_path, "w") as f:
            f.write(f"{os.getpid()}\n{args.port}\n")
    except Exception:
        pass

    def handle_client(conn):
        try:
            # Read length header (4 bytes)
            header = b""
            while len(header) < 4:
                chunk = conn.recv(4 - len(header))
                if not chunk:
                    return
                header += chunk
            text_len = struct.unpack(">I", header)[0]

            if text_len == 0 or text_len > 10000:
                conn.sendall(struct.pack(">I", 0))
                return

            # Read text
            text_bytes = b""
            while len(text_bytes) < text_len:
                chunk = conn.recv(min(4096, text_len - len(text_bytes)))
                if not chunk:
                    break
                text_bytes += chunk
            text = text_bytes.decode("utf-8", errors="replace").strip()

            if not text:
                conn.sendall(struct.pack(">I", 0))
                return

            # IDLE EXIT 2026-08-30: stamp on real synthesis ONLY. _init_luxtts
            # probes by connecting and closing; stamping on connect would let
            # the health probe pin the model in RAM forever.
            _last_req[0] = time.time()

            # Generate speech
            t1 = time.perf_counter()
            wav = engine.generate_speech(
                text, prompt,
                num_steps=4,
                guidance_scale=3.0,
                t_shift=0.5,
                speed=1.0,
            )

            if wav is None or wav.numel() == 0:
                conn.sendall(struct.pack(">I", 0))
                return

            if wav.dim() == 1:
                wav = wav.unsqueeze(0)

            gen_time = time.perf_counter() - t1
            duration = wav.shape[1] / 48000

            # Send WAV bytes FIRST (before any logging that might crash)
            # WAV FIX 2026-08-30: was torchaudio.save() -> TorchCodec -> ImportError
            # on every single utterance. See _tensor_to_wav_bytes.
            wav_bytes = _tensor_to_wav_bytes(wav, 48000)
            conn.sendall(struct.pack(">I", len(wav_bytes)))
            conn.sendall(wav_bytes)

            # Log after send (safe — if this crashes, client already got data)
            try:
                print(f"[LuxTTS-Server] '{text[:50]}' -> {duration:.1f}s audio in "
                      f"{gen_time:.2f}s ({duration/max(gen_time,0.001):.0f}x realtime)",
                      flush=True)
            except Exception:
                pass  # Windows console encoding issue

        except Exception as e:
            # Log to file since console might have encoding issues
            import traceback
            _err_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "state", "luxtts_error.log"
            )
            try:
                with open(os.path.normpath(_err_path), "a", encoding="utf-8") as _ef:
                    _ef.write(f"\n--- {time.strftime('%H:%M:%S')} ---\n")
                    traceback.print_exc(file=_ef)
            except Exception:
                pass
            try:
                print(f"[LuxTTS-Server] Client error (see luxtts_error.log)", flush=True)
            except Exception:
                pass
            try:
                conn.sendall(struct.pack(">I", 0))
            except Exception:
                pass
        finally:
            conn.close()

    # IDLE EXIT 2026-08-30 -- unload when she is not speaking.
    # os._exit is used deliberately: accept() blocks the main thread, and this
    # server holds NO state worth an atexit handler. The one artifact that must
    # be cleaned up (the pid file) is removed explicitly first.
    if args.idle_exit and args.idle_exit > 0:
        def _idle_watchdog():
            while True:
                time.sleep(30.0)
                idle = time.time() - _last_req[0]
                if idle >= args.idle_exit:
                    print(
                        "[LuxTTS-Server] idle %.1f min (limit %.1f) - exiting to "
                        "free memory; tts_voice relaunches on next utterance"
                        % (idle / 60.0, args.idle_exit / 60.0), flush=True)
                    try:
                        os.unlink(_pid_path)
                    except Exception:
                        pass
                    os._exit(0)
        threading.Thread(target=_idle_watchdog, daemon=True).start()
        print("[LuxTTS-Server] idle-exit armed: %.1f min"
              % (args.idle_exit / 60.0), flush=True)

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        print("[LuxTTS-Server] Shutting down", flush=True)
    finally:
        srv.close()
        try:
            os.unlink(_pid_path)
        except Exception:
            pass


if __name__ == "__main__":
    main()
