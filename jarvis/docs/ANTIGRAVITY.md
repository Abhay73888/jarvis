# JARVIS ko Google Antigravity mein chalana — Complete Guide

Ye guide batati hai ki is JARVIS project ko **Google Antigravity** (Google ka
free agentic IDE — Gemini 3 Pro powered) mein kaise daal kar develop aur
execute karna hai.

---

## 0. Ek zaroori clarification (confusion hoti hai!)

**Do alag Gemini hain is setup mein:**

| | Kya hai | Kahan se |
|---|---|---|
| **Antigravity ka Gemini 3 Pro** | IDE ka agent — jo aapke project ko *develop* karega (code likhega, tests chalayega) | Antigravity app mein Google sign-in se milta hai (public preview, free with limits) |
| **JARVIS ka apna Gemini** | JARVIS runtime ka dimaag — user ki baat samajhne ke liye | Aapka API key: `JARVIS_GEMINI_API_KEY` in `.env` — free key: **aistudio.google.com/apikey** |

Antigravity se project banwana aur JARVIS ko Gemini key dena — dono alag steps
hain, dono zaroori hain.

---

## 1. Antigravity install karo (Windows)

1. **antigravity.google/download** kholo (sirf official site — koi third-party
   mirror nahi).
2. **Windows x64** choose karo (Intel/AMD PC) ya **ARM64** (Snapdragon laptop).
   Requirement: Windows 10 64-bit ya newer.
3. Installer run karo — SmartScreen warning aaye to **More info → Run anyway**.
4. Launch karke **Google account se sign in** karo (Gemini 3 Pro isse active
   hota hai).

## 2. Project ko Antigravity mein kholo

1. Workspace file download karo: `jarvis-antigravity.zip` (Arena workspace se).
2. Kisi folder mein unzip karo — e.g. `C:\dev\jarvis`.
3. Antigravity mein **File → Open Folder** → `C:\dev\jarvis` select karo.
   (Project root kholo, parent folder nahi — indexing fast rahegi.)
4. Agent **`AGENTS.md`** automatically padh lega — usme project ke rules,
   setup commands, architecture, aur "what to build next" sab likha hai.

## 3. Python ready karo (agar nahi hai)

Antigravity ke terminal mein (Ctrl+` / Terminal → New Terminal):
```powershell
python --version        # 3.12+ chahiye
# Agar nahi hai: python.org se install karo, "Add Python to PATH" tick karo
```

## 4. Pehla Mission — Setup + Verification

**Agent Manager** kholo (**Ctrl+E**) → New Agent → ye prompt paste karo:

> Read AGENTS.md first. Then set up this project: create a venv, install
> requirements.txt, run `python run.py init`, then run `pytest -q`.
> Expected result: all tests pass (95 passed). Report the actual output.

**Setting tip:** Antigravity mein *Terminal Command Auto Execution* default
"Request Review" rehta hai — matlab har command se pehle aapki approval
lega. Theek hai — JARVIS jaisa hi safety model hai. Jab bharosa ho jaye,
settings mein allowlist badal sakte ho.

## 5. JARVIS ko uska Gemini key do + run karo

1. **aistudio.google.com/apikey** se free API key banao.
2. Project root mein `.env` file banao:
   ```
   JARVIS_GEMINI_API_KEY=AIza...aapki_key
   ```
3. Terminal mein chalao:
   ```powershell
   .venv\Scripts\activate
   pip install -r requirements-windows.txt    # voice/GUI/browser extras
   python run.py doctor                        # sab ✓ hona chahiye
   python run.py                               # JARVIS console start
   ```
4. Try karo: `mera laptop slow kyu hai` · `desktop pe folder bana Demo naam ka`
   · `python automation tutorial search karo` → `first wala kholo`
   (browser agent ke liye pehle: `pip install playwright` +
   `playwright install chromium`)

## 6. Aage ke Missions (paste-ready)

**Mission A — Windows verification (🔶 → ✅):**
> Read AGENTS.md. Verify the Windows-specific features on THIS machine
> (Start Menu app discovery, open_application with os.startfile,
> close_application via taskkill, PowerShell terminal_execute, headed
> Playwright browser). Write real tests where possible, update README's
> status matrix from 🔶 to ✅ only with evidence.

**Mission B — Phase 6 Voice:**
> Read AGENTS.md and docs/ROADMAP.md Phase 6. Implement the voice subsystem:
> local wake word (openwakeword), faster-whisper STT with Hindi/English
> auto-detect, TTS abstraction (edge-tts online + pyttsx3 offline fallback),
> streaming "Sure sir..." first-token speech, and barge-in interrupt.
> Platform-guard all audio code; unit-test everything non-audio; keep the
> full suite green; update docs.

**Mission C — Phase 11 GUI:**
> Read AGENTS.md. Build the PySide6 GUI + system tray per docs/ROADMAP.md
> Phase 11: subscribe only to EventBus topics (status, tool.finished,
> permission.requested); dark glass theme; waveform; task status; CPU/RAM;
> install the permission confirm handler. Console must keep working.

## 7. Antigravity tips is project ke liye

- **Agent Manager (Ctrl+E)** se parallel agents chalao — e.g. ek Voice pe,
  ek GUI pe (alag branches).
- **Artifacts/Mission Control** se agent ke plans aur browser ke verifiable
  steps review karo — merge se pehle.
- Agent se kaho har change ke baad `pytest -q` chalaye — AGENTS.md mein ye
  rule already hai, wo follow karega.
- Kabhi agent se API key code/commit mein nahi dalwa — hamesha `.env`
  (AGENTS.md rule #3, aur JARVIS ka redaction system bhi isko pakadta hai).

---

**TL;DR:** Antigravity install → zip unzip → File → Open Folder → Mission 1
prompt paste (agent setup + tests kar dega) → `.env` mein apni Gemini key →
`python run.py` → JARVIS live. 🧠
