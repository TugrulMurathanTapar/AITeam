# 🚀 Multi-AI Orchestrator

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows%20%7C%20WSL-lightgrey.svg)](#cross-platform-support)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Interface](https://img.shields.io/badge/UI-Textual%20TUI%20%26%20Web-green.svg)](#interface-modes)
[![Encryption](https://img.shields.io/badge/Security-AES--256--GCM-red.svg)](#sync-token-workflow--cryptography)
[![i18n](https://img.shields.io/badge/i18n-English%20%7C%20T%C3%BCrk%C3%A7e-orange.svg)](#bilingual-support-i18n)

> A cross-platform multi-AI deliberation platform, portable memory manager, and execution orchestrator featuring rich Terminal UI (TUI), zero-knowledge encrypted cloud sync, sandboxed skill automation, and seamless Turkish/English localization.

---

## 📑 Table of Contents

1. [Features](#-key-features)
2. [System Architecture](#-system-architecture)
3. [Project Directory Layout](#-project-directory-layout)
4. [Installation & Quick Start](#-installation--quick-start)
   - [Linux & macOS](#linux--macos)
   - [Windows](#windows)
   - [WSL (Windows Subsystem for Linux)](#wsl-windows-subsystem-for-linux)
5. [Terminal User Interface (TUI)](#-terminal-user-interface-tui)
   - [Navigation & Shortcuts](#keyboard-shortcuts)
   - [Deliberation Panel](#multi-ai-deliberation)
6. [Web Client & GitHub Pages](#-web-client--github-pages)
7. [Sync Token & Cryptography](#-sync-token-workflow--cryptography)
8. [Security Policy & Sandboxing](#-security-policy--sandboxing)
9. [Supported Providers & Setup](#-supported-providers--setup)
   - [OpenAI](#1-openai)
   - [Anthropic Claude](#2-anthropic-claude)
   - [Google Gemini](#3-google-gemini)
   - [Groq](#4-groq-lpu)
   - [Ollama (Local LLMs)](#5-ollama-local)
10. [Bilingual Support (i18n)](#-bilingual-support-i18n)
11. [Contributing](#-contributing)
12. [License](#-license)

---

## 🌟 Key Features

* **Multi-AI Deliberation Engine**: Run debates across multiple AI models concurrently. Synthesize divergent reasoning with automated consensus scoring and designated judge models.
* **Portable Memory Browser**: Maintain hierarchical persistent facts, project identities, and custom sub-memories. Easily merge, branch, or export contexts.
* **Zero-Knowledge Encrypted Sync**: Package API configurations and memories into an encrypted string or QR code using client-side **AES-256-GCM** derived with **PBKDF2-HMAC-SHA256**.
* **Dual Interface System**:
  * **Textual TUI**: High-speed, responsive, terminal-based keyboard-first interface for local developers and sysadmins.
  * **Web Client**: Lightweight browser companion hosted statically on GitHub Pages with client-side decryption.
* **Fine-Grained Security Enforcement**: Explicit permission barriers for file system reads/writes/deletions, outbound network requests, and terminal command execution.
* **Bilingual Out of the Box**: Seamless 1-click toggle between **English** and **Turkish (Türkçe)** across all screens, logs, and dialogs.

---

## 🏛 System Architecture

The Multi-AI Orchestrator decouples providers, deliberation logic, storage, and user interfaces into an asynchronous, modular architecture:

```
                  +----------------------------------------------+
                  |                 USER / DEV                   |
                  +----------------------+-----------------------+
                                         |
                  +----------------------v-----------------------+
                  |         Cross-Platform Launchers             |
                  |     (run.sh / run.bat / launcher.py)         |
                  +----------------------+-----------------------+
                                         |
            +----------------------------+----------------------------+
            |                                                         |
+-----------v--------------------+                       +------------v-------------------+
|     Textual TUI Interface      |                       |    Browser Web Client (Static) |
| (ui/app.py, i18n, screens, css)|                       | (HTML5, Vanilla JS, WebCrypto) |
+-----------+--------------------+                       +------------+-------------------+
            |                                                         |
            |        +-----------------------------------+            |
            +------->|   Encrypted Sync Token / QR Code  |<-----------+
                     |  (AES-256-GCM + PBKDF2 Derivation)|
                     +-----------------------------------+
                                         |
            +----------------------------+----------------------------+
            |                            |                            |
+-----------v-----------+   +------------v-----------+   +------------v-------------------+
|   Multi-AI Engine     |   |   Hierarchical Memory  |   |    Security & Skills Engine    |
| - OpenAI / Anthropic  |   | - Core Memory (JSON)   |   | - Sandboxed Tool Execution     |
| - Gemini / Groq       |   | - Sub-Memories Manager |   | - FS Scope & Sudo Gatekeeper   |
| - Ollama (Local)      |   | - Context Merging      |   | - Full Audit Event Logger      |
| - Consensus & Debate  |   +------------------------+   +--------------------------------+
+-----------------------+
```

---

## 📂 Project Directory Layout

```
.
├── config/                  # Provider profiles, credentials, app preferences
├── launcher/
│   ├── launcher.py          # Python environment checker & TUI bootstrapper
│   ├── run.sh               # Unix/macOS launch script with automatic venv setup
│   └── run.bat              # Windows launcher batch script
├── logs/                    # Audit logs and debug traces
├── memory/                  # Core memory and isolated sub-memory JSON files
├── ui/
│   ├── __init__.py          # UI package init
│   ├── app.py               # Textual TUI Application instance
│   ├── i18n.py              # Bilingual (TR/EN) registry with ~200 entries
│   └── screens/             # Modals, chat view, memory browser, settings
├── workspace/               # Safe sandbox directory for file tools
├── pyproject.toml           # Standard PEP 517 / 621 package metadata
├── requirements.txt         # Production dependencies
└── README.md                # Documentation and architecture guide
```

---

## 🚀 Installation & Quick Start

### Prerequisites
* Internet access for the first launch
* On Windows, **winget** (App Installer) if Python 3.10+ is not already installed
* On Debian, administrator access (`sudo` or root) so the launcher can install system packages

---

### Debian Linux

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/ai-orchestrator.git
   cd ai-orchestrator
   ```

2. **Make the launcher executable and launch:**
   ```bash
   chmod +x launcher/run.sh
   ./launcher/run.sh
   ```

> `run.sh` installs missing Debian packages (including Python, venv, and desktop-automation prerequisites) through apt, creates `.venv`, installs `requirements.txt`, and starts the app. It may request your sudo password. Python 3.10+ is required; Debian 12 or newer is recommended.
>
> `install_linux.sh` is a separate, optional system-wide installer. It copies the app to `/opt/ai-orchestrator` and adds the `ai-orchestrator` command; it is not another project-folder launcher.

---

### Windows

1. **Clone the repository:**
   ```cmd
   git clone https://github.com/your-org/ai-orchestrator.git
   cd ai-orchestrator
   ```

2. **Run the batch launcher:**
   ```cmd
   launcher\run.bat
   ```

> The launcher checks that `.venv` uses Python 3.10 or newer and recreates it if it is missing, broken, or too old. If no compatible system Python is found, it installs Python 3.12 for the current Windows user with winget, then creates the environment and installs `requirements.txt`. Install Windows App Installer (which provides winget) first if it is unavailable.

`launcher\run.bat` is the single supported Windows project launcher. The former root-level and portable-bundle batch launchers have been removed.

---

### WSL (Windows Subsystem for Linux)

Install a Debian WSL distribution separately, then use the Debian launcher inside WSL. The launcher installs Debian packages but does not install or configure WSL itself:
```bash
wsl
cd /path/to/ai-orchestrator
./launcher/run.sh
```

---

## 🖥 Terminal User Interface (TUI)

The TUI is powered by [Textual](https://textual.textualize.io/) and designed for high efficiency:

```
+-------------------------------------------------------------------------------+
| 🚀 AI Orchestrator [EN] | Models: 3 Active | Memory: ProjectAlpha             |
+-------------------------------------------------------+-----------------------+
|  Chat & Deliberation Session                          | Context & Facts       |
|                                                       | - Stack: FastAPI, TUI |
|  User: Analyze edge-case routing for microservices.   | - Security: Strict    |
|                                                       | - Provider: Claude 3.5|
|  Claude: In distributed scenarios, consider back-     +-----------------------+
|  pressure and circuit breakers...                     | Deliberation Panel    |
|                                                       | Round 1/2: In debate  |
|  GPT-4o: Concurring, but adding exponential jitter... | Consensus: 87%        |
|                                                       +-----------------------+
|  Judge: Synthesis suggests token-bucket + jitter.     | Active Tools          |
|                                                       | [Bash] [FS] [Web]     |
+-------------------------------------------------------+-----------------------+
| > Enter command or prompt...                                [ Send ] [ Ctrl+D ]|
+-------------------------------------------------------------------------------+
```

### Keyboard Shortcuts

The chat composer stays at the bottom of the chat screen, including after returning from Settings. The right-hand chat sidebar contains a multi-AI deliberation switch. With deliberation off, choose an enabled model there for a direct reply; with only one enabled model, chat uses it directly and deliberation is unavailable. The mode switch is saved with the application settings.

| Shortcut | Description |
| :--- | :--- |
| `Ctrl+L` | **Toggle Language** (English ⇄ Türkçe) instantly |
| `Ctrl+D` | **Toggle Multi-AI Deliberation** (available when at least two models are enabled) |
| `Ctrl+N` | **New Session** (reset context buffer) |
| `Ctrl+S` | **Open Settings** (API keys, models, security scope) |
| `Ctrl+Q` | **Quit** the orchestrator |
| `F1` | **Help Dialog** & Documentation |

---

## 🌐 Web Client & GitHub Pages

The project includes an optional client-side Web Client designed for deployment on **GitHub Pages**:

* **Zero Backend Required**: Runs 100% in the browser.
* **Client-Side Cryptography**: Uses the W3C WebCrypto API for PBKDF2 derivation and AES-256-GCM decryption.
* **Portable Setup**: Sync state between your desktop terminal and mobile phone via QR code without exposing secrets to an intermediary server.

### Deploying to GitHub Pages

1. In your repository on GitHub, navigate to **Settings** > **Pages**.
2. Under **Build and deployment**, set the source to **Deploy from a branch**.
3. Select `main` (or `gh-pages`) branch and `/web` (or `/docs`) folder.
4. Click **Save**. Your web client will be live at `https://<username>.github.io/<repo-name>/`.

---

## 🔐 Sync Token Workflow & Cryptography

All API credentials, sub-memories, and security parameters can be bundled into an encrypted token.

```
+-------------------+        PBKDF2-HMAC-SHA256         +----------------------+
| User Passphrase   | --------------------------------> | 256-bit AES Key      |
+-------------------+      (600,000 Iterations)         +----------+-----------+
                                                                   |
+-------------------+                                              |
| App State Payload | ---------------------------------------------+
| (APIs, Memories)  |                    AES-256-GCM
+-------------------+       (12-byte IV + 16-byte Auth Tag)
                                         |
                                         v
                         +-------------------------------+
                         | Encrypted Sync Token / Base64 |
                         |       or Visual QR Code       |
                         +-------------------------------+
```

1. In the TUI, navigate to **Cloud & Sync** (`Ctrl+S` > Sync).
2. Enter a master passphrase (minimum 8 characters).
3. Click **Generate Token** or **Show QR Code**.
4. In the Web Client or on another terminal instance, enter the passphrase and paste the token string (or scan the QR code) to restore state.

---

## 🛡 Security Policy & Sandboxing

The orchestrator follows the principle of least privilege:

* **File System Scoping**: Tools can only access explicit directories configured in `allowed_paths` (defaults to `./workspace/`).
* **Sudo Protection**: Elevated commands require explicit permission toggles in the Security Settings.
* **Terminal Commands**: AI terminal execution is disabled by default; enable **Allow AI to run terminal commands** in Security Settings only when needed. Commands run with the current user's operating-system permissions.
* **Chat Tool Access**: In direct (non-deliberation) chat, permission-enabled registered tools are exposed to compatible providers and run through the same permission checks. Saving Security Settings persists these permissions. Screen capture, mouse, and keyboard permissions do not currently provide AI-callable desktop tools.
* **Filesystem Scope**: To let chat create, read, or update files, enable the relevant read/write permissions and add the destination directory to **Allowed Paths**. Chat shows a live elapsed-time/status indicator while a model or tool is working.
* **Provider Transport**: Remote API endpoints must use HTTPS. HTTP is accepted only for localhost services such as Ollama.
* **Private Local Data**: API keys, saved provider/model configurations, and chat history stay in the per-user application data directory, separate from the source tree. Do not share that settings file or logs.
* **Audit Trail**: Every file read/write, skill execution, and network request is recorded in `logs/audit.log`.

---

## 🔌 Supported Providers & Setup

### 1. OpenAI
* **Compatible Models**: `gpt-4o`, `gpt-4o-mini`, `o1-preview`, `o1-mini`
* **Base URL**: `https://api.openai.com/v1`
* **Schema**: `OpenAI`

### 2. Anthropic Claude
* **Compatible Models**: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`, `claude-3-haiku-20240307`
* **Base URL**: `https://api.anthropic.com/v1`
* **Schema**: `Anthropic`

### 3. Google Gemini
* **Compatible Models**: `gemini-1.5-pro-latest`, `gemini-1.5-flash`
* **Base URL**: `https://generativelanguage.googleapis.com/v1beta`
* **Schema**: `Google`

### 4. Groq (LPU)
* **Compatible Models**: `llama-3.3-70b-versatile`, `mixtral-8x7b-32768`
* **Base URL**: `https://api.groq.com/openai/v1`
* **Schema**: `OpenAI`

### 5. Ollama (Local)
* **Compatible Models**: `llama3.2`, `mistral`, `deepseek-r1`, `qwen2.5-coder`
* **Base URL**: `http://localhost:11434/v1`
* **Schema**: `OpenAI`
* **Setup**:
  ```bash
  ollama run llama3.2
  ```

---

## 🇹🇷 Bilingual Support (i18n)

The application features full parity between English and Turkish:
* UI strings, status prompts, notifications, and confirmations are registered in `ui/i18n.py`.
* Switch languages anytime using `Ctrl+L` or from the Settings panel.
* Dynamic event listeners update all widgets immediately without restarting the app.

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository and create your feature branch (`git checkout -b feature/my-feature`).
2. Adhere to **Python 3.10+ async-first** patterns and type annotations.
3. Keep Turkish and English string entries synchronized in `ui/i18n.py`.
4. Commit your changes and open a Pull Request.

---

## 📄 License

This project is licensed under the terms of the **MIT License**. See [LICENSE](LICENSE) for details.

## ⚖️ Responsibility & Disclaimer

This software is provided **as is**, without warranties of any kind. The user is solely responsible for installation, API keys, credentials, terminal and filesystem permissions, backups, memory data, provider usage, and every result produced by the application.

Users must review permissions, protect sensitive data, maintain independent backups of important files, and operate the software only in environments they are authorized to use. The developers are not liable for data loss, unauthorized actions, service failures, security incidents, or any direct or indirect damages arising from use of this software.

---

## 🧪 Testing Stage / Test Aşaması

Bu sürüm **test aşamasındadır** ve henüz nihai üretim sürümü olarak kabul edilmemelidir. / This release is in the **testing stage** and should not yet be considered a final production release.
