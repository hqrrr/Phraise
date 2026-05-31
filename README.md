# PhrAIse

[![License](https://img.shields.io/github/license/hqrrr/Phraise?color=888)](LICENSE)&nbsp;
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2B-4c8eda)](https://github.com/hqrrr/Phraise)&nbsp;
[![Python](https://img.shields.io/badge/Python-3.11%2B-4c8eda)](https://python.org)

> A system-wide AI writing assistant for Windows. Use your own LLM API keys - no subscription, no vendor lock-in, full control.

<p align="center">
  <sub>
    🌐 <a href="README_zh.md">中文文档</a>
  </sub>
</p>

## Quick Navigation

- [Why PhrAIse?](#why-phraise)
- [What It Does](#what-it-does)
- [Getting Started](#getting-started)
- [LLM Providers](#llm-providers)
- [Configuration](#configuration)
- [Hotkeys](#hotkeys)
- [Build](#build)
- [Project Structure](#project-structure)
- [License & Cost](#license--cost)

## Why PhrAIse?

If you already pay for LLM API access, you can use it as a writing assistant; no need for additional subscriptions to services like DeepL or Grammarly. Today's flash models can polish and translate text at a fraction of a cent per request.

[WritingTools](https://github.com/theJayTea/WritingTools) is the most popular open-source alternative. It follows an Apple Intelligence-inspired pop-up menu workflow (select text -> pick action -> get result). PhrAIse takes a different approach: one hotkey opens a persistent floating window in which all the styles, rewrites and grammar fixes are visible at once, with no need for extra clicks between edits.

Neither is objectively better. They're built for different writing habits. This is the one that fits mine.

## What It Does

Select text anywhere, hit a hotkey (Default: Ctrl+C+C), and PhrAIse rewrites or translates it using your configured LLM.

- **Optimize**: three rewrite versions per request with grammar checking, in any style you define (Concise, Formal, Natural, or custom)
- **Translate**: translation with auto-detection, one-click replace
- **Custom instructions**: free-form AI edits with extensible style presets
- **System integration**: global hotkeys, UIA-based text grab (clipboard-safe), system tray, app blacklist
- **Configuration**: OpenAI-compatible API, dual model slots, per-function model assignment, custom CSS theming

## Getting Started

### Requirements

- Windows 10 (21H2+) / 11
- Python 3.11+
- API key from any OpenAI-compatible LLM provider

### Run from Source

```bash
pip install -r phraise/requirements.txt
python -m phraise.main
```

On first launch, right-click the tray icon or floating ball -> **Settings** -> configure at least one model with your API key.

## LLM Providers

| Provider           | Status                         |
|--------------------|--------------------------------|
| OpenAI             | Built-in                       |
| Claude (Anthropic) | Built-in                       |
| Gemini (Google)    | Built-in                       |
| DeepSeek           | Built-in                       |
| OpenRouter         | Built-in                       |
| Kimi (Moonshot)    | Built-in                       |
| GLM (Zhipu)        | Built-in                       |
| Qwen (Tongyi)      | Built-in                       |
| SiliconFlow        | Built-in                       |
| **Custom**         | Any OpenAI-compatible endpoint |

## Configuration

Settings are in `%APPDATA%/PhrAIse/settings.json`. All configurable through the Settings panel.

## Hotkeys

| Hotkey                    | Action                                      |
|---------------------------|---------------------------------------------|
| `Ctrl+C+C` (double-tap C) | Trigger optimize/translate on selected text |
| `Ctrl+Shift+B`            | Toggle floating ball visibility             |
| `Esc`                     | Close floating window                       |

All hotkeys are configurable in **Settings**.

## Build

Package into a standalone `.exe` with PyInstaller:

```bash
python build.py
# Output: dist/PhrAIse.exe
```

## Project Structure

```text
Phraise/
├── build.py              # PyInstaller build script
├── phraise/
│   ├── main.py           # Application entry point & lifecycle
│   ├── config.py         # JSON-based configuration management
│   ├── i18n.py           # Internationalization
│   ├── theme.py          # Themes & CSS config
│   ├── prompts.py        # LLM prompt templates
│   ├── llm_client.py     # OpenAI-compatible API client
│   ├── settings_panel.py # Settings dialog (models, styles, triggers, appearance)
│   ├── floating_ball.py  # Draggable always-on-top orb
│   ├── floating_window.py# Main window (optimize / translate)
│   ├── hotkeys.py        # Global hotkey listener
│   ├── text_grabber.py   # UIA text extraction & replacement
│   ├── detector.py       # Active window detection
│   ├── dispatch.py       # Thread-safe main-thread dispatcher
│   ├── error_log.py      # Error logging
│   └── assets/           # Icons and resources
└── README.md
```

## License & Cost

**PhrAIse** is free and open-source under the [GNU GPLv3](LICENSE). No premium tiers, no subscriptions, no limitations.

If you find it useful, the best way to support the project is:

- 🐞 Report bugs or unexpected behavior
- 💡 Suggest features or improvements
- 🔧 Submit pull requests
- 📢 Share it with someone who might find it helpful

---

*Built for my own workflow. Shared in case it fits yours too.*
