# pipeline/generate_captions.py
# Create SRT aligned to scenes and burn into the visuals video.

import sys
from pathlib import Path
import subprocess
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"

def format_time_s(seconds: float) -> str:
    # SRT uses format: HH:MM:SS,mmm
    ms = int(round(seconds * 1000))
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def make_srt(script_path: Path, audio_path: Path, n_scenes: int, out_srt: Path):
    text = script_path.read_text(encoding="utf-8").strip()
    # naive sentence split into parts (you can refine later)
    parts = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
    if not parts:
        parts = [text]

    # get audio duration via ffprobe
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    total_s = float(res.stdout.strip())
    per_scene = total_s / max(1, n_scenes)

    # Build N entries by mapping parts to scenes:
    # If parts < n_scenes, we chunk the longest parts; otherwise assign first n_scenes parts.
    captions = []
    # create text blocks: try to keep them natural by grouping words
    words = text.split()
    if len(parts) >= n_scenes:
        # use first n_scenes sentences (if more, we merge remaining into last)
        blocks = parts[:n_scenes-1] + [" ".join(parts[n_scenes-1:])]
    else:
        # split words evenly into n_scenes blocks
        avg = max(1, len(words) // n_scenes)
        blocks = []
        i = 0
        for s in range(n_scenes):
            chunk = words[i:i+avg]
            if s == n_scenes-1:
                chunk = words[i:]
            blocks.append(" ".join(chunk))
            i += avg

    # construct SRT entries
    t = 0.0
    with open(out_srt, "w", encoding="utf-8") as f:
        for i, block in enumerate(blocks):
            start = t
            end = start + per_scene
            f.write(f"{i+1}\n")
            f.write(f"{format_time_s(start)} --> {format_time_s(end)}\n")
            f.write(block.strip() + "\n\n")
            t = end

    return total_s, per_scene

def burn_subtitles(input_video: Path, srt_path: Path, output_video: Path):
    """
    Convert SRT -> ASS (via ffmpeg), ensure a Styles block is present, then burn ASS into video.
    Runs ffmpeg with cwd=OUT so paths are relative (avoids Windows colon issues).
    """
    ass_path = srt_path.with_suffix(".ass")

    # 1) Convert SRT -> ASS (ffmpeg)
    cmd_conv = ["ffmpeg", "-y", "-i", srt_path.name, ass_path.name]
    print("Converting SRT -> ASS:", " ".join(cmd_conv))
    subprocess.run(cmd_conv, check=True, cwd=OUT)

    # 2) Ensure [V4+ Styles] exists with our desired style (insert if missing)
    ass_text = ass_path.read_text(encoding="utf-8", errors="ignore")
    if "[V4+ Styles]" not in ass_text:
        # build a basic Styles block (you can tweak Fontname/Fontsize/Outline/Alignment)
        styles_block = (
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
        )

        # Insert styles_block before the [Events] section if present, otherwise append at top
        if "[Events]" in ass_text:
            parts = ass_text.split("[Events]", 1)
            ass_text = parts[0] + styles_block + "[Events]" + parts[1]
        else:
            ass_text = styles_block + ass_text

        ass_path.write_text(ass_text, encoding="utf-8")

    # 3) Burn ASS into the video using ffmpeg (ass filter reads styles from file)
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video.name,
        "-vf", f"ass={ass_path.name}",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        output_video.name
    ]
    print("Burning subtitles (ffmpeg):", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=OUT)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline/generate_captions.py <safe_topic> [n_scenes]")
        sys.exit(1)

    safe_topic = sys.argv[1].replace(" ", "_")
    n_scenes = int(sys.argv[2]) if len(sys.argv) > 2 else 9

    script_file = OUT / f"{safe_topic}.txt"
    audio_file = OUT / "cloned.wav"
    visuals_in = OUT / "out_visuals.mp4"   # produced by generate_visuals.py
    out_srt = OUT / f"{safe_topic}.srt"
    out_final = OUT / "out_final.mp4"

    if not script_file.exists():
        raise SystemExit("Script missing: " + str(script_file))
    if not audio_file.exists():
        raise SystemExit("Audio missing: " + str(audio_file))
    if not visuals_in.exists():
        raise SystemExit("Visuals missing: " + str(visuals_in))

    total_s, per_scene = make_srt(script_file, audio_file, n_scenes, out_srt)
    print(f"Created SRT: {out_srt} (total {total_s:.2f}s, per scene {per_scene:.2f}s)")
    print("Burning subtitles into video (this may take a while)...")
    burn_subtitles(visuals_in, out_srt, out_final)
    print("Wrote final video with captions:", out_final)
