import os
from pathlib import Path

target = Path("topics.txt")

print(f"📂 Current Working Directory: {os.getcwd()}")
print(f"🔍 Looking for: {target.resolve()}")

if not target.exists():
    print("❌ FAILURE: Python cannot find 'topics.txt'.")
    print("   -> Check if the file is named 'topics.txt.txt'")
    print("   -> Check if you are in the correct folder.")
else:
    content = target.read_text().splitlines()
    clean_topics = [t for t in content if t.strip()]
    print(f"✅ SUCCESS: File found!")
    print(f"📝 Raw lines in file: {len(content)}")
    print(f"🏭 Valid topics found: {len(clean_topics)}")
    
    if len(clean_topics) == 0:
        print("⚠️ WARNING: File exists but is empty (or only has whitespace).")