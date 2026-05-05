# ALEX — Adaptive Logic Execution eXecutor

> [!WARNING]
> **Main.exe must be run exactly where you want ALEX to exist (ALL FILES WILL BE STORED TOGETHER WHERE MAIN.exe will be**
ALEX is a modular voice + text AI execution assistant built in Python, powered by Groq-hosted open-source LLMs. It converts natural language into structured system actions and executes them safely through a strict, deterministic pipeline.

Unlike traditional assistants, ALEX doesn’t just respond—it **acts**.

---

> [!WARNING]
> **USER MUST RUN THE FOLLOWING COMMAND IF THEY WISH TO USE BROWSER AUTOMATION FEATURES:**

```bash
pip install playwright
playwright install chromium
```

Without this step, browser automation features will not function.

---

## Features

*  Voice + Text input (STT + CLI fallback)
*  Text-to-Speech responses
*  Groq-powered LLM planning (LLaMA 3.x / OSS)
*  Strict function registry (`knowledge.md`)
*  Deterministic intent → execution pipeline
*  Modular action system
*  Real-time animated overlay UI (audio-reactive orb)
*  Multi-step task execution (chained actions)

---

##  How It Works

1. User gives input (voice or text)
2. LLM converts input → strict JSON intent
3. Intent is validated against schema + registry
4. Router maps function → Python التنفيذ
5. Action executes safely

**LLM plans. Python executes. Nothing else runs.**

---

## Installation (Quick Start)

### 1. Download ALEX

* Go to **Releases** on this repository
* Download the latest build for your platform
* Extract the files

---

### 2. Get Groq API Keys

* Visit Groq
* Create an account and generate **2 API keys**

---

### 3. Launch ALEX

* Run the application
* The setup wizard (Qt-based UI) will appear

---

### 4. Configure API Keys

* Paste both Groq API keys into the wizard
* Complete setup

---

### 5. Start Using ALEX

* Use voice or text commands
* The overlay UI will indicate system state:

  * Idle
  * Listening
  * Processing
  * Speaking

---

## 📁 Project Structure

```
assistant/
├── main.py
├── config.py
├── llm/
├── core/
├── voice/
├── actions/
├── knowledge/
├── ui/
└── utils/
```

---

## Safety Model

* Only functions in `knowledge.md` can execute
* No arbitrary or dynamic code execution
* Sensitive actions require confirmation
* All LLM outputs must follow strict JSON schema

---

## Example

**Input:**

> "Open YouTube and play lo-fi music"

**Execution Flow:**
→ JSON intent generated
→ Validated
→ Routed
→ `play_youtube_music()` executed

---

## Tech Stack

* Python
* Groq API (LLaMA 3.x / OSS models)
* PyQt6 / PySide6 (overlay UI)
* NumPy + audio processing (FFT visualization)

---

## Philosophy

ALEX is not a chatbot.

It is a **controlled AI execution layer** designed for:

* Predictability
* Safety
* Real-world task execution

> The model decides.
> The system verifies.
> Python executes.

---

## Status

 Fully functional (MVP complete)
 Actively evolving

---

## ❤️ Contributing

Contributions, ideas, and improvements are welcome. Open an issue or submit a PR.
P.S. : Comments before a PR would be appreciated more.

---
