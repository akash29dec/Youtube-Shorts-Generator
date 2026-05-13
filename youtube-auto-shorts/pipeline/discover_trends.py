# pipeline/discover_trends.py
# Robust trending topic discovery:
# 1) try pytrends.trending_searches
# 2) fallback to Google Trends daily RSS feed
# 3) fallback to youtube-search-python quick query results
#
# Output: output/trending_candidates.json

from pathlib import Path
import json
import time

OUT = Path(__file__).resolve().parents[1] / "output"
OUT.mkdir(exist_ok=True)

# Try pytrends first
def get_trends_pytrends(region='india', top_n=15):
    try:
        from pytrends.request import TrendReq
    except Exception as e:
        print("pytrends not installed or import failed:", e)
        return []

    try:
        pytrends = TrendReq(hl='en-US', tz=330)
        # pytrends uses 'pn' values like 'india', 'united_states'
        df = pytrends.trending_searches(pn=region)
        return df[0].tolist()[:top_n]
    except Exception as e:
        print("pytrends trending_searches failed:", type(e).__name__, e)
        return []

# Fallback: Google Trends RSS (daily)
def get_trends_rss(region='IN', top_n=15):
    # Map common names -> country code used by RSS endpoint
    code = region.upper() if len(region) <= 3 else {
        'india':'IN', 'united_states':'US', 'united_kingdom':'GB',
        'canada':'CA', 'australia':'AU'
    }.get(region.lower(), 'US')
    url = f'https://trends.google.com/trends/trendingsearches/daily/rss?geo={code}'
    try:
        import requests
        import xml.etree.ElementTree as ET
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall('.//item')
        topics = []
        for it in items[:top_n]:
            title = it.find('title').text if it.find('title') is not None else None
            if title:
                topics.append(title.strip())
        return topics
    except Exception as e:
        print("RSS fallback failed:", type(e).__name__, e)
        return []

# Last fallback: youtube-search-python quick searches for "trending" keywords
def get_trends_youtube(sample_queries=None, top_n=10):
    try:
        from youtubesearchpython import VideosSearch
    except Exception as e:
        print("youtube-search-python not installed:", e)
        return []

    if sample_queries is None:
        sample_queries = ["trending now", "hot right now", "top news", "viral", "breaking"]

    topics = []
    for q in sample_queries:
        try:
            vs = VideosSearch(q + " shorts", limit=5)
            res = vs.result().get("result", [])
            for r in res:
                title = r.get("title")
                if title and title not in topics:
                    topics.append(title)
                    if len(topics) >= top_n:
                        return topics[:top_n]
        except Exception as e:
            print("youtube search failed for", q, e)
        time.sleep(0.9)
    return topics[:top_n]

if __name__ == "__main__":
    # choose region string for pytrends ('india','united_states', etc) and code for RSS ('IN','US')
    pytrends_region = 'india'   # change if you want another country
    rss_region_code = 'IN'      # ISO code for RSS fallback
    top_n = 15

    print("Trying pytrends...")
    topics = get_trends_pytrends(region=pytrends_region, top_n=top_n)
    if topics:
        source = "pytrends"
    else:
        print("Pytrends failed — trying RSS endpoint...")
        topics = get_trends_rss(region=rss_region_code, top_n=top_n)
        if topics:
            source = "google_trends_rss"
        else:
            print("RSS failed — falling back to youtube-search-python")
            topics = get_trends_youtube(top_n=top_n)
            source = "youtube_search_fallback"

    # For each topic gather a few youtube example videos (quick check)
    examples = []
    try:
        from youtubesearchpython import VideosSearch
        for t in topics:
            try:
                vs = VideosSearch(t + " shorts", limit=4)
                res = vs.result().get("result", [])
                vids = [{"title": v.get("title"), "link": v.get("link"), "duration": v.get("duration")} for v in res]
            except Exception:
                vids = []
            examples.append({"topic": t, "youtube_examples": vids})
            time.sleep(0.9)
    except Exception:
        # If youtube-search-python missing, just return topics
        examples = [{"topic": t, "youtube_examples": []} for t in topics]

    out_path = OUT / "trending_candidates.json"
    out_path.write_text(json.dumps({"source": source, "candidates": examples}, indent=2), encoding="utf-8")
    print("Saved trending candidates to", out_path)
