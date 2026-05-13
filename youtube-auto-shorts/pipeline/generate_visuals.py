# pipeline/generate_visuals.py
import os
import time
import random
import requests
import subprocess
import shutil
import re
import json
from pathlib import Path
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------- PATHS ----------------
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
ASSETS = ROOT / "assets"
MUSIC_DIR = ASSETS / "music"
FALLBACK_DIR = ASSETS / "fallbacks"  # Place generic loops here
TMP = OUT / "visual_tmp"

# Create directories
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)
MUSIC_DIR.mkdir(parents=True, exist_ok=True)
FALLBACK_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- CONFIG ----------------
USED_IDS_FILE = OUT / "used_ids.txt"
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
FPS = 30
TRANSITION_DURATION = 0.5
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

# ---------------- UTILS ----------------
def get_file_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(r.stdout.strip())
    except Exception:
        return 0.0

def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9\s]', '', text)

def download_file(url: str, out_path: Path):
    try:
        r = requests.get(url, stream=True, timeout=30, verify=False)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(1024 * 32):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")
        return False

# ---------------- INTELLIGENT SCENE PARSER ----------------
def analyze_script(script_path: Path):
    if script_path.suffix == '.json':
        with open(script_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        scenes = []
        total_words = 0
        for segment in data['script_segments']:
            text = segment.get('text', '').strip()
            # parse visual keywords into a list of short phrases (split on commas)
            vk_raw = segment.get('visual_keywords', '') or ''
            vk_phrases = [p.strip() for p in vk_raw.split(',') if p.strip()]

            words = re.findall(r"\w+", text)
            word_count = max(1, len(words))
            total_words += word_count

            scenes.append({
                "text": text,
                "visual_keywords": vk_phrases,
                "word_count": word_count
            })
        return scenes, total_words
    else:
        text = script_path.read_text(encoding="utf-8")
        words = re.findall(r"\w+", text)
        return [{"text": text, "visual_keywords": ["abstract background"], "word_count": max(1, len(words))}], len(words)


# ---------------- CONTENT FETCHING (ROBUST SEARCH ADDED) ----------------
def fetch_content_for_scene(scene, idx, duration, used_ids):
    """Search Pexels using prioritized logic + fallbacks to landscape video."""
    vk_phrases = scene.get("visual_keywords", []) or ["abstract background"]

    # 1. Build Query List
    queries = []
    for p in vk_phrases:
        queries.append(p)                   # "snake wearing mask"
        queries.append(f"{p} close-up")     # "snake wearing mask close-up"
        
        # 🧠 SMART SPLIT: If phrase is long (e.g. "snake mask"), split it
        words = p.split()
        if len(words) > 1:
            queries.append(words[-1])       # "mask" (Noun usually last)
            queries.append(words[0])        # "snake"
            
    # Remove duplicates
    seen_q = set()
    queries = [q for q in queries if not (q in seen_q or seen_q.add(q))]

    if PEXELS_KEY:
        headers = {"Authorization": PEXELS_KEY}
        
        for q in queries[:15]: # Try up to 15 variations
            q_clean = q.strip()
            if not q_clean: continue
            
            # 🔁 TRY 1: Portrait (Best fit)
            found = search_pexels_api(q_clean, "portrait", duration, used_ids, headers, idx)
            if found: return found
            
            # 🔁 TRY 2: Landscape (Crop later - vastly expands results)
            # Many "Cinematic" clips are only available in landscape
            print(f"   ↳ Retrying '{q_clean}' in Landscape mode...")
            found = search_pexels_api(q_clean, "landscape", duration, used_ids, headers, idx)
            if found: return found

    # fallback: local files
    print(f"⚠️ No Pexels match for Scene {idx+1}. Checking fallbacks...")
    fallbacks = list(FALLBACK_DIR.glob("*.mp4"))
    if fallbacks:
        chosen = random.choice(fallbacks)
        print(f"✅ Using fallback: {chosen.name}")
        return chosen

    return None

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def search_pexels_api(query, orientation, duration, used_ids, headers, idx):
    """Helper function to run the actual API call with RETRIES"""
    print(f"🔎 Scene {idx+1}: Searching Pexels ({orientation}) for '{query}'...")
    
    # Configure retry logic (3 retries, waiting longer between each)
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        url = "https://api.pexels.com/videos/search"
        params = {"query": query, "per_page": 15, "orientation": orientation}
        
        # Increased timeout to 30s
        r = session.get(url, headers=headers, params=params, timeout=30, verify=False)
        
        if r.status_code != 200: 
            print(f"   ❌ API Status: {r.status_code}")
            return None
        
        videos = r.json().get("videos", [])
        print(f"   ↳ API returned {len(videos)} raw videos")

        # Filter used IDs
        candidates = [v for v in videos if str(v['id']) not in used_ids]
        
        # Sort by duration closeness
        candidates = sorted(candidates, key=lambda v: abs(v.get('duration', 0) - duration))
        
        for v in candidates:
            v_dur = v.get('duration', 0)
            # Filter clips that are too short
            if v_dur < 1.0 or v_dur < max(1.0, duration * 0.3): continue 
            
            # Find best file (prefer HD)
            files = v.get("video_files", [])
            best_file = None
            for f in files:
                if f.get('width', 0) >= 1080 or f.get('height', 0) >= 1080:
                    best_file = f
                    break
            if not best_file and files: best_file = files[0] 
            
            if best_file:
                out_path = TMP / f"scene_{idx}_raw.mp4"
                if download_file(best_file['link'], out_path):
                    used_ids.add(str(v['id']))
                    print(f"✅ FOUND: Clip ID={v['id']} ({orientation}) for '{query}'")
                    return out_path
    except Exception as e:
        print(f"   ⚠️ API Error: {e}")
    return None

# ---------------- PROCESSING (SHADOW LAWS LOOK) ----------------
def process_clip(raw_path, duration, idx):
    output_path = TMP / f"scene_{idx}_final.mp4"
    
    if not raw_path or not raw_path.exists():
        # Generate black filler if download failed entirely
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", 
            "-i", f"color=c=black:s={TARGET_WIDTH}x{TARGET_HEIGHT}:d={duration}",
            "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", str(output_path)
        ], check=True, stderr=subprocess.DEVNULL)
        return output_path

    raw_duration = get_file_duration(raw_path)
    inputs = ["-i", str(raw_path)]
    if raw_duration < duration:
        inputs = ["-stream_loop", "-1", "-i", str(raw_path)]

    # ---------------------------------------------------------
    # 🎨 THE SHADOW LAWS LOOK (FFmpeg Filter Chain)
    # ---------------------------------------------------------
    # 1. Exposure/Brightness: -10 to -15 -> brightness=-0.08 (Slightly less dark to preserve detail)
    # 2. Contrast: +10 to +15 -> contrast=1.12
    # 3. Saturation: -20 to -30 -> saturation=0.7
    # 4. Temperature: Blue Tint -> colorbalance (boost blue, cut red)
    # 5. Vignette: Darken corners
    # ---------------------------------------------------------
    
    # EQ Filter: Contrast, Brightness, Saturation
    eq_filter = "eq=contrast=1.12:brightness=-0.08:saturation=0.7"
    
    # Color Balance: Boost Blue Shadows/Mids, Cut Red (Cold Matrix Look)
    color_balance = "colorbalance=rs=-0.1:rm=-0.1:rh=-0.1:bs=0.1:bm=0.1:bh=0.1"
    
    # Vignette: Standard cinematic corner darkening
    vignette = "vignette=PI/5"

    # Combine into one color grading string
    shadow_laws_grade = f"{eq_filter},{color_balance},{vignette}"

    # Full Filter Chain: Scale/Crop -> Setsar -> Color Grade
    # Note: force_original_aspect_ratio=increase is better for cropping landscape to portrait
    vf_chain = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},"
        f"setsar=1,"
        f"{shadow_laws_grade}"
    )

    cmd = [
        "ffmpeg", "-y", *inputs, "-t", f"{duration:.3f}",
        "-vf", vf_chain, "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-r", str(FPS), "-an", str(output_path)
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print("❌ FFmpeg failed in process_clip")
        print(e.stderr.decode(errors="ignore"))
        raise

    return output_path

# ---------------- STITCHING (FIXED LOGIC) ----------------

def stitch_video(clips, audio_path, output_path, json_path):
    # read mood
    mood = "neutral"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                mood = json.load(f).get("mood", "neutral").lower()
        except:
            pass

    print(f"🎵 MOOD DETECTED: '{mood}'")

    # pick music
    music_root = ROOT / "assets/music"
    target_folder = music_root / mood
    tracks = list(target_folder.glob("*.mp3")) if target_folder.exists() else list(music_root.glob("*.mp3"))
    bg_music = random.choice(tracks) if tracks else None

    # get clip durations (must exist)
    durations = [get_file_duration(Path(c)) for c in clips]
    if not all(d > 0 for d in durations):
        print("⚠️ One or more clip durations are zero. Aborting stitch to avoid bad offsets.")
        raise RuntimeError("Invalid clip durations")

    # ensure transition length is valid
    xf = min(TRANSITION_DURATION, min(durations) / 2.0)
    if xf <= 0:
        xf = 0.2  # fallback tiny transition
    print(f"🔁 Using transition duration: {xf:.2f}s")

    # Build ffmpeg inputs
    cmd = ["ffmpeg", "-y"]
    for clip in clips:
        cmd += ["-i", str(clip)]
    cmd += ["-i", str(audio_path)]
    if bg_music:
        cmd += ["-stream_loop", "-1", "-i", str(bg_music)]

    # Build filter_complex parts
    filter_parts = []
    # 1) scale/pad each clip to same size and label them as f{i}
    for i in range(len(clips)):
        fp = (
            f"[{i}:v]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[f{i}]"
        )
        filter_parts.append(fp)

    # 2) Chain xfade operations
    # Start with first stream label
    cur_label = "f0"
    cur_duration = durations[0]
    # We will produce labels x1, x2, ... for each xfade result
    for i in range(1, len(clips)):
        next_label = f"f{i}"
        out_label = f"x{i}"
        offset = cur_duration - xf
        # protect offset not negative
        if offset < 0:
            offset = 0
        xfade_part = f"[{cur_label}][{next_label}]xfade=transition=fade:duration={xf}:offset={offset}[{out_label}]"
        filter_parts.append(xfade_part)
        # update cur_duration for next iteration
        cur_duration = cur_duration + durations[i] - xf
        cur_label = out_label

    # After chaining, the final label is cur_label
    final_label = cur_label

    # 3) Map final video label to output
    filter_parts.append(f"[{final_label}]format=yuv420p[fout]")

    # 4) audio mixing
    audio_idx = len(clips)
    music_idx = len(clips) + 1 if bg_music else None

    if bg_music:
        filter_parts.append(f"[{audio_idx}:a]volume=1.0[a1];[{music_idx}:a]volume=0.09[a2];[a1][a2]amix=inputs=2:duration=shortest[aout]")
    else:
        filter_parts.append(f"[{audio_idx}:a]anull[aout]")

    filter_complex = ";".join(filter_parts)

    # build final command
    cmd += ["-filter_complex", filter_complex, "-map", "[fout]", "-map", "[aout]", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(output_path)]

    print("🎬 Rendering Final Video (with xfade transitions)...")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print("❌ ffmpeg failed in stitch_video:")
        print(e.stderr.decode(errors="ignore"))
        raise

 
# ---------------- MAIN ----------------
def generate_visuals(script_file: Path, audio_file: Path, out_file: Path):
    print("🚀 Starting Visual Generation Pipeline...")
    total_audio_duration = get_file_duration(audio_file)
    if total_audio_duration <= 0:
        raise RuntimeError(f"Audio duration invalid ({total_audio_duration}). Check audio file: {audio_file}")
    print(f"⏱️ Audio Duration: {total_audio_duration:.2f}s")
    
    # 1. Analyze Script
    scenes, total_words = analyze_script(script_file)   # <-- use total_words name
    if not scenes:
        raise RuntimeError("No scenes parsed from script JSON.")

    # 2. Timing Logic (account for xfade overlap)
    n_scenes = len(scenes)
    reserved_overlap = max(0.0, (n_scenes - 1) * TRANSITION_DURATION)
    target_total = total_audio_duration + reserved_overlap

    # dynamic minimum per scene
    min_scene = max(0.9, total_audio_duration * 0.04)
    scene_durations = []
    allocated = 0.0
    for s in scenes:
        prop = s['word_count'] / total_words if total_words > 0 else 1.0 / n_scenes
        dur = max(min_scene, target_total * prop)
        scene_durations.append(dur)
        allocated += dur

    # scale to exactly meet target_total (avoid rounding drift)
    if allocated > 0:
        scale = target_total / allocated
        scene_durations = [max(min_scene, d * scale) for d in scene_durations]

    print("🔢 scene_durations (s):", ", ".join(f"{d:.2f}" for d in scene_durations))

    # 3. Fetch & Process Clips
    used_ids = set()
    if USED_IDS_FILE.exists():
        try:
            used_ids = set([l.strip() for l in USED_IDS_FILE.read_text(encoding='utf-8').splitlines() if l.strip()])
        except Exception:
            used_ids = set()

    final_clips = []
    for i, scene in enumerate(scenes):
        scene_duration = scene_durations[i]
        print(f"🔹 Scene {i+1}: '{scene['text'][:60]}...' ({scene_duration:.2f}s)")
        raw_clip = fetch_content_for_scene(scene, i, scene_duration, used_ids)
        final_clip = process_clip(raw_clip, scene_duration, i)
        final_clips.append(final_clip)

        # persist used ids incrementally (sorted for readability)
        try:
            with open(USED_IDS_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(used_ids)))
        except Exception as e:
            print("⚠️ Could not write used ids file:", e)

    if not final_clips:
        raise RuntimeError("No clips were downloaded/processed. Aborting.")

    # 4. Stitch (pass script_file for mood reading)
    stitch_video(final_clips, audio_file, out_file, json_path=script_file)

    print(f"✅ Video Generated: {out_file}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        generate_visuals(Path(sys.argv[1]), Path(sys.argv[2]), OUT / "final_output.mp4")