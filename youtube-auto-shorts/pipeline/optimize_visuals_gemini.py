import sys
import os
import json
import re
from pathlib import Path
from google import genai

# --- CONFIG ---
def get_genai_client():
    api_key = "AIzaSyBXHcy_pl9m4PQHh4cD4fBG3z-YAeK11NA"
    if not api_key:
        print("❌ Error: GEMINI_API_KEY is missing.")
        sys.exit(1)
    return genai.Client(api_key=api_key)

# --- MASTER OPTIMIZER PROMPT (FIXES TEXT & VISUALS) ---
OPTIMIZER_PROMPT = """
Act as a Senior Video Editor and Fact-Checker.
You have a JSON script for a viral short. 
You must IMPROVE both the **Script Text** and the **Visuals**.

Input JSON:
<<JSON_DATA>>

**YOUR TASKS:**

1. 🔍 **FIX THE TEXT (Quality Control):**
   - Check the 'text' field for typos, hallucinated words, or weird grammar.
   - **CORRECT** misspelled names (e.g., "Lambhi De Harmines" -> "Lambi Dehar Mines").
   - **REMOVE** nonsense words (e.g., change "nacephalys" to "anomalies" or "creatures").
   - Keep the tone conversational and simple (Grade 6 level).
   - Ensure the script loops seamlessly (last sentence flows into first).

2. 👁️ **FIX THE VISUALS (Strict Stock Footage):**
   - **NO LIFESTYLE CLIPS:** Never show happy couples, people on laptops, or casual friends unless the script demands it.
   - **MATCH THE MOOD:** - If mood="scary", use "dark, misty, shadow, drone shot".
     - If mood="happy", use "bright, sunny, vivid colors".
   - **ABSTRACT CONCEPTS:** If script says "We may never know...", use "time-lapse night sky" or "dark ocean waves", NOT "person thinking".
   - **FORMAT:** Provide EXACTLY 2 distinct, comma-separated search keywords per segment.

3. 🖼️ **GENERATE THUMBNAIL PROMPT:**
   - Add a new field "thumbnail_prompt" to the root of the JSON.
   - Write a prompt for an AI Image Generator (Midjourney/DALL-E) to make a high-CTR cover.
   - Style: "Hyper-realistic, 8k, high contrast, dramatic lighting".

**OUTPUT:**
- Return the SAME JSON structure (with updated 'text' and 'visual_keywords', plus the new 'thumbnail_prompt').
- Output JSON ONLY. No markdown.
"""

def optimize_json(json_path: Path):
    if not json_path.exists():
        print(f"❌ Error: File not found at {json_path}")
        return None

    print(f"🎨 Polishing Text & Visuals for: {json_path.name}...")
    
    # 1. Load the existing JSON
    with open(json_path, "r", encoding="utf-8") as f:
        original_data = json.load(f)

    # 2. Prepare the prompt
    client = get_genai_client()
    
    json_str = json.dumps(original_data, indent=2)
    prompt = OPTIMIZER_PROMPT.replace("<<JSON_DATA>>", json_str)

    # 3. Call Gemini
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=prompt
        )
        raw_text = response.text.strip()

        # 4. Clean and Parse Response
        clean_json = re.sub(r"^```json\s*", "", raw_text)
        clean_json = re.sub(r"^```\s*", "", clean_json)
        clean_json = re.sub(r"\s*```$", "", clean_json)
        
        optimized_data = json.loads(clean_json)

        # 5. Safety Checks & Saving
        if "script_segments" in optimized_data:
            # ✅ FAIL-SAFE: Preserve metadata/mood/topic from original
            for key in ["metadata", "mood", "topic"]:
                if key in original_data and key not in optimized_data:
                    optimized_data[key] = original_data[key]

            # Create new path
            new_path = json_path.parent / f"{json_path.stem}_opt.json"
            
            with open(new_path, "w", encoding="utf-8") as f:
                json.dump(optimized_data, f, ensure_ascii=False, indent=2)
                
            print(f"✅ Optimization Complete! Saved to: {new_path.name}")
            
            # Print Report
            print("\n--- OPTIMIZATION REPORT ---")
            
            # Check Thumbnail
            if "thumbnail_prompt" in optimized_data:
                print(f"🖼️ Thumbnail Prompt Generated: YES")
            else:
                print(f"⚠️ Thumbnail Prompt Missing")

            # Check Text Changes
            orig_segs = original_data.get("script_segments", [])
            new_segs = optimized_data.get("script_segments", [])
            
            changes_detected = False
            for i in range(min(3, len(orig_segs))):
                orig_txt = orig_segs[i]['text']
                new_txt = new_segs[i]['text']
                
                # Show if text was fixed
                if orig_txt != new_txt:
                    print(f"[{i+1}] 📝 Text FIXED:")
                    print(f"     OLD: {orig_txt[:40]}...")
                    print(f"     NEW: {new_txt[:40]}...")
                    changes_detected = True
                
                # Show visuals
                print(f"     👁️ Visuals: {new_segs[i].get('visual_keywords', 'N/A')}")
            
            if not changes_detected:
                print("✅ Text was already perfect (no changes needed).")
            
            print("------------------------------\n")
            
            return new_path
            
        else:
            print("⚠️ AI returned invalid JSON. Using original file.")
            return json_path

    except Exception as e:
        print(f"❌ Optimization failed: {e}")
        return json_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python optimize_visuals_gemini.py <path_to_json>")
        sys.exit(1)
    
    path = Path(sys.argv[1])
    optimize_json(path)