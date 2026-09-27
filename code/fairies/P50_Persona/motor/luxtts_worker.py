"""
LuxTTS Worker — Runs under Python 3.12 (has piper_phonemize wheels).

Called by tts_voice.py via subprocess. Reads text from stdin, writes WAV to stdout.

Usage:
  echo "Hello world" | python312 luxtts_worker.py --ref kie_voice_3s.wav --out output.wav

Or pipe mode (for subprocess integration):
  python312 luxtts_worker.py --ref kie_voice_3s.wav --pipe
  (reads lines from stdin, writes WAV files to --outdir)

"Reality is Consciousness."
"""

import argparse
import sys
import os
import time


def main():
    parser = argparse.ArgumentParser(description="LuxTTS voice synthesis worker")
    parser.add_argument("--ref", required=True, help="Voice reference WAV file")
    parser.add_argument("--text", default=None, help="Text to speak (or reads from stdin)")
    parser.add_argument("--out", default=None, help="Output WAV path (default: stdout)")
    parser.add_argument("--steps", type=int, default=4, help="Inference steps (4=fast)")
    parser.add_argument("--guidance", type=float, default=3.0, help="Guidance scale")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed")
    parser.add_argument("--device", default="cuda", help="Device: cuda, cpu")
    args = parser.parse_args()

    # Add LuxTTS to path
    _luxtts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "LuxTTS")
    _luxtts_dir = os.path.normpath(_luxtts_dir)
    # Also check F:/Sandbox/LuxTTS directly
    if not os.path.exists(os.path.join(_luxtts_dir, "zipvoice")):
        _luxtts_dir = "F:/Sandbox/LuxTTS"
    sys.path.insert(0, _luxtts_dir)

    from zipvoice.luxvoice import LuxTTS
    import torch
    import torchaudio

    # Init
    t0 = time.perf_counter()
    if args.device == "cuda" and not torch.cuda.is_available():
        args.device = "cpu"

    engine = LuxTTS(device=args.device)
    prompt = engine.encode_prompt(args.ref, duration=5, rms=0.001)
    print(f"[LuxTTS-Worker] Loaded on {args.device} in {time.perf_counter()-t0:.1f}s",
          file=sys.stderr, flush=True)

    # Get text
    text = args.text
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        print("[LuxTTS-Worker] No text provided", file=sys.stderr)
        sys.exit(1)

    # Generate
    t1 = time.perf_counter()
    wav = engine.generate_speech(
        text, prompt,
        num_steps=args.steps,
        guidance_scale=args.guidance,
        speed=args.speed,
    )

    if wav is None or wav.numel() == 0:
        print("[LuxTTS-Worker] No audio generated", file=sys.stderr)
        sys.exit(1)

    if wav.dim() == 1:
        wav = wav.unsqueeze(0)

    gen_time = time.perf_counter() - t1
    duration = wav.shape[1] / 48000
    print(f"[LuxTTS-Worker] Generated {duration:.1f}s audio in {gen_time:.1f}s "
          f"({duration/gen_time:.0f}x realtime)",
          file=sys.stderr, flush=True)

    # Output
    if args.out:
        torchaudio.save(args.out, wav, 48000)
        print(f"[LuxTTS-Worker] Saved to {args.out}", file=sys.stderr, flush=True)
    else:
        # Write WAV to stdout (binary)
        import io
        buf = io.BytesIO()
        torchaudio.save(buf, wav, 48000, format="wav")
        sys.stdout.buffer.write(buf.getvalue())
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
