// AudioRecorder.jsx
import React, { useState, useRef, useEffect } from "react";
import "./AudioRecorder.css";

export default function AudioRecorder() {
  // State hooks to manage recording, chat messages, input text, and AI reply mode
  const [recording, setRecording] = useState(false);
  const [chat, setChat] = useState([]); // Stores messages: { sender: 'user' | 'ai', text?, audioUrl? }
  const [inputText, setInputText] = useState("");
  const [aiResponseMode, setAiResponseMode] = useState("text"); // 'text' or 'audio'

  const mediaRecorder = useRef(null); // Holds MediaRecorder instance
  const ws = useRef(null);            // Holds WebSocket instance

  // Function to start audio recording and open WebSocket connection
  const startRecording = async () => {
    // Ask for microphone permission and start audio stream
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    mediaRecorder.current = recorder;

    // Connect to the FastAPI WebSocket backend
    ws.current = new WebSocket("ws://localhost:8000/ws/audio");

    const audioChunks = [];

    // Collect audio data chunks while recording
    recorder.ondataavailable = (e) => {
      audioChunks.push(e.data);
    };

    // When recording stops: convert audio to base64 and send over WebSocket
    recorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: "audio/wav" });
      const reader = new FileReader();

      reader.readAsDataURL(blob);
      reader.onloadend = () => {
        const base64 = reader.result;

        // Send base64 audio to server
        ws.current.send(base64);

        // Also tell server how we want the AI to respond (text or audio)
        ws.current.send(
          JSON.stringify({ type: "mode", payload: aiResponseMode })
        );

        // Add user's recorded audio to chat UI
        const userAudioUrl = URL.createObjectURL(blob);
        setChat((prev) => [...prev, { sender: "user", audioUrl: userAudioUrl }]);
      };
    };

    recorder.start();
    setRecording(true);

    // Handle incoming responses from the AI
    ws.current.onmessage = (event) => {
      try {
        const data = event.data;

        // If it's a text response
        if (typeof data === "string") {
          setChat((prev) => [...prev, { sender: "ai", text: data }]);
        } else {
          // Otherwise it's audio (binary blob)
          const audioBlob = new Blob([data], { type: "audio/mpeg" });
          const audioUrl = URL.createObjectURL(audioBlob);
          setChat((prev) => [...prev, { sender: "ai", audioUrl }]);
        }
      } catch (e) {
        console.error("onmessage error:", e);
      }
    };

    // Stop recording after 5 seconds (auto cutoff)
    setTimeout(() => {
      recorder.stop();
      setRecording(false);
    }, 5000);
  };

  // Function to send a typed message to the server
  const sendTextMessage = async () => {
    if (!inputText.trim()) return;

    // Display user message in chat immediately
    setChat((prev) => [...prev, { sender: "user", text: inputText }]);
    const prompt = inputText;
    setInputText("");

    // Connect to WebSocket and send the typed prompt
    ws.current = new WebSocket("ws://localhost:8000/ws/audio");

    // Handle text or audio mode
    if (aiResponseMode === "text") {
      ws.current.onopen = () => {
        ws.current.send(JSON.stringify({ type: "text", payload: prompt }));
      };
      ws.current.onmessage = (event) => {
        const response = event.data;
        setChat((prev) => [...prev, { sender: "ai", text: response }]);
      };
    } else {
      // For audio responses, also send mode info
      ws.current.onopen = () => {
        ws.current.send(JSON.stringify({ type: "text", payload: prompt }));
        ws.current.send(
          JSON.stringify({ type: "mode", payload: aiResponseMode })
        );
      };
      ws.current.onmessage = (event) => {
        const audioBlob = new Blob([event.data], { type: "audio/mpeg" });
        const audioUrl = URL.createObjectURL(audioBlob);
        setChat((prev) => [...prev, { sender: "ai", audioUrl }]);
      };
    }
  };

  // Auto-scroll chat to bottom when new messages arrive
  useEffect(() => {
    const chatArea = document.querySelector(".chat-box");
    if (chatArea) chatArea.scrollTop = chatArea.scrollHeight;
  }, [chat]);

  return (
    <div className="app-container">
      <nav className="navbar">
        <span className="navbar-title">NeuraVoice 🔊</span>
      </nav>

      <div className="main-content">
        <div className="chat-box">
          {chat.map((msg, idx) => (
            <div
              key={idx}
              className={`chat-bubble ${msg.sender === "user" ? "user" : "ai"}`}
            >
              {/* Show audio if audioUrl exists, else show plain text */}
              {msg.audioUrl ? (
                <audio controls src={msg.audioUrl}></audio>
              ) : (
                <span>{msg.text}</span>
              )}
            </div>
          ))}
        </div>

        <div className="input-area">
          {/* Text input for manual messages */}
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your message..."
            className="text-input"
          />

          {/* Button to send typed message */}
          <button onClick={sendTextMessage} className="record-button">
            Send
          </button>

          {/* Button to start voice recording */}
          <button onClick={startRecording} disabled={recording} className="record-button">
            {recording ? "Listening..." : "Start Talking"}
          </button>

          {/* Dropdown to toggle AI response mode */}
          <select
            className="mode-toggle"
            value={aiResponseMode}
            onChange={(e) => setAiResponseMode(e.target.value)}
          >
            <option value="text">AI responds with Text</option>
            <option value="audio">AI responds with Audio</option>
          </select>
        </div>
      </div>
    </div>
  );
}
