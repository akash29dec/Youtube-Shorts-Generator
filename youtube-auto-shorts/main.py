import sys
import shutil
import json
import asyncio
import subprocess
import time
from pathlib import Path

# --- IMPORTS ---
from pipeline.research_script_gemini import make_script
from pipeline.base_tts import generate_tts_smart 
from pipeline.applio_infer import convert_voice
from pipeline.generate_visuals import generate_visuals
from pipeline.add_captions import generate_ass, burn_captions

# 👇 Import the visual optimizer function
from pipeline.optimize_visuals_gemini import optimize_json 

# --- PATHS ---
ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
FINAL_DIR = ROOT / "final_videos"
FINAL_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def extract_thumbnail(video_path):
    """Extracts a frame from 00:01 to serve as the thumbnail."""
    thumb_path = video_path.with_suffix(".jpg")
    print(f"🖼️ Extracting thumbnail to {thumb_path}...")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path),
            "-ss", "00:00:01.500", "-vframes", "1",
            "-q:v", "2", str(thumb_path)
        ], check=True, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"⚠️ Thumbnail generation failed: {e}")

def run_pipeline(topic, manual_mood="neutral"):
    start_time = time.time()
    print("="*60)
    print(f"🎬 STARTING AUTOMATION FOR: {topic}")
    print("="*60)
    
    safe_name = "".join([c for c in topic if c.isalnum() or c == ' ']).strip().replace(" ", "_")
    
    # ---------------------------------------------------------
    # STEP 1: RESEARCH & SCRIPT
    # ---------------------------------------------------------
    print(f"\n🔹 [1/5] Generating Script (Mood: {manual_mood})...")
    
    # 1. ROBUST FIX: Use *_ to ignore extra return values
    script_data, clean_text, *_ = make_script(topic)
    
    # 2. ROBUST FIX: Ensure data is a Dictionary
    if isinstance(script_data, str):
        clean_input = script_data.strip().strip('"').strip("'")
        if Path(clean_input).exists():
            print(f"📂 Reading script from file: {clean_input}")
            with open(clean_input, "r", encoding="utf-8") as f:
                script_data = json.load(f)
        else:
            try:
                script_data = json.loads(script_data)
            except json.JSONDecodeError:
                print("❌ CRITICAL ERROR: script_data is invalid JSON.")
                return

    # Define paths
    json_path = OUTPUT_DIR / f"{safe_name}.json"
    txt_path = OUTPUT_DIR / f"{safe_name}_voice.txt"
    
    # Override mood if manually specified
    if manual_mood != "neutral":
        script_data["mood"] = manual_mood
        
    # Save the ORIGINAL JSON (Draft 1)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2)
        
    # Save Draft Text
    txt_path.write_text(clean_text, encoding="utf-8")

    # ---------------------------------------------------------
    # STEP 1.5: OPTIMIZE VISUALS & TEXT (CRITICAL UPDATE)
    # ---------------------------------------------------------
    print(f"\n✨ [1.5/5] Polishing Script, Visuals & Typos with Gemini...")
    
    # Run the optimizer
    optimized_json_path = optimize_json(json_path)
    
    if optimized_json_path and optimized_json_path.exists():
        # 1. Update the JSON path to use the optimized version
        json_path = optimized_json_path
        
        # 2. 🔴 CRITICAL: Reload the FIXED text so the Audio is correct!
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                opt_data = json.load(f)
            
            # Re-construct the text from the fixed segments
            new_full_text = " ".join([seg['text'] for seg in opt_data['script_segments']])
            
            # Overwrite the text file so the TTS reads the correct words
            txt_path.write_text(new_full_text, encoding="utf-8")
            print("✅ Audio Script Updated: Typos & Hallucinations removed.")
            
        except Exception as e:
            print(f"⚠️ Could not reload optimized text: {e}")
            
    else:
        print("⚠️ Optimization failed or returned None. Using original script.")

    # ---------------------------------------------------------
    # STEP 2: AUDIO (Smart Emotional TTS)
    # ---------------------------------------------------------
    print(f"\n🔹 [2/5] Generating Base Audio (Voice: {manual_mood})...")
    base_audio_path = OUTPUT_DIR / f"{safe_name}_base.mp3"
    
    # Now this uses the UPDATED txt_path from Step 1.5
    asyncio.run(generate_tts_smart(txt_path, base_audio_path, mood=manual_mood))
    
    if not base_audio_path.exists():
        print("❌ Error: Base TTS generation failed.")
        return

    # ---------------------------------------------------------
    # STEP 3: RVC CONVERSION (Applio)
    # ---------------------------------------------------------
    print("\n🔹 [3/5] Converting to YOUR Voice (Applio RVC)...")
    final_audio_path = OUTPUT_DIR / f"{safe_name}.wav"
    
    try:
        convert_voice(base_audio_path, final_audio_path)
    except Exception as e:
        print(f"❌ Error in RVC: {e}")
        return

    # ---------------------------------------------------------
    # STEP 4: VISUALS
    # ---------------------------------------------------------
    print("\n🔹 [4/5] Fetching Visuals & Mood Music...")
    video_no_subs = OUTPUT_DIR / f"{safe_name}_raw.mp4"
    
    generate_visuals(json_path, final_audio_path, video_no_subs)
    
    if not video_no_subs.exists():
        print("❌ Error: Visual generation failed.")
        return

    # ---------------------------------------------------------
    # STEP 5: CAPTIONS & FINALIZING
    # ---------------------------------------------------------
    print("\n🔹 [5/5] Finalizing...")
    ass_path = OUTPUT_DIR / f"{safe_name}.ass"
    final_video_path = FINAL_DIR / f"{safe_name}_Short.mp4"
    
    generate_ass(video_no_subs, ass_path, original_script_path=txt_path)
    burn_captions(video_no_subs, ass_path, final_video_path)
    
    if final_video_path.exists():
        extract_thumbnail(final_video_path)
    
    elapsed = time.time() - start_time
    print(f"\n✅ DONE! Saved to: {final_video_path}")
    print(f"⏱️ Total Time: {elapsed:.2f} seconds")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py \"Your Video Topic\"")
        sys.exit(1)
    
    run_pipeline(sys.argv[1])