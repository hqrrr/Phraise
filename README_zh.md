# PhrAIse · 妙语

<img src="phraise/assets/phraise_logo.svg" alt="PhrAIse Logo" width="100"/>

[![License](https://img.shields.io/github/license/hqrrr/Phraise?color=888)](LICENSE)&nbsp;
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2B-4c8eda)](https://github.com/hqrrr/Phraise)&nbsp;
[![Python](https://img.shields.io/badge/Python-3.11%2B-4c8eda)](https://python.org)&nbsp;
[![Downloads](https://img.shields.io/github/downloads/hqrrr/Phraise/total?color=4c8eda)](https://github.com/hqrrr/Phraise/releases)

> 系统级 AI 写作助手。使用你自己的 LLM API Key，或者本地运行语法检查 —— 无订阅费，不绑定服务商，完全可控。

<p align="center">
  <sub>
    🌐 <a href="README.md">English Documentation</a>
  </sub>
</p>

## 快速导航

- [为什么开发这个软件？](#为什么开发这个软件)
- [功能](#功能)
- [快速开始](#快速开始)
- [支持的 LLM 服务商](#支持的-llm-服务商)
- [Coding Plan 兼容性](#coding-plan-兼容性)
- [配置说明](#配置说明)
- [快捷键](#快捷键)
- [打包构建](#打包构建)
- [项目结构](#项目结构)
- [许可与费用](#许可与费用)

## 为什么开发这个软件？

如果你已经在为 LLM API 付费，完全可以用它来做写作助手 —— 不需要额外订阅类似 DeepL / Grammarly 等服务。现在的 flash 模型处理文字润色和翻译，每次请求成本不到一分钱。

[WritingTools](https://github.com/theJayTea/WritingTools) 是最流行的开源替代品，它采用弹出菜单式交互（选中文本 -> 弹窗中选择操作 -> 出结果），类似 Apple Intelligence 的体验。PhrAIse 走的是另一条路：选中文本后一次快捷键打开常驻悬浮窗，风格、改写版本、语法检查全部摊开在眼前 —— 编辑之间无需额外点击。

没有孰优孰劣，只是写作习惯不同。这个是按我自己的使用习惯开发的。

## 功能

选中任意文字，按下快捷键（默认 `Ctrl+C+C`），PhrAIse 就会使用你配置的引擎进行改写或翻译。

**优化** 功能支持两种可切换的引擎：

### 本地离线模式 — Harper

[**Harper**](https://github.com/Automattic/harper) 是一个本地、离线的语法检查引擎。不需要 API Key，不需要联网，数据不会离开你的电脑。它可以发现拼写错误、重复单词、多余或缺失空格、`a`/`an` 错误、未闭合引号、撇号错误等。

当 Harper 被分配到 **优化** 时，PhrAIse 会显示一个修正后的版本，并列出检测到的语法问题。你可以在替换原文前单独启用或关闭某一条修正建议。

### LLM 模式 — 优化与翻译

当你为 **优化** 或 **翻译** 分配一个已配置的LLM模型时，PhrAIse 会使用你的 LLM 服务商：

- **优化**：每次生成相同风格下的三个改写版本，附带语法检查。支持自定义风格（简洁、正式、自然或自定义）
- **翻译**：自动检测源语言，一键替换
- **自定义指令**：自由格式 AI 编辑，风格预设可扩展

### 核心系统功能

- **系统集成**：全局快捷键、UIA 文本抓取（剪贴板兜底）、系统托盘、应用黑名单
- **配置**：OpenAI 兼容 API、双模型配置、按功能分配模型、自定义 CSS 主题

## 支持的 LLM 服务商

内置服务商列表在启动时从 **[models.dev](https://models.dev)** 获取，并与一份本地列表合并。这意味着新的 OpenAI 兼容端点会自动出现；如果网络不可用，**PhrAIse** 会回退到本地列表。

> ⚠️ **Coding Plan 警告**
>
> 大多数服务商按照自己的文档定义 API 计划的使用范围。"Coding plan" 通常面向交互式编程 Agent（例如 OpenCode、Cursor、Codex 等），**不适用**于 PhrAIse 这类写作助手。在 PhrAIse 中使用 coding plan 可能违反服务商的服务条款，并可能导致你的账号被暂停或封禁。
>
> 请查看 [Coding Plan Status](Coding_Plan.md) 确认 PhrAIse 是否被允许使用他们的 coding plan。

## 配置说明

配置文件位于 `%APPDATA%/PhrAIse/settings.json`，所有设置均可通过设置面板修改。

## 快捷键

| 快捷键              | 功能           |
|------------------|--------------|
| `Ctrl+C+C`（双击 C） | 对选中文字触发优化/翻译 |
| `Ctrl+Shift+B`   | 切换悬浮球显示/隐藏   |
| `Esc`            | 关闭悬浮窗        |

所有快捷键均可在 **设置** 中修改。

## 快速开始

### 下载预编译 `.exe`

如果你不想安装 Python，可以直接从 [GitHub Releases](https://github.com/hqrrr/Phraise/releases) 下载最新版本的 `PhrAIse.exe`，双击即可运行。

### 从源码运行

#### 环境要求

- Windows 10 (21H2+) / 11
- Python 3.11+
- 使用 LLM 模式：任一 OpenAI 兼容 LLM 服务商的 API Key
- 使用 Harper 本地模式：无需额外配置，Harper 二进制文件已随软件附带

#### 运行

```bash
pip install -r phraise/requirements.txt
python run.py
```

首次启动后，右键托盘图标或悬浮球 -> **设置** -> 至少为一个模型配置 API Key；或者将 **优化** 设置为 **Harper**，直接使用本地语法引擎。


## 打包构建

使用 PyInstaller 构建独立 `.exe`：

```bash
python build.py
# 输出：dist/PhrAIse.exe
```

后续版本将通过 GitHub Releases 发布可下载的 `.exe` 文件。一旦发布工作流启用，页面顶部的下载量 badge 将显示总下载次数。

## 项目结构

```text
Phraise/
├── build.py              # PyInstaller 打包脚本
├── phraise/
│   ├── main.py           # 应用入口与生命周期管理
│   ├── config.py         # JSON 配置管理
│   ├── i18n.py           # 多语言支持
│   ├── theme.py          # 主题与 CSS 配置
│   ├── prompts.py        # LLM 提示词模板
│   ├── llm_client.py     # OpenAI 兼容 API 客户端
│   ├── harper_client.py  # 本地 Harper 语法引擎客户端
│   ├── harper_lsp_manager.py # Harper LSP 子进程管理
│   ├── settings_panel.py # 设置面板（模型、风格、快捷键、外观）
│   ├── floating_ball.py  # 可拖拽置顶悬浮球
│   ├── floating_window.py# 主窗口（优化 / 翻译）
│   ├── hotkeys.py        # 全局快捷键监听
│   ├── text_grabber.py   # UIA 文本提取与替换
│   ├── detector.py       # 活动窗口检测
│   ├── dispatch.py       # 线程安全主线程调度
│   ├── error_log.py      # 错误日志
│   └── assets/           # 图标与资源文件
└── README.md
```

## 许可与费用

**PhrAIse** 在 [GNU GPLv3](LICENSE) 下免费开源。没有付费版本，无需订阅，没有功能限制。

如果你觉得有用，最好的支持方式是：

- 🐞 报告 bug 或异常行为
- 💡 提出功能建议或改进想法
- 🔧 提交 Pull Request
- 📢 把它分享给可能需要的人

---

*按自己的习惯写的工具。分享出来，或许也适合你的工作流程。*
