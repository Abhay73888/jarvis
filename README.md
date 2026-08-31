# 🤖 JARVIS — Personal AI Operating Layer (v0.6.0-offline)

> An autonomous, ultra-secure, voice-activated desktop AI operating layer for Windows powered by Google Gemini, Ollama Local Brain, Piper Neural TTS, and faster-whisper.

---

## 🌟 Highlights & Features

- 🎙️ **100% Offline Continuous Voice Loop**:
  - Zero-internet hands-free operation: Real-time wake-word detection (*"Jarvis" / "Hey Jarvis"* via `openwakeword`), Automatic Gain Control (AGC), noise filtering, and multilingual speech-to-text with `faster-whisper` (`small` int8 model).
  - Sub-second wake detection and sentence-chunk streaming with instant barge-in interrupt (*"stop" / "ruk jao"*).
- 🗣️ **Piper Neural & Cloud Hybrid TTS**:
  - High-fidelity natural female voice synthesis (Piper `hi_IN` / `en_IN` neural voices, `edge-tts`, and `pyttsx3`/`Zira` fallback).
- 🧠 **Hybrid Brain & Failover Router**:
  - Automatic real-time failover between Google Gemini (online) and local Ollama (`qwen2.5` / `gemma3` / `llama3.1`) with zero context loss.
  - **Privacy Mode**: One-click or voice toggle to enforce 100% local-only execution without making a single external socket request.
- 🌅 **Boot Companion & Spoken Daily Brief**:
  - Lightweight resident companion speaks your daily brief in < 3s after login.
  - Brief includes time, date, battery status, pending tasks from local SQLite DB, and disk warning if > 90%.
  - Fully offline voice-driven task management (*"mere tasks batao"*, *"naya task: ... "*, *"ye complete ho gaya"*, *"snooze 10 minute"*).
- 🖥️ **Cyberpunk HUD Glassmorphism Desktop GUI**:
  - Live animated glowing Orb visualizer (`Listening` / `Thinking` / `Speaking` / `Idle`).
  - Synapse Matrix & Protocol Matrix for real-time offline status and capability badges.
  - Live system stats telemetry (CPU, RAM, Battery) and interactive Push-to-Talk.
- ⌨️ **Global Windows Hotkeys & Dictation**:
  - `Alt + J` / `Ctrl + Shift + A` / `F8` — Show or hide HUD from anywhere in Windows.
  - **Offline Dictation Mode**: Say *"dictation on"* to type your speech directly into any focused application with zero internet.
- 🛡️ **Ultra God-Level Security Suite**:
  1. **Windows DPAPI Vault** (`app/security/vault.py`): TPM hardware-backed credential encryption.
  2. **Zero-Trust Anti-Malware Sandbox** (`app/security/sandbox.py`): Intercepts ransomware shadow copy wipes, OS drive wiping, and malicious download cradles.
  3. **Emergency Protocol Zero / Code Red** (`app/security/lockdown.py`): Voice-activated instant workstation lock and volatile data purge.
  4. **Anti-Prompt Injection 2.0** (`app/security/injection.py`): Neutralizes indirect prompt injections and markdown exfiltration beacons.
  5. **Cryptographic Audit Ledger** (`app/security/audit.py`): SHA-256 HMAC chained immutable security ledger.

---

## ⚡ OFFLINE FIRST — One-Time Setup

JARVIS works completely offline without requiring an active internet connection after running the one-time offline pack setup.

### 🧠 Model Recommendation by RAM

| System RAM | Recommended Local Model | Provider | Disk Footprint |
|---|---|---|---|
| **4 GB** | `qwen2.5:1.5b` / `tinyllama` | Ollama | ~1.0 GB |
| **8 GB** | `qwen2.5:3b` / `gemma3:4b` | Ollama | ~2.5 GB |
| **16 GB+** | `qwen2.5:7b` / `llama3.1:8b` | Ollama | ~4.7 GB |

### 🚀 Setup in 2 Commands

```powershell
# 1. Download & configure all offline models & voices (one time)
python run.py offline-setup

# 2. Verify all local components with self-tests (10-second check)
python run.py offline-verify
```

Verification Output:
```
==============================================================================
  JARVIS OFFLINE VERIFICATION & SELF-TEST SUITE
==============================================================================
  COMPONENT              | STATUS | TIME    | DETAILS
------------------------------------------------------------------------------
  Manifest               | [PASS] | 2ms     | 5/5 components registered
  Offline Brain / NLU    | [PASS] | 0ms     | Intent resolved in 0ms (system_info)
  Neural/Offline TTS     | [PASS] | 1ms     | Clean synthesis & female voice configured
  faster-whisper STT     | [PASS] | 189ms   | Model initialized & ready
  openWakeWord           | [PASS] | 2040ms  | Models loaded (jarvis, hey_jarvis, ...)
  Tesseract OCR          | [PASS] | 35ms    | pytesseract & tessdata operational
==============================================================================
  ✓ ALL OFFLINE SELF-TESTS PASSED — 100% OFFLINE READY.
==============================================================================
```

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

### 2. Configure (Optional for Cloud Gemini Mode)
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
| **Dictation Mode** | *"dictation on"* / *"dictation off"* |
| **Tasks & Agenda** | *"mere tasks batao"* / *"naya task: ... "* / *"ye complete ho gaya"* |
| **Startup Greeting** | `python run.py greet [--speak]` |
| **Install Boot Greeting** | `python run.py startup install [--speak]` |
| **Emergency Lockdown** | *"Jarvis protocol zero"* or *"Jarvis emergency lockdown"* |

---

## 🧪 Testing & Verification
```powershell
pytest
```
*171 automated unit tests verifying core engine, offline voice loop (socket-blocked), hybrid brain, boot companion, offline superpowers, and security suite.*

---

## 📄 License
MIT License.
