from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import the WebSocket router and LLM response function from backend
from backend.phiagent2_groq import router as websocket_router, run_agent

# Initialize the FastAPI app
app = FastAPI()

# Enable CORS (Cross-Origin Resource Sharing) for all origins and methods
# This allows the frontend to communicate with the backend without restrictions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # Allow requests from any domain (dev-friendly; lock down in prod)
    allow_credentials=True,
    allow_methods=["*"],            # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],            # Allow all request headers
)

# Define the schema for POST /chat endpoint using Pydantic
class PromptInput(BaseModel):
    prompt: str  # User's message text

# REST endpoint for simple text-based interaction
@app.post("/chat")
async def chat_response(payload: PromptInput):
    # Pass the user prompt to the LLM and return the reply
    reply = await run_agent(payload.prompt)
    return {"response": reply}

# Include the WebSocket-based audio/text interaction routes
app.include_router(websocket_router)
