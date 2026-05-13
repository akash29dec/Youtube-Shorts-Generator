# YouTube Shorts Generator 🎬🤖

An automated AI-powered pipeline that generates fully-fledged YouTube Shorts from a simple text topic. It handles everything from scriptwriting, voiceover generation, voice cloning (RVC), visual matching, and dynamic subtitle burning.

## 🌟 Features

- **AI Script Generation**: Utilizes Google Gemini to research and write engaging, short-form video scripts.
- **Visual & Script Optimization**: Automatically polishes scripts, fixes typos, and generates high-quality visual prompts.
- **Emotional TTS**: Generates base audio using emotional TTS depending on the topic's "mood" (e.g., energetic, calm, intense, scary).
- **RVC Voice Cloning**: Converts the base TTS voice into a highly realistic, custom AI voice using the integrated **Applio** engine.
- **Dynamic Visuals & Music**: Automatically fetches and stitches background visuals that match the scene's mood.
- **Subtitles & Captions**: Generates `.ass` subtitle files and burns them natively into the final video to maximize engagement.
- **Batch Processing Mode**: Input multiple topics and let the `batch_runner.py` generate multiple videos while you sleep!

## 🛠️ Prerequisites

- **Python 3.9+** (or standard modern Python versions)
- **FFmpeg**: Must be installed and added to your system's PATH.

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/akash29dec/Youtube-Shorts-Generator.git
   cd Youtube-Shorts-Generator/youtube-auto-shorts
   ```

2. **Set up a Virtual Environment** (Recommended):
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: You may also need to install specific dependencies for Applio and Google Generative AI if not already set).*

## 📖 Usage

### 1. Single Video Generation

To generate a single video, run `main.py` and pass the topic as an argument:

```bash
cd youtube-auto-shorts
python main.py "The Philosophy of Marcus Aurelius"
```

The script will:
1. Generate the script and optimize it.
2. Produce a base audio file.
3. Convert the audio using the RVC Applio pipeline.
4. Assemble background videos and music.
5. Burn the subtitles.
6. Save the final MP4 inside the `final_videos/` directory.

### 2. Batch Generation

Want to generate multiple shorts at once? 

1. Add your topics inside `youtube-auto-shorts/topics.txt` (one topic per line):
   ```text
   How to build discipline
   Scariest deep sea creatures
   Stoic quotes for hard times
   ```
2. Run the Batch Runner:
   ```bash
   cd youtube-auto-shorts
   python batch_runner.py
   ```
   The `batch_runner.py` uses an **Auto-Mood Detection** algorithm to automatically assign the best vocal tone (energetic, calm, intense, scary) based on keywords in your topic!

## 📂 Project Structure

```
Youtube-Shorts-Generator/
├── youtube-auto-shorts/
│   ├── main.py                # Main single-video generation pipeline
│   ├── batch_runner.py        # Batch generation script
│   ├── topics.txt             # Text file for batch video topics
│   ├── requirements.txt       # Python dependencies
│   ├── pipeline/              # Core modules (TTS, Visuals, RVC, Scripting)
│   ├── applio/                # RVC Voice Conversion Engine integration
│   ├── final_videos/          # Output directory for finished MP4s
│   ├── output/                # Temporary directory for intermediate files (audio, JSON, etc.)
│   └── models/                # Directory for storing voice models
└── .gitignore                 # Standardized ignore rules
```

## 🤝 Contributing

Contributions are welcome! If you have any ideas, suggestions, or bug reports, feel free to open an issue or submit a pull request.
