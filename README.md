# PhrAIse

<img src="phraise/assets/phraise_logo.svg" alt="PhrAIse Logo" width="100"/>

[![Downloads](https://img.shields.io/github/downloads/hqrrr/Phraise/total?color=4c8eda)](https://github.com/hqrrr/Phraise/releases)&nbsp;
[![Release](https://img.shields.io/github/v/release/hqrrr/Phraise?label=release&color=4c8eda)](https://github.com/hqrrr/Phraise/releases)
&nbsp;
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2B-4c8eda)](https://github.com/hqrrr/Phraise)&nbsp;
[![License](https://img.shields.io/badge/license-GPL--3.0-lightgray)](LICENSE)

> A system-wide AI writing assistant. Use your own LLM API keys - or run grammar checks locally - no subscription, no vendor lock-in, full control.

<p align="center">
  <sub>
    🌐 <a href="README_zh.md">中文文档</a>
  </sub>
</p>

## Quick Navigation

- [PhrAIse](#phraise)
  - [Quick Navigation](#quick-navigation)
  - [Why PhrAIse?](#why-phraise)
  - [What It Does](#what-it-does)
    - [Local Mode with Harper](#local-mode-with-harper)
    - [LLM Mode - Optimize \& Translate](#llm-mode---optimize--translate)
    - [Core System Features](#core-system-features)
  - [LLM Providers](#llm-providers)
  - [Configuration](#configuration)
  - [Hotkeys](#hotkeys)
  - [Getting Started](#getting-started)
    - [Download Pre-built `.exe`](#download-pre-built-exe)
    - [Run from Source](#run-from-source)
      - [Requirements](#requirements)
      - [Run](#run)
  - [Build](#build)
  - [Project Structure](#project-structure)
  - [License \& Cost](#license--cost)

## Why PhrAIse?

If you already pay for LLM API access, you can use it as a writing assistant; no need for additional subscriptions to services like DeepL or Grammarly. Today's flash models can polish and translate text at a fraction of a cent per request.

[WritingTools](https://github.com/theJayTea/WritingTools) is the most popular open-source alternative. It follows an Apple Intelligence-inspired pop-up menu workflow (select text -> pick action -> get result). PhrAIse takes a different approach: one hotkey opens a persistent floating window in which all the styles, rewrites and grammar fixes are visible at once, with no need for extra clicks between edits.

Neither is objectively better. They're built for different writing habits. This is the one that fits mine.

## What It Does

Select text anywhere, hit a hotkey (Default: `Ctrl+C+C`), and PhrAIse rewrites or translates it using your configured engine.

PhrAIse has two interchangeable engines for the **Optimize** function:

### Local Mode with Harper

*Simple and Fast*

[**Harper**](https://github.com/Automattic/harper) is a local, offline grammar engine. No API key, no network request, no data leaves your machine. It catches spelling mistakes, repeated words, missing/extra spaces, wrong articles (`a`/`an`), unclosed quotes, apostrophe issues, and more.

When Harper is assigned to Optimize, **PhrAIse** shows a single corrected version and a list of detected grammar issues. You can toggle individual fixes on or off before replacing the original text.

**Demo Opmization (Harper mode)**

![demo-optimize-harper-mode](demo/demo-optimize-harper-mode.gif)

### LLM Mode - Optimize & Translate

*More Powerful*

When you assign a configured LLM model to **Optimize** or **Translate**, **PhrAIse** uses your LLM provider:

- **Optimize**: three rewrite versions per request with grammar checking, in any style you define (Concise, Formal, Natural, or custom)
- **Translate**: translation with auto-detection, one-click replace
- **Custom instructions**: free-form AI edits with extensible style presets

**Demo Optimization (LLM mode)**
![demo-optimize-LLM](demo/demo-optimize-LLM.gif)

**Demo Translation (LLM mode)**
![demo-translate-LLM](demo/demo-translate-LLM.gif)

### Core System Features

- **System integration**: global hotkeys, UIA-based text grab (clipboard-safe), system tray, app blacklist
- **Configuration**: OpenAI-compatible API, dual model slots, per-function model assignment, custom CSS theming

## LLM Providers

The built-in provider list is fetched from **[models.dev](https://github.com/anomalyco/models.dev)** on startup and merged with a curated local fallback. This means new OpenAI-compatible endpoints appear automatically; if the network is unavailable, PhrAIse falls back to the local list.

> ⚠️ **Coding Plan Warning**
>
> Most providers define what their coding plans / subscriptions may be used for according to their own documentation. "Coding plans" are generally intended for interactive programming agents (such as OpenCode, Cursor, Codex, etc.), **NOT** for writing assistants like PhrAIse. Using a coding plan in PhrAIse may violate the provider's terms of service and could result in your account being suspended or banned.
>
> Please check [Coding Plan Status](Coding_Plan.md) whether PhrAIse is allowed to use their coding plans.

> 💵 If you're looking for free LLM API, this repo may help you: [Free LLM API resources](https://github.com/cheahjs/free-llm-api-resources)

## Configuration

Settings are in `%APPDATA%/PhrAIse/settings.json`. All configurable through the Settings panel.

## Hotkeys

| Hotkey                    | Action                                      |
|---------------------------|---------------------------------------------|
| `Ctrl+C+C` (double-tap C) | Trigger optimize/translate on selected text |
| `Ctrl+Shift+B`            | Toggle floating ball visibility             |
| `Esc`                     | Close floating window                       |

All hotkeys are configurable in **Settings**.

## Getting Started

### Download Pre-built `.exe`

If you just want to run PhrAIse without installing Python, download the latest release from the [GitHub Releases](https://github.com/hqrrr/Phraise/releases) page and run `PhrAIse.exe` directly.

> 👉 On first launch, right-click the tray icon or floating ball -> **Settings** -> configure at least one model with your API key, or set **Optimize** to **Harper** to use the local grammar engine.

### Run from Source

#### Requirements

- Windows 10 (21H2+) / 11
- Python 3.11+
- For LLM mode: API key from any OpenAI-compatible LLM provider
- For Harper local mode: nothing extra; the Harper binary is bundled

#### Run

```bash
pip install -r phraise/requirements.txt
python run.py
```

> 👉 On first launch, right-click the tray icon or floating ball -> **Settings** -> configure at least one model with your API key, or set **Optimize** to **Harper** to use the local grammar engine.


## Build

Package into a standalone `.exe` with PyInstaller:

```bash
python build.py
# Output: dist/PhrAIse.exe
```

Releases will be published on GitHub with downloadable `.exe` files. The download badge at the top of this README will show total downloads once the release workflow is active.

## Project Structure

```text
Phraise/
├── build.py                    # PyInstaller build script
├── phraise/
│   ├── main.py                 # Application entry point & lifecycle
│   ├── config.py               # JSON-based configuration management
│   ├── i18n.py                 # Internationalization
│   ├── theme.py                # Themes & CSS config
│   ├── prompts.py              # LLM prompt templates
│   ├── llm_client.py           # OpenAI-compatible API client
│   ├── harper_client.py        # Local Harper grammar engine client
│   ├── harper_lsp_manager.py   # Harper LSP subprocess manager
│   ├── settings_panel.py       # Settings dialog (models, styles, triggers, appearance)
│   ├── floating_ball.py        # Draggable always-on-top orb
│   ├── floating_window.py      # Main window (optimize / translate)
│   ├── hotkeys.py              # Global hotkey listener
│   ├── text_grabber.py         # UIA text extraction & replacement
│   ├── detector.py             # Active window detection
│   ├── dispatch.py             # Thread-safe main-thread dispatcher
│   ├── error_log.py            # Error logging
│   └── assets/                 # Icons and resources
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
