# PatchPilot AI

PatchPilot AI is an agentic debugging copilot for C++ game engine and multiplayer/networking developers.

It analyzes uploaded C++ files, detects likely bugs, finds performance and networking risks, suggests fixes, and generates a practical test plan.

## Features

- Upload `.cpp`, `.h`, `.hpp`, `.txt`, `.md` files
- Multi-agent review pipeline:
  - Bug Hunter Agent
  - Networking Agent
  - Performance Agent
  - Test Planner Agent
  - Executive Summary Agent
- Works without API keys using a deterministic fallback analyzer
- Optional LLM endpoint support through OpenAI-compatible APIs
- Streamlit UI for local demo or Hugging Face Spaces

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Optional LLM endpoint

```bash
export PATCHPILOT_LLM_BASE_URL="http://localhost:8000/v1"
export PATCHPILOT_LLM_API_KEY="EMPTY"
export PATCHPILOT_LLM_MODEL="Qwen/Qwen2.5-Coder-7B-Instruct"
```

## AMD Developer Cloud angle

PatchPilot can connect to an OpenAI-compatible coding model served on AMD Developer Cloud using ROCm/vLLM. This allows the multi-agent workflow to run stronger model-powered code review while keeping the app interface simple.

## Hackathon pitch

PatchPilot AI helps C++ game and engine developers catch multiplayer defects before release. It uses multiple specialized agents to convert source code into structured bug reports, networking risk analysis, performance recommendations, and test plans.

## License

MIT
