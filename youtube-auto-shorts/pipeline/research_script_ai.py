# pipeline/research_script_ai.py
# Uses OpenAI (or Gemini) to actually research and write a 60-sec Shorts script

import sys
import json
from pathlib import Path
import os
import openai

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

openai.api_key = os.getenv("OPENAI_API_KEY")

PROMPT_TEMPLATE = """
Act as a professional YouTube script writer.
Research the topic: "{topic}"

Steps:
1) Gather up-to-date info from reliable sources (in your internal knowledge).
2) Summarize accurately.
3) Write a 60-second YouTube Shorts script:
   - hook (exciting, not clickbait)
   - clear explanation
   - helpful/educational
   - conversational tone
   - 1 practical takeaway
   - natural sentences (not numbered)
   - monetizable friendly (no claims, no politics, no hate)
   - simple english

End with: “Sources: public knowledge + research”
Do NOT reference Wikipedia if uncertain.
Do NOT add scene directions.
Do NOT use bullet points or numbering.
"""

def make_script(topic):
    prompt = PROMPT_TEMPLATE.format(topic=topic)
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=450,
        temperature=0.6,
    )
    return resp["choices"][0]["message"]["content"].strip()

if __name__ == "__main__":
    topic = sys.argv[1]
    script = make_script(topic)
    safe = topic.replace(" ", "_")

    (OUT / f"{safe}.txt").write_text(script, encoding="utf-8")

    print("\n------ SCRIPT ------\n")
    print(script)
