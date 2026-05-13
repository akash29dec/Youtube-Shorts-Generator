# pipeline/research_script_wiki.py
# Research a topic from Wikipedia and turn it into a 40-60s monetizable, educational script.

import sys
import json
from pathlib import Path
import wikipedia

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

TEMPLATE = """{hook}

{point1}
{point2}
{point3}

{practical}

{disclaimer}
{sources}
"""

def get_wiki_info(topic: str, sentences: int = 3):
    try:
        summary = wikipedia.summary(topic, sentences=sentences)
        page = wikipedia.page(topic)
        url = page.url
    except wikipedia.DisambiguationError as e:
        # pick first option if ambiguous
        choice = e.options[0]
        summary = wikipedia.summary(choice, sentences=sentences)
        url = wikipedia.page(choice).url
    except Exception:
        summary = "No reliable summary found."
        url = ""
    return summary, url

def make_script(topic: str, summary: str, url: str) -> dict:
    # break summary into short bullet-like facts
    sentences = [s.strip() for s in summary.split(".") if s.strip()]
    if len(sentences) < 3:
        sentences += ["This topic is widely discussed online.", "Always check multiple sources."]

    facts = sentences[:3]

    hook = f"Stop scrolling! In under a minute, here’s a simple breakdown of {topic}."
    point1 = f"1) {facts[0]}"
    point2 = f"2) {facts[1]}"
    point3 = f"3) {facts[2]}"

    practical = (
        f"Practical tip: Don’t just hear about {topic}. Take one small action today — "
        f"like reading a short article or trying one basic example related to it."
    )

    disclaimer = (
        "Disclaimer: This video is for educational and informational purposes only. "
        "Always verify important decisions with multiple trusted sources."
    )

    sources_line = "Sources: " + (url if url else "Public reference sources and general knowledge.")

    script = TEMPLATE.format(
        hook=hook,
        point1=point1,
        point2=point2,
        point3=point3,
        practical=practical,
        disclaimer=disclaimer,
        sources=sources_line,
    )

    return {
        "topic": topic,
        "script": script,
        "summary": summary,
        "source_url": url,
    }

if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "Artificial intelligence"
    summary, url = get_wiki_info(topic, sentences=3)
    data = make_script(topic, summary, url)

    safe = topic.replace(" ", "_")
    txt_path = OUT / f"{safe}.txt"
    meta_path = OUT / f"{safe}_meta.json"

    txt_path.write_text(data["script"], encoding="utf-8")
    meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print("Saved script to:", txt_path)
    print("Saved metadata to:", meta_path)
    print("------ SCRIPT ------")
    print(data["script"])
