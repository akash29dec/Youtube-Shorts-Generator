import time
import sys
from pathlib import Path

# Try to import the pipeline
try:
    print("⚙️ Loading pipeline modules...")
    from main import run_pipeline
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Could not import 'main.py'. Reason: {e}")
    sys.exit(1)

TOPICS_FILE = Path("topics.txt")

def determine_mood(topic):
    """
    Automatically picks the best mood based on keywords in the title.
    """
    topic_lower = topic.lower()
    
    # 1. WEALTH & DISCIPLINE (Uses the new 'energetic' preset)
    if any(x in topic_lower for x in ['poor', 'rich', 'money', 'wealth', 'millionaire', 'success', 'discipline', 'grind', 'business']):
        return "energetic"
    
    # 2. STOICISM & PEACE (Uses 'calm' preset)
    elif any(x in topic_lower for x in ['stoic', 'calm', 'peace', 'silence', 'strength', 'alone', 'monk', 'focus']):
        return "calm"
    
    # 3. DARK PSYCHOLOGY & WARNINGS (Uses 'intense' preset)
    elif any(x in topic_lower for x in ['manipulate', 'lie', 'jealous', 'dark', 'danger', 'warning', 'never', 'signs', 'secretly']):
        return "intense"
        
    # 4. HORROR / MYSTERY (Uses 'scary' preset)
    elif any(x in topic_lower for x in ['ghost', 'haunted', 'death', 'scary', 'creepy', 'night', 'whistle']):
        return "scary"

    # Default fallback
    return "default"

def batch_generate():
    print(f"📂 Reading topics from: {TOPICS_FILE.resolve()}")
    
    if not TOPICS_FILE.exists():
        print("❌ ERROR: 'topics.txt' file not found.")
        return

    try:
        content = TOPICS_FILE.read_text(encoding="utf-8")
        topics = [line.strip() for line in content.splitlines() if line.strip()]
    except Exception as e:
        print(f"❌ ERROR reading text file: {e}")
        return

    print(f"🏭 FOUND {len(topics)} TOPICS. STARTING SMART BATCH...")
    print("=" * 60)

    for i, line in enumerate(topics):
        topic = line.strip()
        
        # 🧠 AUTO-MOOD DETECTION
        mood = determine_mood(topic)

        print(f"\n🚀 [VIDEO {i+1}] Topic: '{topic}'")
        print(f"   🤖 Auto-Mood: '{mood}'")
        
        try:
            run_pipeline(topic, manual_mood=mood)
        except Exception as e:
            print(f"❌ FAILED topic '{topic}': {e}")
            continue

    print("\n" + "="*60)
    print("✅ BATCH COMPLETE. Check 'final_videos'.")

if __name__ == "__main__":
    batch_generate()