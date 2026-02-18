# FILE: python_server/ai_engine/voice.py

import os
import time
from groq import Groq


def transcribe_audio_engine(file_bytes, filename="voice.webm", api_key=None):
    """
    Transcribes audio using Whisper on Groq.
    Includes DEBUG prints to trace errors.
    """
    print(f"\n🎤 [VOICE DEBUG] Starting Transcription...")

    # 1. Validate Key
    if not api_key:
        print("❌ [VOICE DEBUG] Error: API Key is MISSING (None).")
        return {"error": "Groq API Key missing in configuration."}

    print(f"   [VOICE DEBUG] API Key found (Length: {len(api_key)})")

    # 2. Validate File
    file_size = len(file_bytes)
    print(f"   [VOICE DEBUG] Audio File Size: {file_size} bytes")

    if file_size == 0:
        print("❌ [VOICE DEBUG] Error: Audio file is empty.")
        return {"error": "Audio file is empty. Check microphone permissions."}

    client = Groq(api_key=api_key)

    # Use a unique temp name to prevent collisions
    temp_filename = f"temp_{int(time.time())}_{filename}"

    try:
        # 3. Write Temp File
        with open(temp_filename, "wb") as buffer:
            buffer.write(file_bytes)
        print(f"   [VOICE DEBUG] Temp file written: {temp_filename}")

        # 4. Send to Groq
        print(f"   [VOICE DEBUG] Sending to Groq Whisper...")
        with open(temp_filename, "rb") as f:
            t = client.audio.transcriptions.create(
                file=(temp_filename, f.read()),
                model="whisper-large-v3",
                prompt="User asking about grocery inventory, sales, churn, and customers.",
                response_format="json",
            )

        clean_text = t.text.strip()
        print(f"✅ [VOICE DEBUG] Success! Transcript: '{clean_text}'")

        # Filter Hallucinations
        if clean_text.lower() in ["you", "thank you", "mbc", "subtitles by", ""]:
            return {"text": ""}

        return {"text": clean_text}

    except Exception as e:
        print(f"❌ [VOICE DEBUG] CRITICAL ERROR: {str(e)}")
        return {"error": str(e)}
    finally:
        # Cleanup
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
                print("   [VOICE DEBUG] Temp file cleaned up.")
            except:
                print("⚠️ [VOICE DEBUG] Could not delete temp file (File locked?)")
