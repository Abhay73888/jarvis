# Windows-Specific Notes & Limitations

Honest engineering constraints (Spec §2: don't pretend magic).

## What works headless (verified in CI on Linux + expected on Windows)
- Everything except: audio, screenshots, native window APIs, Start Menu scan,
  `os.startfile`, taskkill. All business logic (planning, permissions, risk,
  files via portable paths, terminal via subprocess) is platform-tested.

## Windows constraints to expect

| Area | Reality |
|---|---|
| **UAC / elevation** | Actions touching `HKLM`, other users' processes, or protected files need an elevated process. JARVIS will not auto-elevate; it reports "may need elevated rights" (close_application already does). |
| **Store apps (UWP)** | Start Menu `.lnk` scan misses some UWP apps; they appear via `Get-StartApps`. Phase 5 adds a PowerShell-based UWP resolver (real invocation, not faked). |
| **Windows Sandbox for Store apps** | Some UWP apps refuse external UI automation entirely. JARVIS will fall back to launch-only and say so. |
| **Antivirus heuristics** | PyInstaller builds + simulated input sometimes trip AV. Signed builds later; documented for now. |
| **UI Automation** | pywinauto/UIA works well for Win32/WPF/WinUI apps with an accessibility tree; Electron apps expose Chromium AX; some Java/DirectX games expose nothing → vision fallback (Phase 8). Never blind-coordinate clicking when a semantic selector exists. |
| **Microphone privacy setting** | Windows Settings → Privacy → Microphone must allow desktop apps, or sounddevice gets silence. `doctor` will check this in Phase 6. |
| **Wake word on battery** | Continuous audio costs ~2-4% CPU with openWakeWord on small models; hotkey alternative provided. |
| **TTS voices** | pyttsx3 uses SAPI5 (Zira/David — robotic); edge-tts gives natural neural voices but needs internet; Hindi voices: en-IN/hi-IN (msedge). |
| **PowerShell execution policy** | JARVIS runs PowerShell with `-NoProfile -NonInteractive` and does NOT require script execution (inline `-Command` only). setup.ps1 is run explicitly by the user. |
| **Paths with spaces / non-ASCII (Hindi usernames)** | Tools quote and resolve paths via pathlib; tested with spaces. |
| `os.startfile` | Available only on Windows — guarded by platform checks; Linux dev fallback uses xdg-open. |

## Why Linux CI can honestly test Windows-targeted logic
All decision logic (risk, permissions, planning, intents, file safety) is pure
Python. The Windows-specific adapters (taskkill, startfile, Start Menu scan)
are thin, isolated, and marked 🔶 in the README status matrix until verified
on a real Windows machine.
