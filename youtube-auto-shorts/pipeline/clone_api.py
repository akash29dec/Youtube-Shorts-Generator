import sys
from pathlib import Path
import torch
from TTS.api import TTS

# --- PATHS ---
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/Scripts"
OUT.mkdir(exist_ok=True, parents=True)

REFERENCE_AUDIO = ROOT / "datasetofficial.wav"
OUTPUT_FILE = OUT / "cloned_local_voice.wav"

def clone_locally(script_path):
    text_content = script_path.read_text(encoding="utf-8").strip()
    
    # 1. Clean the text (removes extra hidden spaces/newlines)
    text_content = " ".join(text_content.split())

    print("⏳ Loading XTTS Model...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

    print("🎙️ Generating Audio...")
    tts.tts_to_file(
        text=text_content,
        speaker_wav=str(REFERENCE_AUDIO),
        language="en",
        file_path=str(OUTPUT_FILE),
        split_sentences=True  # <--- THIS IS THE KEY FIX
    )
    print(f"✅ Success! Saved to: {OUTPUT_FILE}")
    
if __name__ == "__main__":
    script_arg = Path(sys.argv[1])
    clone_locally(script_arg)