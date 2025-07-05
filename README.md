# 🔊 NeuraVoice – Real-Time Voice Assistant (WIP)

> A full-stack AI voice assistant platform for **real-time audio/text interaction**, powered by **Groq + LLaMA3**, **Whisper STT**, and **ElevenLabs TTS**, with dynamic WebSocket communication and a multimodal UI.

---

## 🛍️ Problem Statement

While LLM chat interfaces are common, real-time **voice-based agents** are rare, especially those that:

- Handle both **audio and text input**
- Offer **audio or text output**, user-configurable
- Work over **WebSockets for low latency**
- Offer a clean UI + backend structure

Most assistants either:
- Are locked behind closed APIs,
- Or lack proper integration between voice and reasoning models.

---

## ✅ Our Solution

We built **NeuraVoice** — a real-time, audio-optional assistant that features:

- 🎧 **Voice input** via browser microphone
- 🔊 **Audio or text responses** (configurable)
- 🧠 Powered by **Groq LLaMA3**, **Whisper**, and **ElevenLabs**
- ✨ **Interactive React frontend** with chat UI
- ⏳ Uses **WebSockets** for low-latency real-time flow

Built with modularity in mind, this can be the base for agentic AI systems.

---

## 🚀 Features

| Component     | Description                                                                 |
|---------------|-----------------------------------------------------------------------------|
| 📻 Audio Chat   | Press mic button to record 5s audio; transcribed and processed in real-time |
| 💬 Text Chat    | Type text and receive replies like a traditional chat app         |
| 🔄 Dual Modes   | Choose whether AI replies in text or audio                         |
| 🔍 STT + TTS    | Combines Whisper (STT) and ElevenLabs (TTS)                        |
| ✨ Fast Response | Uses WebSocket for instant audio/text streaming                        |
| 🌐 Deploy-ready | Easy to host, configure, and personalize                          |

---

## 🛠️ Tech Stack

- **Frontend**: React (JSX), HTML5 Audio APIs
- **Backend**: FastAPI, WebSockets
- **LLM**: Groq API (LLaMA3-8B)
- **TTS**: ElevenLabs
- **STT**: OpenAI Whisper
- **Other**: dotenv, tempfile, asyncio, base64, BytesIO

---

## 📁 Folder Structure

```bash
.
├── backend/
│   ├── main.py               # FastAPI entry
│   ├── ws_routes.py          # WebSocket endpoint for audio/text
│   ├── phiagent2_groq.py     # Calls Groq API
│   ├── list_voices.py        # Optional helper for ElevenLabs voices
│   └── requirements.txt      # Python dependencies
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── AudioRecorder.jsx # React component for mic/text input
│       ├── AudioRecorder.css # Styling
│       ├── App.js, index.js  # App entrypoints
│       └── ...
│
├── .env                      # API keys
├── README.md
└── venv/                     # Virtual env (ignored)

```

## 🛠️ Setup Instructions

Follow these steps to run the app locally:

## 1. Clone the Repo

```
bash
git clone https://github.com/NikunjBuddhawar/NeuraVoice
cd neura-voice
```


## 2. Backend Setup (Python)

```
bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Add the .env file

```
ELEVENLABS_API_KEY=your-elevenlabs-key
GROQ_API_KEY=your-groq-key
```

## 4. Run the FastAPI server

```
bash
uvicorn main:app --reload
```

## 5. Frontend Setup (React)

```
bash
cd frontend
npm install
npm start
```
## 🔄 Workflow Diagram

```mermaid
graph TD
    A[User Speaks or Types] --> B[Frontend (React)]
    B --> C[WebSocket /ws/audio]
    C --> D[FastAPI Backend]
    D -->|Audio| E[Whisper Transcription]
    D -->|Text| F[Groq LLM]
    E --> F
    F -->|Response| G[ElevenLabs TTS or Text]
    G --> H[Send Response Back via WebSocket]
    H --> I[Frontend Renders in Chat]
```