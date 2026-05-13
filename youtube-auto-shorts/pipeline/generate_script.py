# pipeline/generate_script.py
# Simple script generator: Topic -> short YouTube Shorts script (.txt)

import sys
from pathlib import Path

# ROOT is the project root (folder above /pipeline)
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def make_script(topic: str) -> str:
    hook = f"Want a quick fact about {topic}?"
    bullets = [
        f"1) {topic} is trending right now.",
        "2) It affects your daily life more than you think.",
        "3) Learn one fast tip in under a minute.",
    ]
    insight = f"My quick tip: try one small change using {topic} today."
    cta = "Like & subscribe for more 60-second tips!"

    parts = [hook, ""] + bullets + ["", insight, "", cta]
    return "\n".join(parts)

if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI tools"
    script = make_script(topic)

    safe_name = topic.replace(" ", "_")
    out_path = OUTPUT_DIR / f"{safe_name}.txt"

    out_path.write_text(script, encoding="utf-8")

    print("Saved script to:", out_path)
    print("------ SCRIPT ------")
    print(script)
