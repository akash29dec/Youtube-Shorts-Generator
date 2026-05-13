import sys
import asyncio
import edge_tts
from pathlib import Path

# --- 1. CONFIGURATION & MOODS ---
MOOD_PRESETS = {
    "scary":   {"voice": "en-US-AvaMultilingualNeural", "style": "whispering", "rate": "+2%",   "pitch": "+5Hz"},
    "energetic": {"voice": "en-US-AvaMultilingualNeural", "style": "serious",  "rate": "+10%",  "pitch": "-2Hz"},
    "happy":   {"voice": "en-US-AvaMultilingualNeural", "style": "cheerful",   "rate": "+5%",  "pitch": "+5Hz"},
    "intense": {"voice": "en-US-AvaMultilingualNeural", "style": "angry",      "rate": "+5%",  "pitch": "-2Hz"},
    "timid":   {"voice": "en-US-AvaMultilingualNeural", "style": "fearful",    "rate": "-5%",   "pitch": "+2Hz"},
    "calm":    {"voice": "en-US-AvaMultilingualNeural", "style": "calm",       "rate": "-5%",   "pitch": "-5Hz"},
    "default": {"voice": "en-US-AvaMultilingualNeural", "style": "serious",   "rate": "+2%",   "pitch": "-5Hz"} 
}

def clean_text_for_flow(text):
    """
    Removes structural pauses to prevent robotic stopping.
    """
    text = text.replace(",", " ")
    text = text.replace("...", " ")
    text = text.replace(";", " ")
    return " ".join(text.split())

async def generate_tts_smart(text_file, output_file, mood="default"):
    # 1. Validation
    if not text_file.exists():
        print(f"❌ Error: Script file not found at {text_file}")
        return

    raw_text = text_file.read_text(encoding="utf-8").strip()
    if not raw_text:
        print("❌ Error: Script file is empty!")
        return

    # 2. Optimize Text Flow
    text = clean_text_for_flow(raw_text)

    # 3. Select Settings
    mood = mood.lower().strip()
    settings = MOOD_PRESETS.get(mood, MOOD_PRESETS["default"])
    
    print(f"🎭 Voice: {settings['voice']} | Mood: {mood} | Rate: {settings['rate']}")

    # 4. GENERATE (The v7.2.7 Way)
    # We DO NOT build SSML manually. We pass arguments to the library.
    # The library will build the SSML internally.
    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice=settings['voice'],
            rate=settings['rate'],
            pitch=settings['pitch']
        )
        await communicate.save(output_file)
        print(f"✅ Audio Saved: {output_file}")
    except Exception as e:
        print(f"❌ Error generating audio: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        script_path = Path(sys.argv[1])
        mood_arg = sys.argv[2] if len(sys.argv) > 2 else "default"
        output_path = script_path.parent / "base_tts.mp3"
        asyncio.run(generate_tts_smart(script_path, output_path, mood_arg))