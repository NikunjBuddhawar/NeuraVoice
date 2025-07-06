import React, { useState, useRef, useEffect } from "react";
import "./AudioRecorder.css";

// Main Component
export default function AudioRecorder() {
  // UI State
  const [recording, setRecording] = useState(false); // Tracks if user is recording audio
  const [chat, setChat] = useState([]); // Holds all chat messages (text or audio)
  const [inputText, setInputText] = useState(""); // Text input field value
  const [aiResponseMode, setAiResponseMode] = useState("text"); // "text" or "audio" response from AI

  // Refs
  const mediaRecorder = useRef(null); // MediaRecorder instance for audio capture
  const ws = useRef(null); // WebSocket connection reference
  const nextIsAudio = useRef(false); // Flag to expect incoming binary audio blob

  // Function to start or stop voice recording
  const startRecording = async () => {
    if (recording) {
      // Stop if already recording
      mediaRecorder.current?.stop();
      setRecording(false);
      return;
    }

    try {
      // Get microphone input stream
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorder.current = recorder;

      const audioChunks = []; // Buffer to hold recorded audio chunks

      // Open WebSocket connection
      ws.current = new WebSocket("ws://localhost:8000/ws/audio");

      // On WS connection open, send selected response mode
      ws.current.onopen = () => {
        ws.current.send(JSON.stringify({ type: "mode", payload: aiResponseMode }));
      };

      // Handle incoming WebSocket messages (AI replies)
      ws.current.onmessage = async (event) => {
        // Server indicates next message is audio
        if (typeof event.data === "string" && event.data === "__AUDIO__") {
          nextIsAudio.current = true;
          return;
        }

        // If next message is binary audio blob
        if (event.data instanceof Blob && nextIsAudio.current) {
          const blob = new Blob([event.data], { type: "audio/mpeg" });
          const audioUrl = URL.createObjectURL(blob);
          setChat((prev) => [...prev, { sender: "ai", audioUrl }]);
          nextIsAudio.current = false;
          return;
        }

        // Otherwise treat it as plain text message
        if (typeof event.data === "string") {
          setChat((prev) => [...prev, { sender: "ai", text: event.data }]);
        }
      };

      // Capture audio chunks while recording
      recorder.ondataavailable = (e) => {
        audioChunks.push(e.data);
      };

      // On recording stop, send audio to backend and store locally
      recorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: "audio/wav" });
        ws.current.send(blob); // Send audio to backend
        const userAudioUrl = URL.createObjectURL(blob);
        setChat((prev) => [...prev, { sender: "user", audioUrl: userAudioUrl }]);
      };

      recorder.start();
      setRecording(true); // Update UI state
    } catch (err) {
      console.error("Failed to start recording:", err);
    }
  };

  // Function to send text input to the AI backend
  const sendTextMessage = () => {
    if (!inputText.trim()) return;

    setChat((prev) => [...prev, { sender: "user", text: inputText }]);
    const prompt = inputText;
    setInputText(""); // Clear input box

    // Open a new WebSocket connection
    ws.current = new WebSocket("ws://localhost:8000/ws/audio");

    ws.current.onopen = () => {
      ws.current.send(JSON.stringify({ type: "mode", payload: aiResponseMode }));
      ws.current.send(JSON.stringify({ type: "text", payload: prompt }));
    };

    // Handle AI's reply (text or audio)
    ws.current.onmessage = async (event) => {
      if (typeof event.data === "string" && event.data === "__AUDIO__") {
        nextIsAudio.current = true;
        return;
      }

      if (event.data instanceof Blob && nextIsAudio.current) {
        const blob = new Blob([event.data], { type: "audio/mpeg" });
        const audioUrl = URL.createObjectURL(blob);
        setChat((prev) => [...prev, { sender: "ai", audioUrl }]);
        nextIsAudio.current = false;
        return;
      }

      if (typeof event.data === "string") {
        setChat((prev) => [...prev, { sender: "ai", text: event.data }]);
      }
    };
  };

  // Auto-scroll chat box to bottom when chat updates
  useEffect(() => {
    const chatArea = document.querySelector(".chat-box");
    if (chatArea) chatArea.scrollTop = chatArea.scrollHeight;
  }, [chat]);

  // Component UI
  return (
    <div className="app-container">
      {/* Header */}
      <nav className="navbar">
        <span className="navbar-title">NeuraVoice 🔊</span>
      </nav>

      {/* Main Chat + Input Area */}
      <div className="main-content">
        {/* Chat Display */}
        <div className="chat-box">
          {chat.map((msg, idx) => (
            <div
              key={idx}
              className={`chat-bubble ${msg.sender === "user" ? "user" : "ai"}`}
            >
              {/* Audio or Text output */}
              {msg.audioUrl ? (
                <audio controls src={msg.audioUrl}></audio>
              ) : typeof msg.text === "string" ? (
                <span>{msg.text}</span>
              ) : (
                <span>[Invalid response]</span>
              )}
            </div>
          ))}
        </div>

        {/* Input Controls */}
        <div className="input-area">
          {/* Text Input */}
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your message..."
            className="text-input"
          />

          {/* Buttons */}
          <button onClick={sendTextMessage} className="record-button">
            Send
          </button>

          <button onClick={startRecording} className="record-button">
            {recording ? "Stop Talking" : "Start Talking"}
          </button>

          {/* Response Mode Selector */}
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
