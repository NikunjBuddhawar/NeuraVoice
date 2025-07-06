from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import the core LLM agent function and WebSocket route handler
from backend.phiagent2_groq import run_agent
from backend.ws_routes import router as websocket_router

# === FastAPI App Initialization ===
app = FastAPI()

# === CORS Middleware ===
# This allows your frontend (even if it's on a different domain/port) to talk to your backend without getting blocked.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow any domain to make requests
    allow_credentials=True,
    allow_methods=["*"],  # allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # allow all headers (especially important for auth tokens)
)

# === Request Schema for /chat ===
# Used to validate incoming POST body data
class PromptInput(BaseModel):
    prompt: str  # Single string prompt from user

# === REST Endpoint: POST /chat ===
# This is a simple HTTP endpoint to get an LLM response (text in, text out).
@app.post("/chat")
async def chat_response(payload: PromptInput):
    reply = await run_agent(payload.prompt)  # delegate to Groq LLM logic
    return {"response": reply}  # send back a JSON with the response

# === WebSocket Endpoint for Audio/Text Stream ===
# This pulls in your live bi-directional route from ws_routes.py
app.include_router(websocket_router)
