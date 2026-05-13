# pipeline/compose_video.py
# Compose a vertical short with explicit audio mapping

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = ROOT / "assets"
OUTPUT_DIR.mkdir(exist_ok=True)

def compose(background: Path, audio: Path, out_path: Path):
    if not background.exists():
        raise FileNotFoundError(f"Background not found: {background}")
    if not audio.exists():
        raise FileNotFoundError(f"Audio not found: {audio}")

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(background),   # input 0: image
        "-i", str(audio),        # input 1: audio
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-map", "0:v:0",         # take video from input 0
        "-map", "1:a:0",         # take audio from input 1
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",        # re-encode audio to AAC
        "-b:a", "192k",
        "-ac", "2",          # force stereo
        "-shortest",
        str(out_path)
    ]

    print("Running ffmpeg:")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print("Saved video to:", out_path)

if __name__ == "__main__":
    bg = ASSETS_DIR / "bg.jpg"
    audio = OUTPUT_DIR / "cloned.wav"  # use cloned.wav (which currently = base_tts.wav)
    out = OUTPUT_DIR / "out.mp4"
    compose(bg, audio, out)
