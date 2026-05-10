import re
import os
import requests
import streamlit as st

SAMPLE_CPP = """
#include <vector>
#include <thread>
#include <mutex>
#include <cstring>
#include <iostream>

struct Packet {
    int playerId;
    int sequence;
    char payload[256];
};

class NetworkWorld {
public:
    std::vector<Packet*> incoming;
    std::mutex mtx;
    int lastSequence = 0;

    void receive(char* data, int size) {
        Packet* p = new Packet();
        memcpy(p, data, size);
        incoming.push_back(p);
    }

    void process() {
        for (auto p : incoming) {
            if (p->sequence < lastSequence) {
                std::cout << "old packet" << std::endl;
            }
            lastSequence = p->sequence;
            applyPacket(p);
        }
        incoming.clear();
    }

    void applyPacket(Packet* p) {
        std::thread worker([&]() {
            std::cout << "Applying packet for player " << p->playerId << std::endl;
        });
        worker.detach();
    }
};
"""


def call_llm(system_prompt, user_prompt):
    base_url = os.getenv("PATCHPILOT_LLM_BASE_URL")
    api_key = os.getenv("PATCHPILOT_LLM_API_KEY", "EMPTY")
    model = os.getenv("PATCHPILOT_LLM_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")

    if not base_url:
        return None

    try:
        response = requests.post(
            base_url.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 1200,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"LLM endpoint failed, using fallback analysis. Error: {e}"


def find_lines(code, patterns):
    results = []
    for i, line in enumerate(code.splitlines(), start=1):
        for label, pattern in patterns:
            if re.search(pattern, line):
                results.append((i, label, line.strip()))
    return results


def bug_hunter_agent(code, use_llm=False):
    if use_llm:
        out = call_llm(
            "You are a senior C++ engine debugging agent. Return concise Markdown.",
            "Find memory, lifetime, undefined behavior and concurrency bugs in this C++ code:\n\n" + code[:12000],
        )
        if out and not out.startswith("LLM endpoint failed"):
            return out

    patterns = [
        ("Raw allocation may leak or have unclear ownership", r"\bnew\b"),
        ("Unsafe copy: check bounds and object layout", r"\bmemcpy\b|\bstrcpy\b|\bsprintf\b"),
        ("Detached thread can outlive referenced data", r"\.detach\s*\("),
        ("Lambda captures by reference; risky with async work", r"\[&\]"),
        ("Shared container access may need locking", r"\.push_back\s*\(|\.clear\s*\("),
    ]

    hits = find_lines(code, patterns)
    md = "## Bug Hunter Agent\n\n"

    if not hits:
        return md + "No obvious high-risk bug patterns found by the fallback analyzer.\n"

    for line, label, src in hits:
        md += f"- **Line {line}: {label}**\n"
        md += f"  ```cpp\n  {src}\n  ```\n"
        md += "  Suggested action: replace with safer ownership, bounds checks, synchronization, or scoped thread management.\n\n"

    return md


def networking_agent(code, use_llm=False):
    if use_llm:
        out = call_llm(
            "You are a multiplayer networking code review agent. Return concise Markdown.",
            "Review this C++ code for packet ordering, serialization, replay, race, validation, and authoritative-server problems:\n\n" + code[:12000],
        )
        if out and not out.startswith("LLM endpoint failed"):
            return out

    checks = []

    if "sequence" in code:
        checks.append("Sequence numbers are present, but the code should also handle wraparound, duplicate packets, and per-player sequence tracking.")

    if "memcpy" in code:
        checks.append("Binary packet copy should validate size and protocol version before deserialization.")

    if "playerId" in code:
        checks.append("Never trust `playerId` from client payload without server-side session validation.")

    if "lastSequence" in code:
        checks.append("A single `lastSequence` for all players can incorrectly reject valid packets from different clients.")

    if not checks:
        checks.append("Add explicit packet schema validation, authentication/session mapping, and replay protection.")

    return "## Networking Agent\n\n" + "\n".join(f"- {c}" for c in checks)


def performance_agent(code, use_llm=False):
    if use_llm:
        out = call_llm(
            "You are a C++ performance profiling agent for game engines. Return concise Markdown.",
            "Find performance bottlenecks and suggest optimizations in this C++ code:\n\n" + code[:12000],
        )
        if out and not out.startswith("LLM endpoint failed"):
            return out

    items = []

    if "std::thread" in code:
        items.append("Creating threads per packet/job is expensive. Use a thread pool or job system.")

    if "std::vector<Packet*>" in code:
        items.append("Vector of raw pointers causes cache misses and ownership complexity. Prefer value storage, object pools, or `unique_ptr`.")

    if "std::cout" in code:
        items.append("Console logging inside hot paths can stall frames. Use async logging with levels.")

    if "memcpy" in code:
        items.append("Copying entire packet buffers can be acceptable, but avoid unnecessary copies and validate packet size first.")

    if not items:
        items.append("Profile CPU time, allocations, lock contention, and packet processing latency under load.")

    return "## Performance Agent\n\n" + "\n".join(f"- {i}" for i in items)


def test_planner_agent(code, use_llm=False):
    if use_llm:
        out = call_llm(
            "You are a test engineering agent for C++ multiplayer engines. Return concise Markdown.",
            "Generate a practical test plan for this C++ code. Include unit, integration, fuzz, load, and concurrency tests:\n\n" + code[:12000],
        )
        if out and not out.startswith("LLM endpoint failed"):
            return out

    return """
## Test Planner Agent

Recommended tests:

- **Bounds test:** send packets smaller/larger than `sizeof(Packet)` and verify safe rejection.
- **Replay test:** send duplicate and out-of-order sequence numbers.
- **Multi-client test:** verify each player has independent sequence tracking.
- **Race test:** call `receive()` and `process()` concurrently under ThreadSanitizer.
- **Lifetime test:** ensure detached/asynchronous jobs never access freed packet memory.
- **Load test:** simulate thousands of packets per second and measure frame-time impact.
- **Fuzz test:** mutate packet bytes and confirm the server never crashes.
"""


def summary_agent(parts, use_llm=False):
    joined = "\n\n".join(parts.values())

    if use_llm:
        out = call_llm(
            "You are an executive technical summarizer. Return concise Markdown.",
            "Summarize this multi-agent code review into top risks, fixes, and business value:\n\n" + joined[:12000],
        )
        if out and not out.startswith("LLM endpoint failed"):
            return out

    return """
## Executive Summary Agent

PatchPilot found risks commonly seen in real-time C++ multiplayer systems:

1. **Memory and lifetime risk** from raw pointers, detached threads, and unclear ownership.
2. **Networking correctness risk** from packet deserialization, global sequence tracking, and insufficient client validation.
3. **Performance risk** from per-packet thread creation, console logging in hot paths, and pointer-heavy containers.

### Suggested fix strategy

- Replace raw packet pointers with RAII ownership or value/object-pool storage.
- Validate packet size and schema before copying/deserializing.
- Track sequence numbers per player/session.
- Replace detached threads with a job system/thread pool.
- Add fuzz, race, replay, and load tests.

### Business value

This reduces multiplayer crashes, cheating surface, desync bugs, and frame-time spikes before launch.
"""


def run_patchpilot(code, use_llm=False):
    parts = {
        "bugs": bug_hunter_agent(code, use_llm),
        "networking": networking_agent(code, use_llm),
        "performance": performance_agent(code, use_llm),
        "tests": test_planner_agent(code, use_llm),
    }

    summary = summary_agent(parts, use_llm)

    full_report = (
        "# PatchPilot AI Code Review Report\n\n"
        + summary
        + "\n\n"
        + parts["bugs"]
        + "\n\n"
        + parts["networking"]
        + "\n\n"
        + parts["performance"]
        + "\n\n"
        + parts["tests"]
    )

    return {
        "summary": summary,
        "bugs": parts["bugs"],
        "networking": parts["networking"],
        "performance": parts["performance"],
        "tests": parts["tests"],
        "full_report": full_report,
    }


st.set_page_config(page_title="PatchPilot AI", page_icon="🛠️", layout="wide")

st.title("🛠️ PatchPilot AI")
st.subheader("Agentic debugging copilot for C++ game engine and multiplayer code")

with st.sidebar:
    st.header("Settings")
    use_llm = st.toggle("Use optional LLM endpoint", value=False)
    st.caption("If off, PatchPilot uses a deterministic fallback analyzer, so the demo works without API keys.")
    st.divider()
    st.markdown("### Optional LLM env vars")
    st.code("PATCHPILOT_LLM_BASE_URL\nPATCHPILOT_LLM_API_KEY\nPATCHPILOT_LLM_MODEL")

st.markdown(
    """
PatchPilot AI reviews C++ multiplayer/game-engine code using multiple specialized agents:

- Bug Hunter Agent
- Networking Agent
- Performance Agent
- Test Planner Agent
- Executive Summary Agent
"""
)

uploaded = st.file_uploader(
    "Upload C++ source/header files",
    type=["cpp", "h", "hpp", "cc", "cxx", "txt", "md"],
    accept_multiple_files=True,
)

use_sample = st.checkbox("Use included sample multiplayer code", value=True)

code_parts = []

if use_sample:
    code_parts.append("// FILE: sample_netcode.cpp\n" + SAMPLE_CPP)

for file in uploaded or []:
    text = file.read().decode("utf-8", errors="replace")
    code_parts.append(f"// FILE: {file.name}\n{text}")

code = "\n\n".join(code_parts)

if code:
    with st.expander("Preview input", expanded=False):
        st.code(code[:6000], language="cpp")

if st.button("Run AI Agent Review", type="primary", disabled=not bool(code)):
    with st.spinner("PatchPilot agents are reviewing your code..."):
        report = run_patchpilot(code, use_llm=use_llm)

    st.success("Review complete")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Summary", "Bugs", "Networking", "Performance", "Tests"]
    )

    with tab1:
        st.markdown(report["summary"])

    with tab2:
        st.markdown(report["bugs"])

    with tab3:
        st.markdown(report["networking"])

    with tab4:
        st.markdown(report["performance"])

    with tab5:
        st.markdown(report["tests"])

    st.download_button(
        "Download Markdown Report",
        data=report["full_report"],
        file_name="patchpilot_report.md",
        mime="text/markdown",
    )

st.divider()
st.caption("PatchPilot AI — built for AMD Developer Hackathon.")
