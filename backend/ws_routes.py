# 📁 backend/ws_routes.py

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect
import base64
import os
import tempfile
import asyncio
import json

from backend.phiagent2_groq import run_agent  # LLM interface using Groq
from elevenlabs import generate, set_api_key  # TTS via ElevenLabs
import whisper  # STT via OpenAI Whisper
from dotenv import load_dotenv

# Load environment variables from .env file (e.g., API keys)
load_dotenv()

# Initialize FastAPI router for WebSocket routes
router = APIRouter()

# Set up API keys for ElevenLabs and Groq
set_api_key(os.getenv("ELEVENLABS_API_KEY"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Load Whisper speech-to-text model (base size for speed)
whisper_model = whisper.load_model("base")

# WebSocket route for real-time audio/text interaction
@router.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket connected")

    try:
        while True:
            # Wait for a message from the client (text or audio)
            data = await websocket.receive()

            # === CASE 1: Incoming TEXT input → Return TTS ===
            if "text" in data:
                try:
                    payload = json.loads(data["text"])

                    # Only handle type: "text" messages
                    if payload.get("type") == "text":
                        user_input = payload["payload"]
                        print("[📝 User Text]:", user_input)

                        # Get LLM response from Groq API
                        reply_text = await run_agent(user_input)
                        print("[🤖 AI Reply]:", reply_text)

                        # Generate speech from the reply using ElevenLabs
                        audio_output = generate(
                            text=reply_text,
                            voice="Sarah",
                            model="eleven_monolingual_v1"
                        )

                        # Send audio bytes back to client
                        await websocket.send_bytes(b"".join(audio_output))

                except Exception as e:
                    print("[⚠️ Text Handling Error]:", e)
                    await websocket.send_text("Error handling text message.")

            # === CASE 2: Incoming AUDIO input → Transcribe → Get Reply → Return TTS ===
            elif "bytes" in data:
                try:
                    audio_data = data["bytes"]
                    print(f"[🎤 Audio Received] Bytes: {len(audio_data)}")

                    # Save raw audio to a temporary WAV file for Whisper to read
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp.write(audio_data)
                        tmp_path = tmp.name

                    # Use Whisper to transcribe audio
                    result = whisper_model.transcribe(tmp_path)
                    os.remove(tmp_path)  # Clean up the temp file

                    user_input = result["text"]
                    print("[🧠 Transcribed Text]:", user_input)

                    # If nothing could be understood
                    if not user_input.strip():
                        await websocket.send_text("❌ Could not understand audio.")
                        continue

                    # Get response from LLM
                    reply_text = await run_agent(user_input)
                    print("[🤖 AI Reply]:", reply_text)

                    # Convert AI response into speech using ElevenLabs
                    audio_output = generate(
                        text=reply_text,
                        voice="Sarah",
                        model="eleven_monolingual_v1"
                    )

                    # Send the synthesized audio to the frontend
                    await websocket.send_bytes(b"".join(audio_output))

                except Exception as e:
                    print("[⚠️ Audio Processing Error]:", e)
                    await websocket.send_text("Error processing audio input.")

    # Handle client disconnects cleanly
    except WebSocketDisconnect:
        print("🚪 WebSocket disconnected")

    # Catch unexpected server-side errors
    except Exception as e:
        print("[❌ Unexpected Error]:", e)
        try:
            await websocket.send_text("Server error occurred.")
        except:
            pass

    # Final cleanup (log that connection closed)
    finally:
        print("🛑 WebSocket connection closed")
