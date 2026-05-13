# pipeline/applio_infer.py
import sys
import subprocess
import os
from pathlib import Path

# --- CONFIGURATION ---
ROOT = Path(__file__).resolve().parents[1]
APPLIO_DIR = ROOT / "applio"
OUT_DIR = ROOT / "output"

# MODEL CONFIG (Verify these exist!)
MODEL_NAME = "mikky_500e_5000s.pth"  
INDEX_FILENAME = "mikky.index"

PYTHON_EXE = APPLIO_DIR / "venv" / "Scripts" / "python.exe"
CORE_SCRIPT = APPLIO_DIR / "core.py"

def convert_voice(input_path: Path, output_path: Path):
    """
    Runs Applio RVC to convert input audio (EdgeTTS) into the cloned voice.
    """
    # 1. Verification
    if not input_path.exists():
        raise FileNotFoundError(f"❌ Input file not found: {input_path}")
    
    if not CORE_SCRIPT.exists():
        raise FileNotFoundError(f"❌ Applio core.py not found at: {CORE_SCRIPT}")

    # 2. Build the Command
    cmd = [
        str(PYTHON_EXE),
        str(CORE_SCRIPT),
        "infer",
        "--pth_path", str(APPLIO_DIR / "assets" / "weights" / MODEL_NAME),
        "--index_path", str(APPLIO_DIR / "logs" / INDEX_FILENAME),
        "--input_path", str(input_path),
        "--output_path", str(output_path),
        "--f0_method", "rmvpe",      # Best quality pitch algorithm
        "--pitch", "0",              # Pitch shift
        "--index_rate", "0.75",      # Accent retention strength
        "--volume_envelope", "1",
        "--protect", "0.33",
        "--split_audio", "False"
    ]

    print(f"🔄 [RVC] Converting voice: {input_path.name} -> {output_path.name}")

    # 3. Run It
    try:
        # We must set CWD to APPLIO_DIR so it finds its internal configs
        result = subprocess.run(
            cmd, 
            cwd=APPLIO_DIR, 
            check=True, 
            text=True, 
            capture_output=True,
            env={**os.environ, "SYSTEMROOT": os.getenv("SYSTEMROOT")} # Fix for some Windows envs
        )
        print(f"✅ Voice Conversion Complete: {output_path}")
        
    except subprocess.CalledProcessError as e:
        print("\n❌ APPLIO FAILED")
        print("---------------- ERROR LOG ----------------")
        print(e.stderr)
        print("-------------------------------------------")
        raise RuntimeError("Applio inference failed.")

if __name__ == "__main__":
    # Test run
    test_in = OUT_DIR / "base_tts.mp3"
    test_out = OUT_DIR / "cloned.wav"
    convert_voice(test_in, test_out)