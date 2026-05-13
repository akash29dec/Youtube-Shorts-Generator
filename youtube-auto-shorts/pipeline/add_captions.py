import sys
import whisper
import subprocess
import ssl
import os
import textwrap
from pathlib import Path
import datetime

# --- 1. USE STANDALONE FFMPEG ---
try:
    from imageio_ffmpeg import get_ffmpeg_exe
    FFMPEG_EXE = get_ffmpeg_exe()
except ImportError:
    print("❌ Error: 'imageio-ffmpeg' not found. Please run: pip install imageio-ffmpeg")
    sys.exit(1)

# --- 2. SSL FIX ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- PATHS ---
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

def format_timestamp_ass(seconds: float):
    """Converts seconds to ASS format (H:MM:SS.cs)"""
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 10000) 
    return f"{hours:1}:{minutes:02}:{secs:02}.{millis:02}"

def generate_ass(video_path, ass_path, original_script_path=None):
    print(f"👂 Transcribing: {video_path.name}...")
    
    script_context = ""
    if original_script_path and original_script_path.exists():
        script_context = original_script_path.read_text(encoding="utf-8")
        print("🎯 Using original script as vocabulary prompt.")

    # Use 'base' model for speed, 'small' for better accuracy if needed
    model = whisper.load_model("base", device="cpu")
    
    # word_timestamps=True is REQUIRED for the grouping logic below
    result = model.transcribe(
        str(video_path), 
        word_timestamps=True, 
        fp16=False,
        initial_prompt=script_context
    )
    
    header = textwrap.dedent("""\
        [Script Info]
        ScriptType: v4.00+
        PlayResX: 1080
        PlayResY: 1920

        [V4+ Styles]
        Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        Style: Default,Arial Black,80,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,2,10,10,350,1

        [Events]
        Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
    """)
    
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        
        for segment in result["segments"]:
            words = segment.get("words", [])
            
            # Chunk words into groups of 3 for fast-paced reading
            chunk_size = 2
            for i in range(0, len(words), chunk_size):
                chunk = words[i:i + chunk_size]
                if not chunk: continue
                
                start_ts = format_timestamp_ass(chunk[0]["start"])
                end_ts = format_timestamp_ass(chunk[-1]["end"])
                
                # Combine words and clean up
                text = " ".join([w["word"].strip().upper() for w in chunk])
                text = text.replace(",", "").replace(".", "").replace("?", "")
                
                f.write(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}\n")
    
    print(f"✅ Subtitles generated: {ass_path}")
    return True

def burn_captions(video_path, ass_path, output_path):
    print("🔥 Burning captions into video...")
    
    # Path escaping for Windows FFmpeg
    clean_ass_path = str(ass_path.absolute()).replace("\\", "/").replace(":", "\\:")
    
    cmd = [
        FFMPEG_EXE, "-y", 
        "-i", str(video_path.absolute()),
        "-vf", f"subtitles='{clean_ass_path}'", 
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        str(output_path.absolute())
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"🎬 FINAL VIDEO READY: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg Error: {e.stderr.decode()}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline/add_captions.py <video_path> [script_path]")
        sys.exit(1)

    video_in = Path(sys.argv[1]).resolve()
    script_in = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
    
    base_name = video_in.stem
    ass_out = OUT / f"{base_name}.ass"
    
    # Ensure final_videos directory exists
    final_dir = ROOT / "final_videos"
    final_dir.mkdir(exist_ok=True)
    video_out = final_dir / f"{base_name}_Short.mp4"

    if generate_ass(video_in, ass_out, original_script_path=script_in):
        burn_captions(video_in, ass_out, video_out)