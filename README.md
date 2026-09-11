# F.R.I.D.A.Y. Core Command Center v3.0

An advanced, interactive Windows PC automation and voice assistant system inspired by Iron Man's F.R.I.D.A.Y. This project combines a Flask-powered web engine, a 3D reactive hologram interface (Three.js), multi-model AI integration (Groq Llama 3 & Gemini API), voice synthesis (Deepgram API), offline local LLM fallbacks (Hugging Face Transformers), and MediaPipe computer vision for real-time gesture control.

> ⚠️ **DEVELOPMENT BUILD & SERVER WARNING**  
> This application runs locally on a private Flask development server (`127.0.0.1:5000`). It is actively being refactored, contains experimental OS controls, and is missing production security protocols. **DO NOT** deploy this directly to public servers or store unencrypted API keys in public repositories. Use strictly at your own risk.

---

## 🚀 Key Features

### 🧠 Intelligent Hybrid AI Core
* **High-Speed Groq Engine:** Primary text generation powered by Groq using `llama-3.3-70b-versatile` for ultra-low latency response times.
* **Gemini Intent Parsing:** Parses user prompts to differentiate between OS automation commands, media controls, and conversational chat.
* **Offline Local LLM Backup:** Integrates PyTorch and Hugging Face Transformers (`test_brain.py`) to process basic reasoning offline without active cloud access.
* **Deepgram Text-to-Speech:** Asynchronous voice synthesis processed via `pygame.mixer` to keep the execution loop lag-free.

### 💻 Windows PC Automation & Control
* **Media & Volume Control:** Granular system master volume adjustments and isolated application volume control (Spotify, Chrome, VS Code) using `pycaw`.
* **Application Ecosystem:** Instantly launch, monitor, or force-terminate applications (`taskkill`) including custom Web URL shortcuts and automated YouTube search queries.
* **System Telemetry & Operations:** Workstation locking, scheduled shutdowns, screenshot capture, and real-time CPU, RAM, and network telemetry polling.

### 🎥 Futuristic 3D UI & Gesture Recognition
* **3D Reactive Hologram:** Interactive Three.js particle sphere and ring matrix with bloom post-processing, audio-reactive pulses, and status-based visual shifts.
* **MediaPipe Hand Tracking:** Real-time webcam tracking for 3D navigation. Use pinch gestures to translate/pan the viewport, or open hands to scale, zoom, and rotate the visual core.
* **Dual-Wave Equalizer:** A canvas-based interactive waveform visualizer displaying live execution states and voice response audio.

---

## 🛠️ Tech Stack

* **Backend Framework:** Python 3.10–3.14, Flask, Asyncio, Threading, PyWebView
* **AI & Machine Learning:** Groq SDK, Google GenAI SDK (`gemini-2.5-flash`), Deepgram Aura TTS API, PyTorch, Hugging Face `transformers`, `accelerate`
* **OS & Hardware Integration:** `pycaw`, `comtypes`, `pyautogui`, `psutil`, `pygame-ce` (Audio & Surface Pipeline)
* **Frontend Design:** WebGL, Three.js, OrbitControls, UnrealBloomPass, HTML5, Modern CSS, JavaScript (ES6)
* **Computer Vision:** MediaPipe Hands API, OpenCV / Webcam Interface

---

## 🛠️ Installation & Setup

### 1. Prerequisites
* **Operating System:** Windows 10 or 11 (Required for `pycaw` audio and PyAutoGUI controls)
* **Python Version:** Python 3.10 – 3.14

### 2. Clone Repository
```cmd
git clone [https://github.com/YOUR_USERNAME/friday-command-center.git](https://github.com/YOUR_USERNAME/friday-command-center.git)
cd friday-command-center
