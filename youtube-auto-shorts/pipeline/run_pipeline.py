# pipeline/run_pipeline.py
# FULL AUTOMATED PIPELINE
# topic -> script -> TTS -> cloned voice -> visuals -> dynamic captions

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

PY = sys.executable  # always use venv python

def run(cmd_list, step: str):
    print(f"\n==============================")
    print(f"STEP: {step}")
    print("Running:", " ".join(cmd_list))
    subprocess.run(cmd_list, check=True)

if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI tools for students"
    safe = topic.replace(" ", "_")

    script_file = OUTPUT_DIR / f"{safe}.txt"

    # -------------------------------------------------
    # 1) Research + Script (Gemini)
    # -------------------------------------------------
    run(
        [PY, "pipeline/research_script_gemini.py", topic],
        "1️⃣ Gemini: Research & script generation",
    )

    if not script_file.exists():
        raise FileNotFoundError(f"Script not found: {script_file}")

    # -------------------------------------------------
    # 2) Base TTS
    # -------------------------------------------------
    run(
        [PY, "pipeline/base_tts.py", str(script_file)],
        "2️⃣ Generating base TTS audio",
    )

    # -------------------------------------------------
    # 3) Voice cloning (Applio)
    # -------------------------------------------------
    run(
        [PY, "pipeline/convert_applio.py"],
        "3️⃣ Voice cloning (Applio)",
    )

    # -------------------------------------------------
    # 4) Generate visuals (Pexels videos + transitions)
    # -------------------------------------------------
    run(
        [PY, "pipeline/generate_visuals.py", topic],
        "4️⃣ Generating visuals (videos + crossfades)",
    )

    # -------------------------------------------------
    # 5) Dynamic 1-line captions (audio-aligned)
    # -------------------------------------------------
    run(
        [PY, "pipeline/generate_dynamic_captions.py", topic],
        "5️⃣ Generating dynamic captions",
    )

    # -------------------------------------------------
    # 5) Aligning 1-line captions (audio-aligned)
    # -------------------------------------------------
    run(
        [PY, "pipeline/align_script_to_audio.py", topic],
        "At last Aligning script to audio timestamps",
    )

    print("\n🎉 PIPELINE COMPLETE")
    print("📁 Output folder:", OUTPUT_DIR)
