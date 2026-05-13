import sys
import os
import re
import json
from pathlib import Path
from google import genai
from google.genai import types  # Import types for config

# --- CONFIG ---
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

# --- Small trigger -> visual mapping (customize as needed) ---
TRIGGER_TO_VISUALS = {
    "ancient egypt": ["egyptian tomb", "pharaoh statue", "hieroglyphs close-up", "ancient doll"],
    "wax": ["vintage wax doll", "melting wax close-up", "wax figure with hair"],
    "human hair": ["strand of human hair close-up", "hair being pulled", "hair on vintage doll"],
    "human eyes": ["close-up human eye", "eyeblink slow-mo", "eye reflection"],
    "magic": ["occult ritual scene", "candles and runes", "mysterious hands doing ritual"],
    "ritual": ["dark ritual candles", "circle of stones", "ancient altar"],
    "city fountain": ["city fountain wide shot", "fountain close-up with water splashes"],
    "cocktail": ["cocktail glass close-up", "pouring drink", "straw in drink"],
}

# Basic stopwords for quick noun-ish extraction
STOPWORDS = set(["the","a","an","and","but","or","so","then","you","it","is","was","are","be","to","of","in","on","for","with","that","this","as","by","from","at","your"])

# --- CONFIG FOR GENAI ---

def get_genai_client():
    """
    Returns an authenticated GenAI Client.
    """
    api_key = "AIzaSyBXHcy_pl9m4PQHh4cD4fBG3z-YAeK11NA"
    if not api_key:
        print("❌ Error: GEMINI_API_KEY is missing.")
        sys.exit(1)
    
    # NEW SYNTAX: Initialize Client directly
    return genai.Client(api_key=api_key)

# --- PROMPT ENGINEERING ---
PROMPT_TEMPLATE = """
Act as a Viral Content Creator for a 'Dark Self-Improvement' YouTube Shorts channel.
Topic: "<<TOPIC>>"

STRUCTURE:
1. **The Hook (0-3s):** State a controversial or painful truth. Use "You" to attack the viewer's ego. (e.g., "You are poor because you are distracted.")
2. **The Insight (3-40s):** Give 3 rapid-fire psychological facts or harsh truths. No fluff. Direct and brutal.
3. **The Loop (40-60s):** End with a sentence that seamlessly flows back into the start.

TONE: Machiavellian, brutal, direct, authoritative. Grade 5 reading level.

OUTPUT JSON ONLY:
{
  "mood": "intense", 
  "metadata": {"title":"Viral Title","tags":"psychology, money, stoicism"},
  "script_segments": [
    {"text": "Hook sentence.", "visual_keywords": "visual1, visual2"},
    ...
  ]
}
"""

def clean_script_text(text: str) -> str:
    text = text.replace("*", "").replace("#", "").replace("`", "")
    text = re.sub(r'\[.*?\]', '', text)
    text = " ".join(text.split())
    return text

def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    s = re.sub(r"-+", "-", s).strip('-')
    return s[:120]

def extract_candidate_visual_words(text: str, max_words=3):
    tokens = re.findall(r"\w+", text.lower())
    candidates = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
    joined = []
    for i, w in enumerate(candidates):
        if w in ("ancient","old") and i+1 < len(candidates):
            joined.append(w + " " + candidates[i+1])
    seen = set()
    result = []
    for w in (joined + candidates):
        if w not in seen:
            seen.add(w)
            result.append(w)
        if len(result) >= max_words:
            break
    return result

def map_triggers_to_visuals(words):
    visuals = []
    text_joined = " ".join(words)
    for trig, vlist in TRIGGER_TO_VISUALS.items():
        if trig in text_joined:
            visuals.extend(vlist)
    for w in words:
        if w in TRIGGER_TO_VISUALS:
            visuals.extend(TRIGGER_TO_VISUALS[w])
        else:
            if " " in w:
                visuals.append(w + " close-up")
            else:
                visuals.append(w + " close-up")
    seen = set()
    out = []
    for v in visuals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out[:2]

def enhance_visual_keywords(data: dict):
    segments = data.get('script_segments', [])
    for seg in segments:
        text = seg.get('text', '')
        vk = seg.get('visual_keywords', '')
        if not vk or len(vk.strip()) < 3 or vk.strip().lower() in ("b-roll","background","generic footage","filler"):
            candidates = extract_candidate_visual_words(text)
            mapped = map_triggers_to_visuals(candidates)
            if mapped:
                seg['visual_keywords'] = ", ".join(mapped)
            else:
                first_words = " ".join(text.split()[:3])
                seg['visual_keywords'] = first_words + " close-up"
        else:
            pieces = [p.strip() for p in vk.split(',') if p.strip()]
            seg['visual_keywords'] = ", ".join(pieces[:2])
    return data

def make_script(topic: str):
    print(f"🧠 Brainstorming viral story for: '{topic}'...")
    
    # 1. Get the Client
    client = get_genai_client()

    try:
        # SAFELY inject the topic
        prompt_text = PROMPT_TEMPLATE.replace("<<TOPIC>>", topic)

        # 2. NEW GENERATION CALL
        # Note: I changed model to 'gemini-2.0-flash' as '3-flash' is not standard yet.
        # Added 'response_mime_type' to enforce JSON output (New SDK Feature)
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=prompt_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        raw_text = response.text.strip()

        # Clean JSON wrappers (still good to keep for safety)
        clean_json = re.sub(r"^```json\s*", "", raw_text)
        clean_json = re.sub(r"^```\s*", "", clean_json)
        clean_json = re.sub(r"\s*```$", "", clean_json)

        try:
            data = json.loads(clean_json)
        except json.JSONDecodeError:
            print("⚠️ JSON Parse Error. Attempting robust fix...")
            start = clean_json.find("{")
            end = clean_json.rfind("}")
            if start != -1 and end != -1:
                clean_json = clean_json[start:end+1]
                data = json.loads(clean_json)
            else:
                raise ValueError("Could not extract JSON from response")

        if 'script_segments' not in data or not isinstance(data['script_segments'], list):
            raise ValueError("Generated JSON missing 'script_segments' list")

        full_text = ""
        seg_count = 0
        for seg in data['script_segments']:
            if 'text' not in seg:
                seg['text'] = ""
            seg['text'] = clean_script_text(seg['text'])
            full_text += seg['text'] + " "
            seg_count += 1

        data = enhance_visual_keywords(data)
        words = len(full_text.split())

        slug = slugify(topic)
        out_path = OUT / f"{slug}_script_with_visuals.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("-" * 30)
        print(f"📝 Story generated: {words} words.")
        print(f"🎞️ Visual Scenes: {seg_count}")
        print(f"🎭 Mood: {data.get('mood', 'neutral')}")
        print(f"💾 Saved to: {out_path}")
        print("-" * 30)

        print("\n--- SCRIPT PREVIEW ---\n")
        for i, seg in enumerate(data['script_segments']):
            print(f"[{i+1}] {seg['text']}")
            print(f"     -> visual_keywords: {seg.get('visual_keywords', '')}")
        print("\n----------------------\n")

        return data, full_text.strip()

    except Exception as e:
        print(f"❌ Error in script generation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python research_script_gemini.py <topic>")
        sys.exit(1)
    make_script(" ".join(sys.argv[1:]))