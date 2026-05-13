# pipeline/generate_dynamic_captions.py
# Transcribe audio with timestamps (faster-whisper), produce 1-line AI captions per short segment
# and burn them into the final video (uses ASS path handling similar to your captions script).
#
# Usage:
#   python pipeline/generate_dynamic_captions.py "AI tools for students" 2.5
# where the last argument is optional segment_duration (seconds) — default 2.5s.

import os
import math
import time
from pathlib import Path
import subprocess
from dotenv import load_dotenv

# --- CAPTION TUNING (adjustable) ---
CAP_START_DELAY = 0.08     # seconds: small delay so caption appears slightly AFTER audio start
CAP_POST_BUFFER = 0.05     # seconds: small tail so captions don't cut off immediately
CAP_MIN_DURATION = 1.4     # seconds: minimum time a caption should be visible (readability)
CAP_MIN_GAP = 0.06         # seconds: minimum gap between captions (prevents overlap)
CAP_MAX_WORDS = 10         # max words per caption (single-line)
CAP_MAX_CHARS = 60         # safety max chars per caption

# google genai client
try:
    from google import genai
    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

load_dotenv()   # load .env in project root

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GENAI_API_KEY")
if GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
    if GENAI_AVAILABLE:
        genai.configure(api_key=GOOGLE_API_KEY)

# fallback local heuristic summarizer
def local_summarize_one_line(text, max_words=8):
    # simple safe fallback: pick most informative 6-10 words
    words = [w.strip() for w in text.split() if w.strip()]
    if not words:
        return ""
    # try to remove filler words at start
    fillers = {"um","uh","like","so","and","but","then","well","you","know"}
    filtered = [w for w in words if w.lower() not in fillers]
    out = filtered[:max_words] if len(filtered) >= 1 else words[:max_words]
    caption = " ".join(out)
    # at most 60 chars
    if len(caption) > 60:
        caption = " ".join(caption.split()[:max_words])
    return caption.strip()

# function to call Gemini for a one-line caption
def call_gemini_one_line(prompt_text, max_chars=60):
    """
    Uses the Google Generative AI Python client (google-genai).
    Prompts Gemini to produce a single-line, readable caption (<= max_chars) in plain text.
    """
    if not GENAI_AVAILABLE or not GOOGLE_API_KEY:
        return None

    # conservative prompt for consistent 1-line captions
    system = "You are a caption generator. Given a short excerpt of spoken audio, return ONE short caption line that a mobile viewer would read while listening. Keep it concise (<= 60 characters), present tense, active voice, no special characters or emojis. Do not include timestamps or labels."
    user = f"Transcript excerpt:\n\n{prompt_text}\n\nReturn exactly one short caption line (no explanation)."

    try:
        # this uses the "models/text-bison-001" style or "chat" call depending on genai package;
        # we'll use the chat-style if available, otherwise text completion
        resp = genai.generate_text(
            model="chat-bison-001",
            temperature=0.2,
            max_output_tokens=64,
            prompt=f"{system}\n\n{user}"
        )
        # genai.generate_text returns an object with .text or .output
        txt = ""
        if hasattr(resp, "output"):
            # new response format
            txt = resp.output[0].content[0].text if resp.output and len(resp.output) and resp.output[0].content else resp.text
        else:
            txt = getattr(resp, "text", str(resp))
        line = txt.strip().splitlines()[0].strip()
        if len(line) > max_chars:
            line = line[:max_chars].rsplit(" ", 1)[0]
        return line
    except Exception as e:
        print("  [WARN] Gemini call failed:", e)
        return None

# --- VOSK transcription fallback (Windows-friendly) ---
# Ensure you downloaded a VOSK model into ./models/vosk-en

FW_AVAILABLE = False  # force using VOSK on Windows

def transcribe_with_vosk(audio_path: Path, segment_duration=2.5):
    """
    Transcribe audio using VOSK, produce fixed-length windows (segment_duration seconds).
    Returns list of windows: [{'start': float, 'end': float, 'text': str}, ...]
    """
    try:
        from vosk import Model, KaldiRecognizer
        import wave
        import json
    except Exception as e:
        raise SystemExit("VOSK not installed or import failed: " + str(e))

    model_dir = Path.cwd() / "models" / "vosk-en"
    if not model_dir.exists():
        raise SystemExit(f"VOSK model not found at {model_dir}. Download and extract a model into this folder.")

    print("Loading VOSK model from:", model_dir)
    model = Model(str(model_dir))

    wf = wave.open(str(audio_path), "rb")
    if wf.getnchannels() != 1:
        # convert stereo -> mono temporary via ffmpeg (write temp file)
        tmp_mono = audio_path.with_name(audio_path.stem + "_mono.wav")
        cmd = ["ffmpeg", "-y", "-i", str(audio_path), "-ac", "1", "-ar", "16000", str(tmp_mono)]
        subprocess.run(cmd, check=True)
        wf.close()
        wf = wave.open(str(tmp_mono), "rb")

    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    segments = []
    # We'll accumulate words with their timestamps, then merge into windows.
    words_accum = []
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            # res may have "result": [ {word, start, end}, ... ]
            if "result" in res:
                for w in res["result"]:
                    words_accum.append({"word": w.get("word", ""), "start": float(w.get("start", 0.0)), "end": float(w.get("end", 0.0))})
        else:
            # partial result ignored
            pass

    # final result
    final = json.loads(rec.FinalResult())
    if "result" in final:
        for w in final["result"]:
            words_accum.append({"word": w.get("word", ""), "start": float(w.get("start", 0.0)), "end": float(w.get("end", 0.0))})

    wf.close()

    if not words_accum:
        return []

    # Determine total audio time from last word end (or fallback to ffprobe)
    total_time = words_accum[-1]["end"]
    # Build fixed windows of length segment_duration
    windows = []
    t = 0.0
    idx = 0
    while t < total_time - 0.01:
        wstart = t
        wend = min(total_time, t + segment_duration)
        # gather words in this window
        words = [w["word"] for w in words_accum if (w["end"] > wstart + 0.01 and w["start"] < wend - 0.01)]
        text = " ".join(words).strip()
        windows.append({"start": wstart, "end": wend, "text": text})
        t += segment_duration
        idx += 1

    # cleanup tmp mono if created
    if 'tmp_mono' in locals() and Path(tmp_mono).exists():
        try:
            Path(tmp_mono).unlink()
        except Exception:
            pass

    return windows


def write_srt_from_caption_list(captions, out_srt: Path):
    def fmt(t):
        ms = int(round(t * 1000))
        h = ms // 3600000; ms %= 3600000
        m = ms // 60000; ms %= 60000
        s = ms // 1000; ms %= 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    with open(out_srt, "w", encoding="utf-8") as f:
        for i, c in enumerate(captions, start=1):
            f.write(f"{i}\n")
            f.write(f"{fmt(c['start'])} --> {fmt(c['end'])}\n")
            f.write(c['line'] + "\n\n")

def burn_ass_using_existing(ass_name, in_video, out_video):
    # reuse earlier approach: run ffmpeg in OUT folder and burn ASS
    cmd = ["ffmpeg", "-y", "-i", in_video.name, "-vf", f"ass={ass_name}", "-c:v", "libx264", "-preset", "fast", "-c:a", "copy", out_video.name]
    subprocess.run(cmd, check=True, cwd=OUT)

def ensure_ass_style(ass_path: Path):
    txt = ass_path.read_text(encoding="utf-8", errors="ignore")
    if "[V4+ Styles]" not in txt:
        styles_block = (
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Segoe UI,44,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,12,12,120,1\n\n"
        )
        if "[Events]" in txt:
            parts = txt.split("[Events]", 1)
            txt = parts[0] + styles_block + "[Events]" + parts[1]
        else:
            txt = styles_block + txt
        ass_path.write_text(txt, encoding="utf-8")

def main():
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI tools for students"
    seg_dur = float(sys.argv[2]) if len(sys.argv) > 2 else 2.5

    safe_topic = topic.replace(" ", "_")
    audio_file = OUT / "cloned.wav"
    visuals_in = OUT / "out_visuals.mp4"   # or out_dynamic.mp4 previous
    if not audio_file.exists():
        raise SystemExit("Missing audio: " + str(audio_file))
    if not visuals_in.exists():
        raise SystemExit("Missing visuals file: " + str(visuals_in))

    print("Transcribing audio with timestamps (VOSK)...")
    windows = transcribe_with_vosk(audio_file, segment_duration=seg_dur)

    print(f"Produced {len(windows)} windows (each ~{seg_dur}s).")

        # --- build raw captions (Gemini or local) ---
    raw_captions = []
    for w in windows:
        text = w["text"]
        line = None
        if GENAI_AVAILABLE and GOOGLE_API_KEY:
            line = call_gemini_one_line(text, max_chars=CAP_MAX_CHARS)
            if line:
                print("AI caption:", line)
        if not line:
            line = local_summarize_one_line(text, max_words=CAP_MAX_WORDS)
            print("Local caption:", line)
        raw_captions.append({"start": float(w["start"]), "end": float(w["end"]), "line": line or ""})
        time.sleep(0.2)

    # --- post-process captions: single-line, truncation, enforce min duration & no-overlap ---
    processed_captions = []
    prev_end = 0.0
    for c in raw_captions:
        # normalize / single-line
        line = " ".join(str(c.get("line", "")).split())
        words = line.split()
        if len(words) > CAP_MAX_WORDS:
            line = " ".join(words[:CAP_MAX_WORDS])
        if len(line) > CAP_MAX_CHARS:
            line = line[:CAP_MAX_CHARS].rsplit(" ", 1)[0]

        # compute start/end with safety buffers and monotonic schedule
        start = max(c["start"] + CAP_START_DELAY, prev_end + CAP_MIN_GAP)
        end = max(c["end"] + CAP_POST_BUFFER, start + CAP_MIN_DURATION)

        # final clamp (avoid negative or tiny durations)
        if start < 0:
            start = 0.0
        if end <= start:
            end = start + CAP_MIN_DURATION

        processed_captions.append({"start": start, "end": end, "line": line})
        prev_end = end

    # use processed_captions going forward
    captions = processed_captions


    # write SRT & convert -> ASS (we will reuse your earlier ASS insertion approach)
    out_srt = OUT / f"{safe_topic}_dynamic.srt"
    out_ass = OUT / f"{safe_topic}_dynamic.ass"
    write_srt_from_caption_list(captions, out_srt)

    # convert to ASS using ffmpeg, then ensure style
    subprocess.run(["ffmpeg", "-y", "-i", out_srt.name, out_ass.name], check=True, cwd=OUT)
    ensure_ass_style(out_ass)

    # burn ASS into video (create out_dynamic.mp4)
    out_video = OUT / "out_dynamic.mp4"
    burn_ass_using_existing(out_ass.name, visuals_in, out_video)
    print("Wrote dynamic captioned video:", out_video)

if __name__ == "__main__":
    main()
