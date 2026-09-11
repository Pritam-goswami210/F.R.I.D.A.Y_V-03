import os
import re
import logging
import asyncio
import urllib.parse
import urllib.request
import threading
import json
import time
import psutil
import requests
import io
import pygame
import pyautogui
from PIL import Image
from flask import Flask, render_template_string, request, jsonify
import webview

# Groq Import
from groq import AsyncGroq

# Windows COM & Audio Control Imports
import comtypes
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume

# Initialize Pygame Audio Mixer
pygame.mixer.init()

WEB_PASSWORD = "friday"  # System Dashboard Password

# Deepgram TTS Configuration
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "YOUR_DEEPGRAM_API_KEY_HERE")
DEEPGRAM_VOICE_MODEL = "aura-asteria-en"

def speak_text(text: str):
    """Generates audio via Deepgram Aura TTS API and plays it asynchronously using pygame."""
    if not DEEPGRAM_API_KEY:
        print("Deepgram API Key is missing. Audio playback skipped.")
        return

    def _play():
        try:
            url = f"https://api.deepgram.com/v1/speak?model={DEEPGRAM_VOICE_MODEL}"
            headers = {
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "text": text
            }
            
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                audio_stream = io.BytesIO(response.content)
                pygame.mixer.music.load(audio_stream)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
            else:
                print(f"Deepgram Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Voice output error: {e}")

    threading.Thread(target=_play, daemon=True).start()


# Groq API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
client = AsyncGroq(api_key=GROQ_API_KEY)
MODEL_NAME = "llama-3.3-70b-versatile"

# System Prompt
def build_friday_prompt() -> str:
    """Dynamically builds the F.R.I.D.A.Y system prompt including live telemetry and health evaluation."""
    update_system_stats()
    cpu = system_state["cpu"]
    ram = system_state["ram"]
    
    # Assess overall system health based on performance telemetry
    if cpu > 85 or ram > 90:
        perf_status = f"CRITICAL HEAVY LOAD (CPU: {cpu}%, RAM: {ram}%)"
    elif cpu > 70 or ram > 75:
        perf_status = f"MODERATE ELEVATION (CPU: {cpu}%, RAM: {ram}%)"
    else:
        perf_status = f"NOMINAL (CPU: {cpu}%, RAM: {ram}%)"

    return f"""You are F.R.I.D.A.Y. (Female Replaceable Intelligent Digital Assistant Youth), an advanced AI system for Windows PC control and management. You operate through a standalone desktop interface.

# Current Real-Time System Telemetry
- CPU Usage: {cpu}%
- RAM Usage: {ram}%
- Health Status Evaluation: {perf_status}

# Core Responsibilities
- Execute system commands and manage Windows applications accurately
- Provide real-time system monitoring and health reporting
- Interface with the command center dashboard for visual feedback

# Personality & Tone
- Professional, helpful, concise, and calm under pressure
- Slightly witty, but always polite and efficient

# Operational & System Guidelines
- Always report system health based strictly on the current real-time telemetry provided above.
- NEVER claim "operating at peak efficiency" or "all systems nominal" if the Health Status Evaluation indicates elevated or critical load.
- If system load is critical (CPU > 85% or RAM > 90%), explicitly alert the user to potential performance degradation in your reply.

# Response Output Format
You MUST respond EXCLUSIVELY with a valid JSON object. Do not include markdown block formatting (such as ```json) or conversational preamble before or after the JSON structure.

JSON Schema:
{{
  "action": "app_launch" | "chat" | "system_command",
  "app_name": "<name of application if action is app_launch, otherwise null>",
  "reply": "<spoken response text for user, accurately reflecting system state>"
}}
"""

async def get_friday_response(user_message: str) -> str:
    """Queries the Groq API with dynamically refreshed system telemetry context."""
    try:
        prompt = build_friday_prompt()
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return content if content else '{"action": "chat", "app_name": null, "reply": "I am processing that request."}'
    except Exception as e:
        print(f"Groq error: {e}")
        return json.dumps({
            "action": "chat",
            "app_name": None,
            "reply": f"Apologies, I encountered an error communicating with core services: {str(e)}"
        })

# Flask web app
web_app = Flask(__name__)

# Global state for dashboard
system_state = {
    "cpu": 0,
    "ram": 0,
    "network": "Online",
    "tasks": 0,
    "memory": "0 GB",
    "last_command": "Ready for command...",
    "command_history": [],
    "status": "OPERATIONAL",
    "hand_tracking": {
        "active": False,
        "landmarks": [],
        "orb_engaged": False
    }
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.WARNING
)

# Application registry & process mappings
BUILTIN_APPS = {
    "calculator": "calc",
    "calculater": "calc",
    "calc": "calc",
    "notepad": "notepad",
    "cmd": "start cmd",
    "terminal": "start wt",
    "camera": "start microsoft.windows.camera:",
    "spotify": "start spotify:",
    "chrome": "start chrome",
    "vscode": "code",
    "vs code": "code",
    "writer": "start soffice --writer",
    "impress": "start soffice --impress"
}

PROCESS_MAP = {
    "terminal": "WindowsTerminal.exe",
    "wt": "WindowsTerminal.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "vscode": "code.exe",
    "vs code": "code.exe",
    "code": "code.exe",
    "notepad": "notepad.exe",
    "writer": "soffice.bin",
    "impress": "soffice.bin",
    "libreoffice": "soffice.bin",
    "spotify": "Spotify.exe",
    "chrome": "chrome.exe",
    "brave": "brave.exe",
    "calculator": "CalculatorApp.exe",
    "calculater": "CalculatorApp.exe",
    "calc": "CalculatorApp.exe",
    "virtualbox": "VirtualBox.exe",
    "virtual box": "VirtualBox.exe",
    "oracle": "VirtualBox.exe",
    "blender": "blender.exe",
    "figma": "Figma.exe",
    "tlauncher": "javaw.exe",
    "minecraft": "javaw.exe"
}

CUSTOM_LINKS = {
    "moe": "https://everythingmoe.com",
    "everythingmoe": "https://everythingmoe.com",
    "github": "https://github.com",
    "gpt": "https://chatgpt.com",
    "chatgpt": "https://chatgpt.com",
    "youtube": "https://www.youtube.com",
    "gemini": "https://gemini.google.com/"
}

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>F.R.I.D.A.Y. Core Command Center</title>
    <!-- Three.js -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/EffectComposer.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/RenderPass.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/ShaderPass.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/UnrealBloomPass.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/CopyShader.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/LuminosityHighPassShader.js"></script>
    
    <!-- MediaPipe for Hand Gestures -->
    <script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js" crossorigin="anonymous"></script>
    <script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js" crossorigin="anonymous"></script>

    <style>
        :root {
            --primary: #00f0ff;
            --primary-glow: rgba(0, 240, 255, 0.4);
            --bg-center: #031424;
            --font-family: 'Segoe UI', monospace, sans-serif;
        }

        * { 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
            -webkit-tap-highlight-color: transparent;
        }

        body {
            background: radial-gradient(circle at 50% 50%, var(--bg-center) 0%, #000000 100%);
            background-size: 200% 200%;
            animation: bgShift 10s ease-in-out infinite alternate;
            overflow: hidden;
            font-family: var(--font-family);
            color: #fff;
            user-select: none;
            transition: background 0.8s ease;
            width: 100vw;
            height: 100vh;
        }

        @keyframes bgShift {
            0% { background-position: 50% 50%; }
            100% { background-position: 50% 30%; }
        }

        #canvas-container { 
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            z-index: 1; 
        }

        #header-bar {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 10;
            background: rgba(0, 0, 0, 0.65);
            padding: 8px 24px;
            border: 1px solid var(--primary);
            border-radius: 30px;
            backdrop-filter: blur(12px);
            box-shadow: 0 0 25px var(--primary-glow);
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 2px;
            color: var(--primary);
        }

        #telemetry-panel {
            position: fixed;
            top: 75px;
            left: 15px;
            z-index: 10;
            font-size: 10px;
            letter-spacing: 1.2px;
            color: var(--primary);
            background: rgba(0, 0, 0, 0.5);
            padding: 10px 14px;
            border-left: 2px solid var(--primary);
            backdrop-filter: blur(8px);
            box-shadow: 0 0 15px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        #ui-layer {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 10;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            width: 90vw;
            max-width: 460px;
        }

        #chat-log {
            width: 100%;
            height: 120px;
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid var(--primary);
            border-radius: 8px;
            padding: 10px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 6px;
            backdrop-filter: blur(8px);
            font-size: 11px;
        }

        .bubble {
            padding: 6px 10px;
            border-radius: 6px;
            max-width: 85%;
            word-wrap: break-word;
        }

        .bubble.user {
            background: var(--primary);
            color: #000;
            align-self: flex-end;
            font-weight: 600;
        }

        .bubble.bot {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            align-self: flex-start;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        #eq-canvas {
            width: 100%;
            max-width: 380px;
            height: 28px;
            background: rgba(0, 0, 0, 0.4);
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }

        #input-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            padding: 8px 14px;
            width: 100%;
            background: rgba(0, 0, 0, 0.7);
            border: 1px solid var(--primary);
            border-radius: 12px;
            backdrop-filter: blur(12px);
            box-shadow: 0 0 30px var(--primary-glow);
        }

        #text-input {
            background: transparent;
            border: none;
            color: var(--primary);
            font-size: 13px;
            width: 100%;
            outline: none;
            letter-spacing: 1px;
        }

        #text-input::placeholder { color: var(--primary); opacity: 0.5; }

        #mic-btn {
            width: 36px; 
            height: 36px;
            flex-shrink: 0;
            border-radius: 50%;
            border: 1px solid var(--primary);
            background: rgba(255, 255, 255, 0.05);
            cursor: pointer;
            display: flex; 
            align-items: center; 
            justify-content: center;
            transition: all 0.4s;
        }

        #mic-btn:hover { background: var(--primary); transform: scale(1.05); }
        #mic-btn:hover svg { fill: #000; }
        #mic-btn svg { width: 16px; height: 16px; fill: var(--primary); }

        #status-text {
            color: var(--primary);
            font-size: 11px;
            letter-spacing: 2px;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--primary-glow);
            text-align: center;
        }

        #gesture-cam {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 160px;
            height: 120px;
            border: 2px solid var(--primary);
            border-radius: 8px;
            z-index: 20;
            opacity: 0.6;
            box-shadow: 0 0 15px var(--primary-glow);
            transform: scaleX(-1);
            object-fit: cover;
        }

        /* Modal Overlay Notification */
        #modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(8px);
            z-index: 100;
            align-items: center;
            justify-content: center;
        }

        #modal-box {
            background: rgba(3, 20, 36, 0.95);
            border: 1px solid var(--primary);
            box-shadow: 0 0 30px var(--primary-glow);
            border-radius: 12px;
            padding: 24px 32px;
            text-align: center;
            max-width: 320px;
            width: 80%;
        }

        #modal-title {
            color: var(--primary);
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 1.5px;
            margin-bottom: 12px;
        }

        #modal-message {
            color: #ffffff;
            font-size: 12px;
            letter-spacing: 1px;
            margin-bottom: 20px;
        }

        #modal-ok-btn {
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 6px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 700;
            letter-spacing: 1px;
            transition: all 0.3s ease;
        }

        #modal-ok-btn:hover {
            background: var(--primary);
            color: #000;
            box-shadow: 0 0 15px var(--primary-glow);
        }

        .hud-corner {
            position: fixed; 
            width: 25px; 
            height: 25px;
            z-index: 5; 
            pointer-events: none;
            border: 2px solid var(--primary);
            opacity: 0.6; 
        }
        .top-left { top: 10px; left: 10px; border-right: none; border-bottom: none; }
        .top-right { top: 10px; right: 10px; border-left: none; border-bottom: none; }
        .bottom-left { bottom: 10px; left: 10px; border-right: none; border-top: none; }
        .bottom-right { bottom: 10px; right: 10px; border-left: none; border-top: none; }

        @media (max-width: 600px) {
            #telemetry-panel { top: 70px; left: 10px; font-size: 9px; padding: 8px 10px; }
            #gesture-cam { width: 100px; height: 75px; }
        }
    </style>
</head>
<body>
    <div id="canvas-container"></div>
    <video id="gesture-cam" autoplay playsinline></video>

    <!-- Camera Error Modal Notification -->
    <div id="modal-overlay">
        <div id="modal-box">
            <div id="modal-title">SYSTEM NOTICE</div>
            <div id="modal-message">No camera found</div>
            <button id="modal-ok-btn" onclick="closeModal()">OK</button>
        </div>
    </div>

    <div id="header-bar">F.R.I.D.A.Y. CORE COMMAND CENTER</div>

    <div id="telemetry-panel">
        <div>CORE: <span id="tele-core">FRIDAY_v8.1</span></div>
        <div>STATUS: <span id="tele-status">SYNCHRONIZED</span></div>
        <div>CPU: <span id="tele-cpu">0%</span> | RAM: <span id="tele-ram">0%</span></div>
        <div>GESTURES: <span id="tele-gesture">ACTIVE</span></div>
    </div>

    <div class="hud-corner top-left"></div>
    <div class="hud-corner top-right"></div>
    <div class="hud-corner bottom-left"></div>
    <div class="hud-corner bottom-right"></div>

    <div id="ui-layer">
        <div id="status-text">SYSTEM STANDBY</div>
        <div id="chat-log">
            <div class="bubble bot">Boss, standing by for directive...</div>
        </div>
        <canvas id="eq-canvas" width="380" height="28"></canvas>
        <div id="input-container">
            <input type="text" id="text-input" placeholder="Boss, standing by for directive..." autocomplete="off">
            <button id="mic-btn" title="Execute Directive">
                <svg viewBox="0 0 24 24">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                </svg>
            </button>
        </div>
    </div>

    <script>
        const FRIDAY_CONFIG = {
            name: "FRIDAY_v8.1",
            primary: "#00f0ff",
            glow: "rgba(0,240,255,0.4)",
            bg: "#031424",
            colorVec: new THREE.Vector3(0.0, 0.94, 1.0),
            placeholder: "Boss, standing by for directive...",
            displacementType: 1.0,
            colorHex: 0x00f0ff,
            ringSpeedMult: 2.5
        };

        function showCameraErrorModal() {
            document.getElementById('modal-overlay').style.display = 'flex';
            document.getElementById('tele-gesture').textContent = "UNAVAILABLE";
            document.getElementById('tele-gesture').style.color = "#ff4444";
        }

        function closeModal() {
            document.getElementById('modal-overlay').style.display = 'none';
        }

        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x031424, 0.035);

        const sceneGroup = new THREE.Group();
        scene.add(sceneGroup);

        const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.z = 6.5;

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.toneMapping = THREE.ReinhardToneMapping;
        renderer.toneMappingExposure = 1.2;
        document.getElementById('canvas-container').appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.enablePan = false;

        const composer = new THREE.EffectComposer(renderer);
        composer.addPass(new THREE.RenderPass(scene, camera));
        const bloomPass = new THREE.UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.9, 0.4, 0.08);
        composer.addPass(bloomPass);

        const dynamicCoreShader = {
            vertexShader: `
                varying vec2 vUv;
                varying vec3 vNormal;
                varying vec3 vPosition;
                uniform float uTime;
                uniform float uPulse;

                void main() {
                    vUv = uv;
                    vNormal = normalize(normalMatrix * normal);
                    vec3 pos = position;
                    pos += normal * sin(pos.y * 16.0 + uTime * 5.0) * 0.008 * uPulse;

                    vPosition = (modelViewMatrix * vec4(pos, 1.0)).xyz;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
                }
            `,
            fragmentShader: `
                varying vec2 vUv;
                varying vec3 vNormal;
                varying vec3 vPosition;
                uniform float uTime;
                uniform float uPulse;

                void main() {
                    vec3 viewDir = normalize(-vPosition);
                    float fresnel = pow(1.0 - abs(dot(viewDir, vNormal)), 2.2);
                    float grid = clamp(step(0.95, fract(vUv.x * 42.0 - uTime * 0.2)) + step(0.95, fract(vUv.y * 42.0)), 0.0, 1.0);
                    float wave = pow(sin(vUv.y * 150.0 - uTime * 8.0) * 0.5 + 0.5, 4.0);

                    vec3 finalColor = mix(vec3(0.0, 0.35, 0.9), vec3(0.0, 0.94, 1.0), fresnel + grid * 0.6);
                    finalColor = mix(finalColor, vec3(0.8, 0.98, 1.0), wave * 0.4);
                    float alpha = (fresnel * 0.9 + grid * 0.35 + wave * 0.2) * uPulse;
                    gl_FragColor = vec4(finalColor, alpha);
                }
            `
        };

        const coreMaterial = new THREE.ShaderMaterial({
            vertexShader: dynamicCoreShader.vertexShader,
            fragmentShader: dynamicCoreShader.fragmentShader,
            uniforms: { uTime: { value: 0 }, uPulse: { value: 1.0 } },
            transparent: true, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false
        });

        const innerCore = new THREE.Mesh(new THREE.SphereGeometry(1.0, 64, 64), coreMaterial);
        sceneGroup.add(innerCore);

        const cageMaterial = new THREE.MeshBasicMaterial({ color: FRIDAY_CONFIG.colorHex, wireframe: true, transparent: true, opacity: 0.2, blending: THREE.AdditiveBlending });
        const outerCage = new THREE.Mesh(new THREE.IcosahedronGeometry(1.35, 4), cageMaterial);
        sceneGroup.add(outerCage);

        const ringGroup = new THREE.Group();
        sceneGroup.add(ringGroup);

        const ringShader = {
            vertexShader: ` varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); } `,
            fragmentShader: `
                varying vec2 vUv;
                uniform float uTime; uniform float uSpeed; uniform float uDash; uniform vec3 uColor;
                void main() {
                    float angle = atan(vUv.y - 0.5, vUv.x - 0.5);
                    float arc = sin(angle * uDash + uTime * uSpeed) * 0.5 + 0.5;
                    arc = pow(arc, 5.0);
                    gl_FragColor = vec4(uColor, arc * 0.9);
                }
            `
        };

        const rings = [];
        function addRing(radius, tube, dash, speed, rx, ry, rz) {
            const ringGeo = new THREE.TorusGeometry(radius, tube, 16, 128);
            const ringMat = new THREE.ShaderMaterial({
                vertexShader: ringShader.vertexShader,
                fragmentShader: ringShader.fragmentShader,
                uniforms: { uTime: { value: 0 }, uSpeed: { value: speed }, uDash: { value: dash }, uColor: { value: FRIDAY_CONFIG.colorVec } },
                transparent: true, blending: THREE.AdditiveBlending, depthWrite: false
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.set(rx, ry, rz);
            ring.userData = { rx: rx, ry: ry, rz: rz, speed: speed };
            ringGroup.add(ring);
            rings.push(ring);
        }

        addRing(1.55, 0.008, 14.0,  2.2, Math.PI / 2, 0, 0);
        addRing(1.75, 0.005, 20.0, -1.8, Math.PI / 3, Math.PI / 4, 0);
        addRing(1.95, 0.004, 28.0,  2.8, Math.PI / 4, 0, Math.PI / 6);
        addRing(2.15, 0.006, 10.0, -1.2, Math.PI / 1.8, Math.PI / 3, 0);
        addRing(2.45, 0.003, 40.0,  1.4, 0, Math.PI / 2, 0);
        addRing(2.75, 0.002, 52.0, -0.9, Math.PI / 2, Math.PI / 8, 0);

        const pCount = 2000;
        const pGeo = new THREE.BufferGeometry();
        const pPos = new Float32Array(pCount * 3);
        for (let i = 0; i < pCount; i++) {
            const u = Math.random(); const v = Math.random();
            const theta = u * 2.0 * Math.PI; const phi = Math.acos(2.0 * v - 1.0);
            const r = 1.2 + Math.random() * 1.5;
            pPos[i*3] = r * Math.sin(phi) * Math.cos(theta);
            pPos[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
            pPos[i*3+2] = r * Math.cos(phi);
        }
        pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
        const pMat = new THREE.PointsMaterial({ color: FRIDAY_CONFIG.colorHex, size: 0.022, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending });
        const particles = new THREE.Points(pGeo, pMat);
        sceneGroup.add(particles);

        const eqCanvas = document.getElementById('eq-canvas');
        const eqCtx = eqCanvas.getContext('2d');
        let audioActive = false;

        function drawEqualizer() {
            eqCtx.clearRect(0, 0, eqCanvas.width, eqCanvas.height);
            const w = eqCanvas.width;
            const h = eqCanvas.height;
            const midY = h / 2;
            const t = Date.now() * 0.005;

            eqCtx.shadowBlur = 10;
            eqCtx.shadowColor = FRIDAY_CONFIG.primary;

            // Primary Cyan Wave
            eqCtx.beginPath();
            eqCtx.strokeStyle = FRIDAY_CONFIG.primary;
            eqCtx.lineWidth = 2;

            for (let x = 0; x <= w; x += 2) {
                const amp = audioActive ? 12 : 6;
                const y = midY + Math.sin(x * 0.05 + t * 3.5) * Math.cos(x * 0.02 - t * 2) * amp;
                if (x === 0) eqCtx.moveTo(x, y);
                else eqCtx.lineTo(x, y);
            }
            eqCtx.stroke();

            // Secondary White Overlay Wave
            eqCtx.beginPath();
            eqCtx.strokeStyle = "rgba(255, 255, 255, 0.7)";
            eqCtx.lineWidth = 1;

            for (let x = 0; x <= w; x += 3) {
                const amp2 = audioActive ? 8 : 4;
                const y2 = midY + Math.cos(x * 0.08 - t * 4) * Math.sin(x * 0.02 + t) * amp2;
                if (x === 0) eqCtx.moveTo(x, y2);
                else eqCtx.lineTo(x, y2);
            }
            eqCtx.stroke();

            // Node Points along Primary Wave
            const nodeCount = 9;
            for (let i = 0; i < nodeCount; i++) {
                const nx = (i / (nodeCount - 1)) * (w - 20) + 10;
                const ny = midY + Math.sin(nx * 0.05 + t * 3.5) * Math.cos(nx * 0.02 - t * 2) * (audioActive ? 12 : 6);
                eqCtx.fillStyle = "#ffffff";
                eqCtx.beginPath();
                eqCtx.arc(nx, ny, 2.2, 0, Math.PI * 2);
                eqCtx.fill();
            }
            eqCtx.shadowBlur = 0;
        }

        const videoElement = document.getElementById('gesture-cam');
        let prevHandX = null;
        let prevHandY = null;
        let targetScale = 1.0;
        let targetRotationY = 0;
        let targetRotationX = 0;
        let targetPanX = 0;
        let targetPanY = 0;

        const hands = new Hands({locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
        }});

        hands.setOptions({
            maxNumHands: 1,
            modelComplexity: 1,
            minDetectionConfidence: 0.7,
            minTrackingConfidence: 0.7
        });

        hands.onResults((results) => {
            const gestureStatus = document.getElementById('tele-gesture');
            if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
                const landmarks = results.multiHandLandmarks[0];
                const dx = landmarks[8].x - landmarks[4].x;
                const dy = landmarks[8].y - landmarks[4].y;
                const pinchDist = Math.sqrt(dx*dx + dy*dy);
                const currentHandX = landmarks[0].x;
                const currentHandY = landmarks[0].y;
                
                if (prevHandX !== null) {
                    const deltaX = currentHandX - prevHandX;
                    const deltaY = currentHandY - prevHandY;
                    
                    if (pinchDist < 0.05) {
                        targetPanX -= deltaX * 12.0; 
                        targetPanY -= deltaY * 12.0;
                        gestureStatus.textContent = "TRACKING: PAN";
                    } else {
                        targetRotationY -= deltaX * 4.0; 
                        targetRotationX += deltaY * 4.0;
                        targetScale = 0.5 + (pinchDist * 6);
                        targetScale = Math.max(0.4, Math.min(targetScale, 2.5));
                        gestureStatus.textContent = "TRACKING: ROT/ZOOM";
                    }
                }
                prevHandX = currentHandX;
                prevHandY = currentHandY;
                gestureStatus.style.color = "#00ff00";
            } else {
                prevHandX = null;
                prevHandY = null;
                targetScale = 1.0;
                targetPanX = 0;
                targetPanY = 0;
                gestureStatus.textContent = "ACTIVE (NO HAND)";
                gestureStatus.style.color = "var(--primary)";
            }
        });

        const camera_mp = new Camera(videoElement, {
            onFrame: async () => {
                await hands.send({image: videoElement});
            },
            width: 320,
            height: 240
        });

        camera_mp.start().catch((err) => {
            console.warn("Camera failed to start:", err);
            showCameraErrorModal();
        });

        const clock = new THREE.Clock();
        function animate() {
            requestAnimationFrame(animate);
            const t = clock.getElapsedTime();

            coreMaterial.uniforms.uTime.value = t;
            innerCore.rotation.y = t * 0.15;
            outerCage.rotation.x = t * 0.12;
            outerCage.rotation.y = t * 0.18;
            particles.rotation.y = t * 0.06;

            drawEqualizer();

            const speedMult = FRIDAY_CONFIG.ringSpeedMult;
            rings.forEach((ring) => {
                ring.material.uniforms.uTime.value = t * speedMult;
                ring.rotation.z += ring.userData.speed * 0.005 * speedMult;
                ring.rotation.x += ring.userData.speed * 0.0025 * speedMult;
            });

            sceneGroup.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
            sceneGroup.rotation.y += (targetRotationY - sceneGroup.rotation.y) * 0.1;
            sceneGroup.rotation.x += (targetRotationX - sceneGroup.rotation.x) * 0.1;
            sceneGroup.position.x += (targetPanX - sceneGroup.position.x) * 0.1;
            sceneGroup.position.y += (targetPanY - sceneGroup.position.y) * 0.1;

            controls.update();
            composer.render();
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
            composer.setSize(window.innerWidth, window.innerHeight);
        });

        function appendMessage(sender, text) {
            const chatLog = document.getElementById('chat-log');
            const bubble = document.createElement('div');
            bubble.className = `bubble ${sender}`;
            bubble.textContent = text;
            chatLog.appendChild(bubble);
            chatLog.scrollTop = chatLog.scrollHeight;
        }

        async function processInput() {
            const input = document.getElementById('text-input');
            const msg = input.value.trim();
            if (!msg) return;
            
            input.value = '';
            appendMessage('user', msg);
            document.getElementById('status-text').textContent = "CORE PROCESSING...";

            const isCmd = /^(open |close |play |pause|stop|next|prev|volume|mute|unmute|screenshot|screen|lock|shutdown|cancel|go to |visit |link|add link|execute|launch)/i.test(msg);
            const endpoint = isCmd ? '/api/command' : '/api/chat';
            const payload = isCmd ? { command: msg, password: 'friday' } : { message: msg };

            try {
                audioActive = true;
                const res = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.message) {
                    appendMessage('bot', data.message);
                }
            } catch (e) {
                console.error(e);
                appendMessage('bot', "Connection error with core system.");
            } finally {
                audioActive = false;
                document.getElementById('status-text').textContent = "SYSTEM STANDBY";
            }
        }
        
        document.getElementById('text-input').addEventListener('keydown', (e) => { 
            if (e.key === 'Enter') processInput(); 
        });
        document.getElementById('mic-btn').addEventListener('click', processInput);
        
        setInterval(async () => {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('tele-cpu').textContent = data.cpu + '%';
                document.getElementById('tele-ram').textContent = data.ram + '%';
                if (data.network) {
                    document.getElementById('tele-status').textContent = data.network;
                }
            } catch (e) {}
        }, 2000);
    </script>
</body>
</html>"""

import socket

def update_system_stats():
    """Update global system telemetry stats"""
    global system_state
    try:
        system_state["cpu"] = int(psutil.cpu_percent(interval=None))
        system_state["ram"] = int(psutil.virtual_memory().percent)
        system_state["tasks"] = len(psutil.pids())
        memory_gb = psutil.virtual_memory().used / (1024**3)
        system_state["memory"] = f"{memory_gb:.1f} GB"
        
        # Resolve network IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            system_state["network"] = s.getsockname()[0]
            s.close()
        except Exception:
            system_state["network"] = "Offline"
    except Exception as e:
        print(f"Stats error: {e}")

@web_app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@web_app.route("/api/stats", methods=["GET"])
def get_stats():
    update_system_stats()
    return jsonify(system_state)

@web_app.route("/api/command", methods=["POST"])
def api_command():
    data = request.json or {}
    password = data.get("password", "")
    command = data.get("command", "").lower().strip()
    
    if password != WEB_PASSWORD:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    if not command:
        return jsonify({"success": False, "message": "Empty command"}), 400
    
    try:
        msg = execute_system_command(command)
        speak_text(msg)
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@web_app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json or {}
    user_input = data.get('message', '')
    
    # Get response from Groq LLM asynchronously using asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ai_raw_response = loop.run_until_complete(get_friday_response(user_input))
    loop.close()
    
    try:
        parsed_response = json.loads(ai_raw_response)
        action = parsed_response.get("action")
        app_name = parsed_response.get("app_name")
        reply_text = parsed_response.get("reply", "Processing...")

        if action == "app_launch" and app_name:
            # Call the correct function: launch_app_by_name
            reply_text = launch_app_by_name(app_name)
        
        # Trigger Speech Engine
        speak_text(reply_text)
        
        return jsonify({"status": "success", "response": reply_text})

    except Exception:
        # Fallback for non-JSON plain text responses
        speak_text(ai_raw_response)
        return jsonify({"status": "success", "response": ai_raw_response})

@web_app.route("/api/stop", methods=["POST"])
def api_stop():
    data = request.json or {}
    password = data.get("password", "")
    if password != WEB_PASSWORD:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify({"success": True, "message": "Stop sent"})

def open_in_chrome(url: str):
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    os.system(f'start chrome "{url}"')

def play_youtube_video_in_chrome(query: str) -> str:
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    try:
        req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode()
        video_ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", html)
        if video_ids:
            direct_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            open_in_chrome(direct_url)
            return direct_url
    except:
        pass
    open_in_chrome(search_url)
    return search_url

def set_master_volume(percentage: int):
    percentage = max(0, min(100, percentage))
    comtypes.CoInitialize()
    try:
        speakers = AudioUtilities.GetSpeakers()
        volume = speakers.EndpointVolume
        volume.SetMasterVolumeLevelScalar(percentage / 100.0, None)
    except Exception as e:
        print(f"Volume error: {e}")
    finally:
        comtypes.CoUninitialize()

def set_app_volume(app_name: str, percentage: int) -> bool:
    percentage = max(0, min(100, percentage)) / 100.0
    comtypes.CoInitialize()
    try:
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            if session.Process and session.Process.name().lower().startswith(app_name.lower()):
                volume.SetMasterVolume(percentage, None)
                return True
    except Exception as e:
        print(f"App volume adjustment error: {e}")
    finally:
        comtypes.CoUninitialize()
    return False

def launch_app_by_name(app_name: str) -> str:
    app_lower = app_name.lower().strip()
    
    # Check pre-defined shortcuts first
    if app_lower in BUILTIN_APPS:
        os.system(BUILTIN_APPS[app_lower])
        return f"Launching {app_name}"

    # Physical Keyboard & Windows Search interaction
    pyautogui.press('win')
    time.sleep(0.5)
    
    pyautogui.write(app_name, interval=0.05)
    time.sleep(0.8)
    
    pyautogui.press('enter')
    time.sleep(2.5)  # Wait for app process to register

    # Process Verification
    search_term = app_lower.replace(" ", "")
    is_running = False
    
    for proc in psutil.process_iter(['name']):
        try:
            p_name = proc.info['name'].lower()
            if search_term in p_name:
                is_running = True
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if is_running:
        return f"Sir, opening {app_name}."
    else:
        pyautogui.press('escape')
        return f"Sir, {app_name} is not installed."

def close_app_by_name(app_name: str) -> bool:
    app_lower = app_name.lower().strip()
    process_name = PROCESS_MAP.get(app_lower, f"{app_lower}.exe")
    res = os.system(f"taskkill /f /im {process_name}")
    return res == 0

def capture_screenshot() -> str:
    screenshot_path = os.path.join(os.getcwd(), "screenshot.png")
    pyautogui.screenshot(screenshot_path)
    return screenshot_path

def execute_system_command(command: str) -> str:
    cmd = command.lower().strip()
    
    if cmd.startswith("add link "):
        parts = cmd.replace("add link ", "").split(" ", 1)
        if len(parts) == 2:
            name, url = parts[0].strip(), parts[1].strip()
            CUSTOM_LINKS[name] = url
            return f"Added link shortcut: '{name}' -> {url}"
        return "Invalid syntax. Use: add link [name] [url]"

    elif cmd.startswith("link "):
        shortcut = cmd.replace("link ", "").strip()
        if shortcut in CUSTOM_LINKS:
            open_in_chrome(CUSTOM_LINKS[shortcut])
            return f"Opening saved link '{shortcut}'"
        return f"Link '{shortcut}' not found."

    elif cmd.startswith("go to ") or cmd.startswith("visit "):
        site = cmd.replace("go to ", "").replace("visit ", "").strip()
        open_in_chrome(site)
        return f"Navigating to {site}"

    elif cmd.startswith("open "):
        app_query = cmd.replace("open ", "").strip()
        return launch_app_by_name(app_query)

    elif cmd.startswith("close "):
        app_query = cmd.replace("close ", "").strip()
        close_app_by_name(app_query)
        return f"Closed {app_query}"

    elif "volume" in cmd or "vol" in cmd:
        app_vol_match = re.search(r'(spotify|youtube|chrome)\s+volume\s+(\d+)%?', cmd)
        if app_vol_match:
            app_target = app_vol_match.group(1)
            vol_val = int(app_vol_match.group(2))
            set_app_volume(app_target, vol_val)
            return f"Set {app_target} volume to {vol_val}%"
            
        match = re.search(r'\d+', cmd)
        if match:
            vol_level = int(match.group())
            set_master_volume(vol_level)
            return f"Master volume set to {vol_level}%"
        elif "up" in cmd:
            pyautogui.press("volumeup", presses=5)
            return "Volume increased"
        elif "down" in cmd:
            pyautogui.press("volumedown", presses=5)
            return "Volume decreased"

    elif cmd in {"mute", "unmute"}:
        pyautogui.press("volumemute")
        return "Toggled audio mute state"

    elif cmd in {"play", "pause"}:
        pyautogui.press("playpause")
        return "Playback toggled"

    elif cmd in {"next", "next track"}:
        pyautogui.press("nexttrack")
        return "Skipped to next track"

    elif cmd in {"prev", "previous", "prev track"}:
        pyautogui.press("prevtrack")
        return "Skipped to previous track"

    elif "spotify" in cmd:
        query = cmd.replace("play ", "").replace(" on spotify", "").replace("spotify play ", "").replace("spotify", "").strip()
        os.system(f'start spotify:search:"{query}"')
        return f"Searching and playing '{query}' on Spotify"

    elif "youtube" in cmd or cmd.startswith("play "):
        query = cmd.replace("play ", "").replace(" on youtube", "").replace("youtube play ", "").replace("youtube", "").strip()
        play_youtube_video_in_chrome(query)
        return f"Playing '{query}' on YouTube"

    elif "screenshot" in cmd or "screen" in cmd:
        capture_screenshot()
        return "Screenshot captured successfully"

    elif "lock" in cmd:
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "PC workstation locked"

    elif "cancel shutdown" in cmd:
        os.system("shutdown /a")
        return "Scheduled system shutdown canceled"

    elif "shutdown" in cmd:
        os.system("shutdown /s /t 30")
        return "System scheduled to shutdown in 30 seconds"

    elif cmd in {"status", "system check", "system status"}:
        update_system_stats()
        return f"All systems nominal — CPU {system_state['cpu']}%, RAM {system_state['ram']}%"

    return "Directive recognized, processing request."


def run_web_server():
    """Runs backend server internally for standalone interface."""
    web_app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

def main():
    print("=" * 60)
    print("Initializing F.R.I.D.A.Y. Standalone Desktop Core Center")
    print("=" * 60)
    
    # 1. Start Internal Flask Backend Async Communication Engine
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    time.sleep(1.2)

    # 2. Launch WebGL-Compatible Chromium Desktop Window
    webview.create_window(
        "F.R.I.D.A.Y. CORE COMMAND CENTER", 
        "http://127.0.0.1:5000",
        width=1100,
        height=800,
        resizable=True
    )
    webview.start()

if __name__ == "__main__":
    main()