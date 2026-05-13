# pipeline/align_script_to_audio.py
# Align a known script to audio by using VOSK word timestamps (ASR) + fuzzy matching.
# Produces OUTPUT <topic>_aligned.srt and burns ASS into out_aligned.mp4
#
# Usage:
#   python pipeline/align_script_to_audio.py "AI tools for students" 8
# where last arg = max words per caption line (default 8).

import sys
import re
import json
import subprocess
from pathlib import Path
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"

# --- timing tuning (adjustable) ---
CAPTION_MIN_DURATION = 0.45    # keep captions visible at least this long (seconds)
CAPTION_MIN_GAP = 0.12         # minimum gap between captions (seconds)
CAPTION_START_DELAY = 0.08     # small delay so caption appears slightly AFTER audio start (seconds)
CAPTION_POST_BUFFER = 0.05     # small extension after ASR end to avoid cutoff (seconds)

# ---------------- helpers ----------------

def load_script(script_path: Path):
    txt = script_path.read_text(encoding="utf-8").strip()
    # Normalize whitespace
    txt = re.sub(r"\s+", " ", txt)
    # Split into sentences heuristically, then into short lines
    sentences = re.split(r'(?<=[.!?])\s+', txt)
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences, txt

def chunk_sentence_to_lines(sentence: str, max_words=8):
    words = sentence.split()
    lines = []
    i = 0
    while i < len(words):
        chunk = words[i:i+max_words]
        lines.append(" ".join(chunk))
        i += max_words
    return lines

def run_vosk_transcribe_words(audio_path: Path, model_dir: Path):
    """
    Use VOSK to produce words with timestamps.
    Returns list of dicts: [{'word': str, 'start': float, 'end': float}, ...]
    Requires model_dir exists.
    """
    import wave, json
    from vosk import Model, KaldiRecognizer

    if not model_dir.exists():
        raise SystemExit(f"VOSK model not found at {model_dir}. Put a model in this path.")
    wf = wave.open(str(audio_path), "rb")
    model = Model(str(model_dir))
    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    words = []
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            for w in res.get("result", []):
                words.append({"word": w.get("word", ""), "start": float(w.get("start", 0.0)), "end": float(w.get("end", 0.0))})
    final = json.loads(rec.FinalResult())
    for w in final.get("result", []):
        words.append({"word": w.get("word", ""), "start": float(w.get("start", 0.0)), "end": float(w.get("end", 0.0))})
    wf.close()
    return words

def words_to_text_and_index_map(words):
    """
    Build a continuous ASR text string and a char->word index map.
    Returns (asr_text, char_to_word_index, words_list)
    """
    pieces = []
    char_to_word = []
    for wi, w in enumerate(words):
        if not w["word"]:
            continue
        token = w["word"]
        start_idx = len(" ".join(pieces)) + (1 if pieces else 0)
        pieces.append(token)
        # update char_to_word for new token characters (+1 for space if not first)
        token_str = ("" if not pieces[:-1] else " ") + token
        for ch in token_str:
            char_to_word.append(wi)
    asr_text = " ".join([w["word"] for w in words if w["word"]])
    return asr_text, char_to_word, words

def normalize_text(t: str):
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def find_best_span_for_line(asr_words, asr_text, char_to_word_idx, line_text_norm):
    """
    Find the best matching substring in asr_text for the given normalized line text.
    Returns (best_start_word_idx, best_end_word_idx, score) or (None, None, 0).
    Approach: sliding window search over asr_text substrings of similar length and use SequenceMatcher ratio.
    """
    if not asr_text:
        return None, None, 0.0

    # quick fallback: exact substring
    pos = asr_text.find(line_text_norm)
    if pos != -1:
        # map char pos -> word index
        try:
            start_word = char_to_word_idx[pos]
            end_pos = pos + len(line_text_norm) - 1
            end_word = char_to_word_idx[min(end_pos, len(char_to_word_idx)-1)]
            return start_word, end_word, 1.0
        except Exception:
            pass

    # sliding window over words: compare by character ratio
    best = (None, None, 0.0)
    asr_len = len(asr_text)
    target_len = max(1, len(line_text_norm))
    # window step over characters; to keep speed, step by 5 chars
    step = max(1, target_len // 4)
    for start in range(0, max(1, asr_len - 1), step):
        end = min(asr_len, start + target_len + target_len//2)
        substring = asr_text[start:end]
        # similarity
        ratio = SequenceMatcher(None, line_text_norm, substring).ratio()
        if ratio > best[2]:
            try:
                start_word = char_to_word_idx[start]
                end_word = char_to_word_idx[min(end-1, len(char_to_word_idx)-1)]
                best = (start_word, end_word, ratio)
            except Exception:
                continue
    return best

def assign_timestamps_for_lines(script_lines, asr_words, min_score_threshold=0.28):
    """
    For each script line, find best ASR span; if score low, try expanding search or fallback to next available timestamp.
    Returns list of {'line':..., 'start':..., 'end':...}
    """
    asr_text_raw = " ".join([w["word"] for w in asr_words])
    asr_text_norm = normalize_text(asr_text_raw)
    char_map = []
    # build char->word index mapping for normalized ASR text (we will normalize words too)
    # simpler approach: build normalized tokens and map chars
    norm_pieces = []
    for wi, w in enumerate(asr_words):
        token = normalize_text(w["word"])
        if token == "":
            continue
        if norm_pieces:
            sep = " "
            norm_pieces.append(sep + token)
            for _ in range(len(sep + token)):
                char_map.append(wi)
        else:
            norm_pieces.append(token)
            for _ in range(len(token)):
                char_map.append(wi)
    asr_text_norm = "".join(norm_pieces)

    aligned = []
    last_end_word = 0
    for ln in script_lines:
        ln_norm = normalize_text(ln)
        if not ln_norm:
            continue
        start_w, end_w, score = find_best_span_for_line(asr_words, asr_text_norm, char_map, ln_norm)
        if start_w is None or score < min_score_threshold:
            # try a relaxed strategy: search near last_end_word (within next 20 words)
            fallback_start = last_end_word
            fallback_end = min(len(asr_words)-1, last_end_word + 40)
            # build candidate substring from fallback range
            cand = " ".join([normalize_text(w["word"]) for w in asr_words[fallback_start:fallback_end+1]])
            ratio = SequenceMatcher(None, ln_norm, cand).ratio()
            if ratio > score:
                # pick span covering whole fallback range
                start_w = fallback_start
                end_w = fallback_end
                score = ratio
            else:
                # fallback: assign start = last_end_word, end = last_end_word + 1 (best effort)
                start_w = last_end_word
                end_w = min(len(asr_words)-1, last_end_word + max(1, len(ln_norm.split())//2))
                score = 0.0

        # map to timestamps with safety buffers and small start delay so captions don't appear early
        asr_start = asr_words[start_w]["start"] if start_w < len(asr_words) else asr_words[-1]["start"]
        asr_end = asr_words[end_w]["end"] if end_w < len(asr_words) else asr_words[-1]["end"]

        # apply a small positive delay so caption shows shortly AFTER the spoken word starts
        start_ts = asr_start + CAPTION_START_DELAY
        # apply a small post buffer so line doesn't cut off immediately
        end_ts = asr_end + CAPTION_POST_BUFFER

        # enforce minimum duration
        if end_ts - start_ts < CAPTION_MIN_DURATION:
            end_ts = start_ts + CAPTION_MIN_DURATION

        # if this caption would start before the previous caption finished, shift it forward
        if aligned and start_ts <= aligned[-1]["end"] + CAPTION_MIN_GAP:
            # push start to just after previous end + min gap
            start_ts = aligned[-1]["end"] + CAPTION_MIN_GAP
            # ensure end remains at least min duration after new start
            if end_ts <= start_ts + CAPTION_MIN_DURATION:
                end_ts = start_ts + CAPTION_MIN_DURATION

        aligned.append({"line": ln, "start": start_ts, "end": end_ts, "score": score})
        last_end_word = end_w + 1

    return aligned

def write_srt(aligned_lines, out_srt: Path):
    def fmt(t):
        ms = int(round(t * 1000))
        h = ms // 3600000; ms %= 3600000
        m = ms // 60000; ms %= 60000
        s = ms // 1000; ms %= 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    with open(out_srt, "w", encoding="utf-8") as f:
        for i, a in enumerate(aligned_lines, start=1):
            f.write(f"{i}\n")
            f.write(f"{fmt(a['start'])} --> {fmt(a['end'])}\n")
            f.write(a['line'].strip() + "\n\n")

# ---------------- main ----------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python pipeline/align_script_to_audio.py \"topic name\" [max_words_per_line]")
        sys.exit(1)

    topic = sys.argv[1]
    max_words = int(sys.argv[2]) if len(sys.argv) > 2 else 8

    safe_topic = topic.replace(" ", "_")
    script_file = OUT / f"{safe_topic}.txt"
    audio_file = OUT / "cloned.wav"
    visuals_in = OUT / "out_visuals.mp4"
    if not script_file.exists() or not audio_file.exists() or not visuals_in.exists():
        raise SystemExit("Missing script/audio/visuals. Make sure output/<topic>.txt, cloned.wav and out_visuals.mp4 exist.")

    print("Loading script...")
    sentences, full_script = load_script(script_file)

    # break sentences into shorter lines
    lines = []
    for s in sentences:
        parts = chunk_sentence_to_lines(s, max_words=max_words)
        lines.extend(parts)

    print(f"Created {len(lines)} caption lines from script (max_words={max_words}).")

    # -------------- run VOSK to get ASR words --------------
    model_dir = Path.cwd() / "models" / "vosk-en"
    print("Transcribing audio (VOSK) to get word timestamps...")
    asr_words = run_vosk_transcribe_words(audio_file, model_dir)
    if not asr_words:
        raise SystemExit("VOSK produced no words. Check model & audio.")

    print(f"ASR produced {len(asr_words)} words. Running alignment...")
    aligned = assign_timestamps_for_lines(lines, asr_words, min_score_threshold=0.28)

   # ---------- final post-processing pass: ensure monotonic non-overlap & min duration ----------
    # normalize text -> single-line, trim too long (keep this)
    min_gap = CAPTION_MIN_GAP
    min_duration = CAPTION_MIN_DURATION
    max_words_caption = 12
    max_chars_caption = 80

    for a in aligned:
        a['line'] = " ".join(str(a.get('line','')).split())
        words = a['line'].split()
        if len(words) > max_words_caption:
            a['line'] = " ".join(words[:max_words_caption])
        if len(a['line']) > max_chars_caption:
            a['line'] = a['line'][:max_chars_caption].rsplit(" ", 1)[0]

    # ensure sorted
    aligned.sort(key=lambda x: x['start'])

    # enforce monotonic non-overlap strictly: start_i >= end_{i-1} + min_gap
    for i in range(len(aligned)):
        cur = aligned[i]
        # enforce min duration
        if cur['end'] - cur['start'] < min_duration:
            cur['end'] = cur['start'] + min_duration
        if i > 0:
            prev = aligned[i-1]
            # if current starts earlier than allowed, move it forward
            if cur['start'] < prev['end'] + min_gap:
                shift = (prev['end'] + min_gap) - cur['start']
                cur['start'] += shift
                cur['end'] += shift
                # ensure still within audio bounds: if beyond last end, clamp to prev end + min_gap + min_duration
                if cur['end'] < cur['start'] + min_duration:
                    cur['end'] = cur['start'] + min_duration

    # final safety: ensure no negative times and increasing sequence
    for i, c in enumerate(aligned):
        if c['start'] < 0:
            c['start'] = 0.0
        if i > 0 and c['start'] < aligned[i-1]['end'] + min_gap:
            c['start'] = aligned[i-1]['end'] + min_gap
            if c['end'] <= c['start']:
                c['end'] = c['start'] + min_duration



    # write SRT and convert->ASS and burn into video using your existing method
    out_srt = OUT / f"{safe_topic}_aligned.srt"
    out_ass = OUT / f"{safe_topic}_aligned.ass"
    out_video = OUT / "out_aligned.mp4"

    write_srt(aligned, out_srt)
    # convert to ASS
    subprocess.run(["ffmpeg", "-y", "-i", out_srt.name, out_ass.name], check=True, cwd=OUT)

    # ensure ASS style (simple insertion) - reuse small helper
    ass_text = out_ass.read_text(encoding="utf-8", errors="ignore")
    if "[V4+ Styles]" not in ass_text:
        styles_block = (
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Segoe UI,42,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,12,12,36,1\n\n"
        )
        if "[Events]" in ass_text:
            parts = ass_text.split("[Events]", 1)
            ass_text = parts[0] + styles_block + "[Events]" + parts[1]
        else:
            ass_text = styles_block + ass_text
        out_ass.write_text(ass_text, encoding="utf-8")

    # burn ASS into visuals_in
    subprocess.run(["ffmpeg", "-y", "-i", visuals_in.name, "-vf", f"ass={out_ass.name}", "-c:v", "libx264", "-preset", "fast", "-c:a", "copy", out_video.name], check=True, cwd=OUT)
    print("Wrote aligned video:", out_video)

if __name__ == "__main__":
    main()
