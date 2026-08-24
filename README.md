# 🤖 JARVIS — Personal AI Operating Layer

> An autonomous, ultra-secure, voice-activated desktop AI operating layer for Windows powered by Google Gemini and faster-whisper.

---

## 🌟 Highlights & Features

- 🎙️ **Continuous Voice Assistant**: Real-time wake-word detection (*"Jarvis" / "Hey Jarvis"*), Automatic Gain Control (AGC), noise filtering, and multilingual speech-to-text with `faster-whisper`.
- 🗣️ **Neural Text-to-Speech**: High-fidelity Indian English/Hindi voice synthesis (`edge-tts` & `pyttsx3`).
- 🖥️ **Cyberpunk HUD Glassmorphism Desktop GUI**:
  - Live animated glowing Orb visualizer (`Listening` / `Thinking` / `Speaking` / `Idle`).
  - Live system stats telemetry (CPU, RAM, Battery).
  - Conversation feed & interactive Push-to-Talk.
- ⌨️ **Global Windows Hotkeys**:
  - `Alt + J` / `Ctrl + Shift + A` / `F8` — Show or hide HUD from anywhere in Windows.
- 🚀 **Windows Auto-Start on Boot**:
  - Seamless system tray integration with background listening.
- 🛡️ **Ultra God-Level Security Suite**:
  1. **Windows DPAPI Vault** (`app/security/vault.py`): TPM hardware-backed credential encryption.
  2. **Zero-Trust Anti-Malware Sandbox** (`app/security/sandbox.py`): Intercepts ransomware shadow copy wipes, OS drive wiping, and malicious download cradles.
  3. **Emergency Protocol Zero / Code Red** (`app/security/lockdown.py`): Voice-activated instant workstation lock and volatile data purge.
  4. **Anti-Prompt Injection 2.0** (`app/security/injection.py`): Neutralizes indirect prompt injections and markdown exfiltration beacons.
  5. **Cryptographic Audit Ledger** (`app/security/audit.py`): SHA-256 HMAC chained immutable security ledger.

---

## ⚡ Quick Start

### 1. Setup Environment
```powershell
cd jarvis
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt -r requirements-windows.txt
playwright install chromium
```

### 2. Configure API Key
Copy `.env.example` to `.env` in the `jarvis/` directory and add your Google Gemini API Key:
```env
JARVIS_GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Launch JARVIS Desktop App
```powershell
.\run.bat app
```
Or double click `JARVIS` on your desktop!

---

## ⌨️ Shortcuts & Voice Commands

| Action | Shortcut / Trigger |
|---|---|
| **Toggle HUD** | `Alt + J` or `F8` or `Ctrl + Shift + A` |
| **Wake Word** | *"Jarvis"* or *"Hey Jarvis"* |
| **Push-to-Talk** | Click `🎙️ Speak` or click central glowing Orb |
| **Startup Greeting** | `python run.py greet [--speak]` |
| **Install Boot Greeting** | `python run.py startup install [--speak]` |
| **Emergency Lockdown** | *"Jarvis protocol zero"* or *"Jarvis emergency lockdown"* |


---

## 🧪 Testing
```powershell
pytest
```
*104+ unit tests verifying brain, intent, voice, tools, permissions, and security suite.*

---

## 📄 License
MIT License.
