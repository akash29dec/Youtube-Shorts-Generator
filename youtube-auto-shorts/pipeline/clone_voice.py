import sys
import torch
import numpy as np
from pathlib import Path
from TTS.api import TTS
import ssl
import re
from scipy.io import wavfile
import librosa 

# --- 1. SSL FIX ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- PATHS ---
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

# --- CONFIG ---
REFERENCE_AUDIO = ROOT / "audio_8591a4.wav" 
OUTPUT_FILE = OUT / "cloned_voice.wav"

# --- SETTINGS ---
SPEED = 1.1             # Slightly faster for shorts
PAUSE_DURATION = 0.2    # Natural pause

def split_into_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def preprocess_reference_audio(audio_path):
    print(f"🧹 Cleaning reference audio: {audio_path.name}...")
    # Load with Librosa (Fixes MP3/Header crash)
    wav, sr = librosa.load(str(audio_path), sr=None, mono=True)
    
    # Aggressive Trim to remove initial static
    wav, _ = librosa.effects.trim(wav, top_db=20)
    
    clean_path = OUT / "temp_clean_ref.wav"
    wav_int16 = (wav * 32767).astype(np.int16)
    wavfile.write(clean_path, sr, wav_int16)
    return str(clean_path)

def clone_my_voice(script_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🚀 Loading XTTS Model on {device}...")
    
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    
    # 1. Clean Reference
    clean_ref_path = preprocess_reference_audio(REFERENCE_AUDIO)
    
    # 2. Get Latents
    print(f"🧠 Extracting speaker latents...")
    gpt_cond_latent, speaker_embedding = tts.synthesizer.tts_model.get_conditioning_latents(
        audio_path=[clean_ref_path]
    )
    
    # --- FIX: THE WARM-UP ---
    # We generate a dummy sentence first to 'warm up' the model tensors.
    # This absorbs the 'robotic start' glitch. We throw this audio away.
    print("🔥 Warming up model (Discarding first run)...")
    try:
        tts.synthesizer.tts_model.inference(
            text="This is just a warm up.",
            language="en",
            gpt_cond_latent=gpt_cond_latent,
            speaker_embedding=speaker_embedding,
            temperature=0.1, # Low temp for stability
            length_penalty=1.0,
            repetition_penalty=1.2,
            top_k=50,
            top_p=0.8,
            enable_text_splitting=False
        )
    except Exception:
        pass # Ignore warmup errors
    
    # 3. Read & Process Real Script
    full_text = script_path.read_text(encoding="utf-8").strip()
    sentences = split_into_sentences(full_text)
    
    print(f"🎙️ Processing {len(sentences)} sentences...")
    final_audio_pieces = []
    
    for i, sentence in enumerate(sentences):
        print(f"   [{i+1}/{len(sentences)}] Generating: '{sentence[:30]}...'")
        
        # Retry logic for the FIRST sentence only (Double check)
        # If it's the first sentence, we generate it twice and take the second one
        # to ensure the 'cold start' is completely gone.
        attempts = 2 if i == 0 else 1 
        
        valid_segment = None
        
        for attempt in range(attempts):
            try:
                out = tts.synthesizer.tts_model.inference(
                    text=sentence,
                    language="en",
                    gpt_cond_latent=gpt_cond_latent,
                    speaker_embedding=speaker_embedding,
                    temperature=0.7,        
                    length_penalty=1.0,     
                    repetition_penalty=1.2, 
                    top_k=50,
                    top_p=0.85,
                    speed=SPEED,
                    enable_text_splitting=False
                )
                
                wav_segment = np.array(out["wav"])
                
                # Trim silence
                wav_segment, _ = librosa.effects.trim(wav_segment, top_db=20)
                
                # If valid, keep it
                if len(wav_segment) > 1000:
                    valid_segment = wav_segment
            except Exception as e:
                print(f"   ⚠️ Error: {e}")
                continue
        
        if valid_segment is not None:
            final_audio_pieces.append(valid_segment)
            # Pause
            final_audio_pieces.append(np.zeros(int(24000 * PAUSE_DURATION)))

    if not final_audio_pieces:
        print("❌ Generation failed.")
        return

    print("🧵 Stitching...")
    full_wav = np.concatenate(final_audio_pieces)

    # Normalize
    max_val = np.max(np.abs(full_wav))
    if max_val > 0: full_wav = full_wav / max_val
    full_wav = (full_wav * 32767).astype(np.int16)

    wavfile.write(str(OUTPUT_FILE), 24000, full_wav)
    print(f"✅ Voice Cloned Successfully: {OUTPUT_FILE}")

    # Cleanup
    if Path(clean_ref_path).exists():
        try: os.remove(clean_ref_path)
        except: pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python clone_voice.py <path_to_script.txt>")
        sys.exit(1)
    
    script_arg = Path(sys.argv[1]).resolve()
    if not Path(REFERENCE_AUDIO).exists():
        print(f"❌ Error: {REFERENCE_AUDIO} not found")
        sys.exit(1)
        
    clone_my_voice(script_arg)