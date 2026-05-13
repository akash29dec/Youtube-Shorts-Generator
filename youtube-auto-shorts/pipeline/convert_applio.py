# pipeline/convert_applio.py
# For now: pretend to send base_tts.wav to Applio and get cloned.wav
# Currently just copies base_tts.wav -> cloned.wav (placeholder)

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def fake_applio_convert(base_wav: Path, cloned_wav: Path):
    if not base_wav.exists():
        raise FileNotFoundError(f"Base TTS file not found: {base_wav}")
    # placeholder: just copy the file
    shutil.copy(base_wav, cloned_wav)
    print(f"[FAKE APPLIO] Copied {base_wav.name} -> {cloned_wav.name}")

if __name__ == "__main__":
    base = OUTPUT_DIR / "base_tts.wav"
    cloned = OUTPUT_DIR / "cloned.wav"
    fake_applio_convert(base, cloned)
    print("Cloned voice saved as:", cloned)
