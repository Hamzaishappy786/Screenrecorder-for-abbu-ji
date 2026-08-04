# 📹 Screen Recorder — Abbu Ji ke Liye

> *Custom made screen recorder for just my family.*

A lightweight, single-file screen recorder built as a personal gift for my father.  
Designed to run on old hardware (Core i3, 2nd/3rd gen) with zero technical knowledge required — just double-click and go.

---

## Features

- **One-click recording** — big clear buttons in Roman Urdu
- **Auto-compressed output** — H.264 MP4, tuned for small file size
- **Save anywhere** — file dialog after every recording, father picks the folder
- **Full-screen zoom** — hold `Alt + X` and scroll up/down to zoom the entire screen at the cursor
- **Live recording indicator** — blinking red dot appears top-right of screen while recording
- **Clickable save dialog** — click the file path after saving to open the folder directly
- **App icon** — custom `.ico` on the taskbar and title bar

---

## Requirements

| Tool | Notes |
|------|-------|
| Python 3.10+ | [python.org](https://python.org) — tick "Add to PATH" during install |
| ffmpeg | Bundled inside the `.exe` — no separate install needed on target machine |

Python dependencies (installed automatically by `build.bat`):

```
keyboard
pynput
pyinstaller
```

---

## Project Structure

```
Screen recorder for abba ji/
├── recorder.py          # Full application source
├── requirements.txt     # pip dependencies
├── build.bat            # Compiles to .exe — double-click to build
├── me-holding-a-pic.ico # App icon
└── ffmpeg/
    └── ffmpeg.exe       # Bundled FFmpeg binary (not committed to git)
```

---

## Build

```bash
build.bat
```

Output: `dist\ScreenRecorder.exe` (~44 MB, fully self-contained)

> **Note:** `ffmpeg\ffmpeg.exe` is not committed to the repo (94 MB binary).  
> Download from [ffmpeg.org](https://ffmpeg.org/download.html) and place at `ffmpeg\ffmpeg.exe` before building.

---

## Usage

### Recording
| Action | How |
|--------|-----|
| Start recording | Click **● Recording Shuru Karo** |
| Stop & save | Click **■ Roko aur Save Karo** |
| Pick save location | File dialog opens automatically after stopping |

### Zoom (during or outside recording)
| Combo | Effect |
|-------|--------|
| `Alt + X` + scroll up | Zoom in (whole screen, cursor-anchored) |
| `Alt + X` + scroll down | Zoom out |
| `Alt + 0` | Reset zoom to normal |

---

## Sending to Father's PC

Just send the single compiled `ScreenRecorder.exe` — no installation, no Python, nothing else needed.

On first run, Windows SmartScreen may warn about an unknown publisher.  
Tell him: **"More info" → "Run anyway"** — happens once, never again.

---

## UI

Dark GitHub-style theme, maximized on launch, fully in **Roman Urdu**.

```
┌─────────────────────────────────────────────────────────┐
│                      ● REC                              │
│                  Screen Recorder                        │
│       Custom made screen recorder for just my family    │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  ●  Tayyar hai                                    │  │
│  │              00:00                                │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ████████  ●  Recording Shuru Karo  ████████  (green)  │
│                                                         │
│  ████████  ■  Roko aur Save Karo   ████████  (red)     │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  ZOOM KAISE KAREIN                                │  │
│  │  Alt+X + scroll UPAR   →  Zoom In                │  │
│  │  Alt+X + scroll NEECHE →  Zoom Out               │  │
│  │  Alt+0  →  Zoom bilkul normal                    │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

- Status card shows **live timer** (`00:00`) and a **blinking dot** while recording
- Buttons have **hover states** and are **disabled** when not applicable
- Window **minimizes automatically** when recording starts
- After stopping: a custom **save dialog** appears with a clickable blue path that opens the folder in Explorer

---

## FFmpeg Settings

Tuned specifically for low-spec hardware:

```
-framerate 15          # Light on CPU, smooth enough for demos
-preset ultrafast      # Minimal encoding overhead
-tune zerolatency      # No lookahead buffering
-crf 28                # Good compression, small file size
```

---

## Why This Exists

Built with love so Abbu Ji can record his screen without needing to ask for help. 🎁
