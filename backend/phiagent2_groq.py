from fastapi import APIRouter, WebSocket
import base64
import os
import tempfile
import asyncio
from io import BytesIO
from dotenv import load_dotenv
from elevenlabs import generate, set_api_key
import whisper
import requests
import json
from starlette.websockets import WebSocketDisconnect

# Load environment variables from the .env file
load_dotenv()

# Initialize the FastAPI router
router = APIRouter()

# Load the Whisper model (smallest version for faster inference)
whisper_model = whisper.load_model("base")

# Set ElevenLabs API key for text-to-speech
set_api_key(os.getenv("ELEVENLABS_API_KEY"))

# Get Groq API key for LLM responses
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Function to send user input to the Groq LLaMA3 API and return a response
async def run_agent(user_input: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": "You are a helpful, concise voice assistant."},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0.7,
        "max_tokens": 200
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print("[Groq API Error]:", e)
        return "Sorry, I'm having trouble responding right now."

# WebSocket endpoint to handle real-time voice assistant communication
@router.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("INFO: WebSocket connected")

    # Default mode is audio response (can be switched to text)
    response_mode = "audio"

    try:
        while True:
            try:
                # Wait for incoming message from frontend
                raw = await websocket.receive_text()

                # Check if it's a JSON-formatted control message (e.g. text prompt or mode switch)
                if raw.strip().startswith("{"):
                    parsed = json.loads(raw)

                    # Handle plain text message
                    if parsed["type"] == "text":
                        user_input = parsed["payload"]
                        print("[📝 Text Prompt]:", user_input)

                        # Generate a reply from the LLM
                        reply_text = await run_agent(user_input)

                        if response_mode == "text":
                            # Send back plain text response
                            await websocket.send_text(reply_text)
                        else:
                            # Convert reply to audio and stream back
                            print("[🤖 AI Reply for TTS]:", reply_text)
                            audio_output = generate(
                                text=reply_text,
                                voice="Sarah",
                                model="eleven_monolingual_v1"
                            )

                            # Accumulate audio bytes
                            audio_bytes = BytesIO()
                            for chunk in audio_output:
                                if isinstance(chunk, bytes):
                                    audio_bytes.write(chunk)
                                elif isinstance(chunk, int):  # sometimes chunk may be int
                                    audio_bytes.write(bytes([chunk]))

                            # Send audio over the WebSocket
                            await websocket.send_bytes(audio_bytes.getvalue())

                    # Handle a mode switch (text <-> audio)
                    elif parsed["type"] == "mode":
                        response_mode = parsed["payload"]
                        print(f"[📍 AI Response Mode]: {response_mode}")
                    continue

                # If it's not JSON, treat it as base64-encoded audio input
                audio_data = base64.b64decode(raw.split(",")[1])
                print("[🎤 Audio Received] Size:", len(audio_data))

                # Save audio temporarily to disk for Whisper
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(audio_data)
                    tmp_path = tmp.name

                # Transcribe speech to text using Whisper
                result = whisper_model.transcribe(tmp_path)
                os.remove(tmp_path)  # Clean up the temp file

                user_input = result["text"]
                print("[🗣️ Transcribed]:", user_input)

                if not user_input.strip():
                    # Whisper couldn't understand anything
                    await websocket.send_text("❗Could not understand audio.")
                    continue

                # Generate reply using LLM
                reply_text = await run_agent(user_input)
                print("[🤖 AI Reply]:", reply_text)

                if response_mode == "text":
                    await websocket.send_text(reply_text)
                else:
                    # Generate TTS audio from response
                    audio_output = generate(
                        text=reply_text,
                        voice="Sarah",
                        model="eleven_monolingual_v1"
                    )

                    audio_bytes = BytesIO()
                    for chunk in audio_output:
                        if isinstance(chunk, bytes):
                            audio_bytes.write(chunk)
                        elif isinstance(chunk, int):
                            audio_bytes.write(bytes([chunk]))

                    await websocket.send_bytes(audio_bytes.getvalue())

            except WebSocketDisconnect:
                print("❌ WebSocket disconnected")
                break
            except Exception as e:
                print("[WebSocket Error]:", e)
                break

    finally:
        print("INFO: WebSocket fully disconnected")
