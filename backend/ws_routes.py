from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect
import os
import tempfile
import json
from io import BytesIO
import uuid

from backend.phiagent2_groq import run_agent  # Your core logic handler (email/calendar)
from elevenlabs import generate, set_api_key
import whisper
from dotenv import load_dotenv

import chromadb
from sentence_transformers import SentenceTransformer

# === Load environment variables from .env ===
load_dotenv()

# === Setup FastAPI WebSocket router ===
router = APIRouter()

# === ElevenLabs + Whisper setup ===
set_api_key(os.getenv("ELEVENLABS_API_KEY"))
whisper_model = whisper.load_model("base")

# === ChromaDB Memory Store ===
client = chromadb.Client()
collection = client.get_or_create_collection("neura_memory")
embedder = SentenceTransformer("all-MiniLM-L6-v2")  # Lightweight and fast sentence encoder


@router.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket connected")

    response_mode = "audio"  # Default to audio response unless changed

    try:
        while True:
            # Wait for either text or binary (audio) message from frontend
            data = await websocket.receive()
            text_data = data.get("text", None)
            binary_data = data.get("bytes", None)

            # === Handle TEXT input ===
            if text_data is not None:
                try:
                    payload = json.loads(text_data)

                    if payload.get("type") == "mode":
                        # Switch between 'text' and 'audio' output mode
                        response_mode = payload["payload"]
                        print(f"[📍 Mode Switched]: {response_mode}")

                    elif payload.get("type") == "text":
                        user_input = payload["payload"]
                        print("[📝 User Text]:", user_input)

                        # === Step 1: Retrieve related past memory from Chroma ===
                        embedding = embedder.encode([user_input])[0]
                        try:
                            results = collection.query(query_embeddings=[embedding], n_results=3)
                            past_context = "\n".join(results["documents"][0])
                        except Exception as e:
                            print("[⚠️ Chroma Retrieval Error]:", e)
                            past_context = ""

                        # Combine retrieved memory with user input
                        full_input = f"Prior context:\n{past_context}\n\nUser: {user_input}" if past_context else user_input

                        # === Step 2: Get reply from LLM agent ===
                        reply_text = await run_agent(full_input)
                        print("[🤖 AI Reply]:", reply_text)

                        # === Step 3: Store the new interaction in memory ===
                        try:
                            combined = f"User: {user_input}\nAI: {reply_text}"
                            memory_id = str(uuid.uuid4())
                            memory_embedding = embedder.encode([combined])[0]
                            collection.add(documents=[combined], embeddings=[memory_embedding], ids=[memory_id])
                        except Exception as e:
                            print("[⚠️ Chroma Store Error]:", e)

                        # === Step 4: Send reply (text or audio) ===
                        if response_mode == "text":
                            await websocket.send_text(reply_text)
                        else:
                            audio_output = generate(
                                text=reply_text,
                                voice="Sarah",
                                model="eleven_monolingual_v1"
                            )

                            # Convert audio generator into bytes
                            audio_bytes = BytesIO()
                            for chunk in audio_output:
                                if isinstance(chunk, bytes):
                                    audio_bytes.write(chunk)
                                elif isinstance(chunk, int):
                                    audio_bytes.write(bytes([chunk]))

                            await websocket.send_text("__AUDIO__")  # Signal to frontend
                            await websocket.send_bytes(audio_bytes.getvalue())

                except Exception as e:
                    print("[⚠️ Text Handling Error]:", e)
                    await websocket.send_text("Error handling text message.")

            # === Handle AUDIO input ===
            elif binary_data is not None:
                try:
                    print(f"[🎤 Audio Received] Bytes: {len(binary_data)}")

                    # Save incoming audio to a temporary WAV file
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp.write(binary_data)
                        tmp_path = tmp.name

                    print("[DEBUG] Temp file size:", os.path.getsize(tmp_path))

                    # Transcribe using Whisper
                    try:
                        result = whisper_model.transcribe(tmp_path)
                    except Exception as e:
                        print("[Whisper Transcription Error]:", e)
                        os.remove(tmp_path)
                        await websocket.send_text("❌ Whisper failed to transcribe audio.")
                        continue

                    os.remove(tmp_path)  # Clean up temp file

                    user_input = result["text"]
                    print("[🧠 Transcribed]:", user_input)

                    if not user_input.strip():
                        await websocket.send_text("❌ Could not understand audio.")
                        continue

                    # === Step 1: Retrieve relevant memory from Chroma ===
                    embedding = embedder.encode([user_input])[0]
                    try:
                        results = collection.query(query_embeddings=[embedding], n_results=3)
                        past_context = "\n".join(results["documents"][0])
                    except Exception as e:
                        print("[⚠️ Chroma Retrieval Error]:", e)
                        past_context = ""

                    full_input = f"Prior context:\n{past_context}\n\nUser: {user_input}" if past_context else user_input

                    # === Step 2: Get AI reply from agent ===
                    reply_text = await run_agent(full_input)
                    print("[🤖 AI Reply]:", reply_text)

                    # === Step 3: Store memory ===
                    try:
                        combined = f"User: {user_input}\nAI: {reply_text}"
                        memory_id = str(uuid.uuid4())
                        memory_embedding = embedder.encode([combined])[0]
                        collection.add(documents=[combined], embeddings=[memory_embedding], ids=[memory_id])
                    except Exception as e:
                        print("[⚠️ Chroma Store Error]:", e)

                    # === Step 4: Reply in requested format ===
                    if response_mode == "text":
                        await websocket.send_text(reply_text)
                    else:
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

                        await websocket.send_text("__AUDIO__")
                        await websocket.send_bytes(audio_bytes.getvalue())

                except Exception as e:
                    print("[⚠️ Audio Processing Error]:", e)
                    await websocket.send_text("Error processing audio input.")

            else:
                print("[⚠️ Unexpected WebSocket message format]:", data)

    # Handle WebSocket disconnects gracefully
    except WebSocketDisconnect:
        print("🚪 WebSocket disconnected")

    # Catch unexpected server-side exceptions
    except Exception as e:
        print("[❌ Unexpected Server Error]:", e)
        try:
            await websocket.send_text("Internal server error.")
        except:
            pass

    finally:
        print("🛑 WebSocket connection closed")
