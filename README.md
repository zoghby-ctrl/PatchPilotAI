---
title: PatchPilot AI
emoji: 🛠️
colorFrom: blue
colorTo: purple
sdk: streamlit
app_file: app.py
pinned: false
license: mit
---

# PatchPilot AI

PatchPilot AI is a generic agentic code review, debugging, and improvement copilot for tough complex code and simple everyday scripts.

It supports C++, Java, JavaScript, Python, and C# source files. The app analyzes code, detects bug risks, security issues, performance bottlenecks, complexity problems, and generates actionable fix recommendations plus practical test plans.

## Features

- Upload C++, Java, JavaScript, Python, C#, text, or markdown files
- Multi-agent workflow:
  - Language & Structure Agent
  - Bug & Correctness Agent
  - Security Agent
  - Performance & Complexity Agent
  - Refactor Agent
  - Test Planner Agent
  - Executive Summary Agent
- Works without API keys using deterministic rule-based analysis
- Optional OpenAI-compatible model support for deeper review
- Designed for GPT-5.5 / GPT-5.4 / GPT-5 family style coding models through API keys
- Streamlit UI for local demo or Hugging Face Spaces

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Optional OpenAI model mode

Set these as environment variables or enter them in the app sidebar:

```bash
OPENAI_API_KEY=<your_key>
PATCHPILOT_MODEL=gpt-5.5
```

The app calls the OpenAI-compatible Chat Completions endpoint. If no API key is provided, PatchPilot still runs with the deterministic fallback analyzer.

## AMD Developer Hackathon relevance

PatchPilot AI fits the AI Agents & Agentic Workflows track. It uses multiple specialized code-review agents to automate a real developer workflow.

For AMD Developer Cloud integration, the same app can point to an OpenAI-compatible endpoint hosted on AMD GPU infrastructure using ROCm/vLLM:

```bash
PATCHPILOT_LLM_BASE_URL=<AMD-hosted-endpoint>/v1
PATCHPILOT_LLM_API_KEY=<key>
PATCHPILOT_MODEL=<model-name>
```

## License

MIT
