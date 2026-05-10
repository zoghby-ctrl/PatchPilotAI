import os
import re
import requests
import streamlit as st

SAMPLES = {
    "Python": """
def divide_scores(scores):
    total = 0
    for s in scores:
        total += s
    return total / len(scores)

user_input = input("Enter expression: ")
print(eval(user_input))
""",
    "JavaScript": """
function renderUser(user) {
  document.getElementById('name').innerHTML = user.name;
}

async function loadUsers(ids) {
  let users = [];
  ids.forEach(async id => {
    const res = await fetch('/api/users/' + id);
    users.push(await res.json());
  });
  return users;
}
""",
    "C++": """
#include <vector>
#include <cstring>
#include <thread>

void copyPacket(char* data, int size) {
    char buffer[256];
    memcpy(buffer, data, size);
    int* value = new int(42);
    std::thread t([&]() { *value += 1; });
    t.detach();
}
""",
    "Java": """
import java.sql.*;

public class UserRepo {
    public ResultSet getUser(Connection conn, String id) throws Exception {
        String sql = "SELECT * FROM users WHERE id = " + id;
        Statement st = conn.createStatement();
        return st.executeQuery(sql);
    }
}
""",
    "C#": """
using System;
using System.Data.SqlClient;

class UserRepo {
    public void GetUser(SqlConnection conn, string id) {
        var cmd = new SqlCommand("SELECT * FROM Users WHERE Id = " + id, conn);
        var reader = cmd.ExecuteReader();
        Console.WriteLine(reader["Name"]);
    }
}
"""
}

SUPPORTED_EXTS = {
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".h": "C++", ".hpp": "C++",
    ".java": "Java",
    ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".py": "Python",
    ".cs": "C#",
    ".txt": "Text", ".md": "Markdown"
}


def detect_language(filename, code):
    ext = os.path.splitext(filename.lower())[1]
    if ext in SUPPORTED_EXTS:
        return SUPPORTED_EXTS[ext]
    if "#include" in code or "std::" in code: return "C++"
    if "public class" in code and "System." in code: return "C#"
    if "public class" in code or "import java" in code: return "Java"
    if "def " in code or "import " in code: return "Python"
    if "function " in code or "console.log" in code or "=>" in code: return "JavaScript"
    return "Unknown"


def call_model(system_prompt, user_prompt, api_key, model, base_url):
    if not api_key:
        return None
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.15,
        "max_tokens": 1600,
    }
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Model call failed, using fallback analysis. Error: {e}"


def line_hits(code, patterns):
    out = []
    for i, line in enumerate(code.splitlines(), 1):
        for severity, label, pattern, fix in patterns:
            if re.search(pattern, line):
                out.append((i, severity, label, line.strip(), fix))
    return out


def language_agent(files):
    md = "## Language & Structure Agent\n\n"
    langs = {}
    total_lines = 0
    for name, code, lang in files:
        lines = len(code.splitlines())
        total_lines += lines
        langs[lang] = langs.get(lang, 0) + 1
        md += f"- `{name}`: detected **{lang}**, {lines} lines.\n"
    md += f"\n**Total files:** {len(files)}  \n**Total lines:** {total_lines}  \n"
    md += "**Languages detected:** " + ", ".join(f"{k} ({v})" for k, v in langs.items()) + "\n"
    return md


def fallback_agent(title, files, patterns, extra_notes=None):
    md = f"## {title}\n\n"
    any_hit = False
    for name, code, lang in files:
        hits = line_hits(code, patterns)
        if hits:
            any_hit = True
            md += f"### {name} ({lang})\n"
            for line, severity, label, src, fix in hits:
                md += f"- **{severity} | Line {line}: {label}**\n"
                md += f"  ```text\n  {src}\n  ```\n"
                md += f"  **Suggested fix:** {fix}\n\n"
    if not any_hit:
        md += "No high-confidence pattern-based findings in this category. Consider enabling model mode for deeper semantic analysis.\n"
    if extra_notes:
        md += "\n### General guidance\n" + "\n".join(f"- {n}" for n in extra_notes) + "\n"
    return md


def run_fallback(files):
    bug_patterns = [
        ("High", "Possible division by zero / empty collection", r"/\s*len\(|/\s*0|/\s*\w+\.length|/\s*\w+\.Count", "Validate denominator and handle empty collections before division."),
        ("High", "Unsafe memory copy or raw buffer operation", r"\bmemcpy\b|\bstrcpy\b|\bsprintf\b", "Check bounds, prefer safer APIs, and validate input size."),
        ("Medium", "Raw allocation / manual memory management", r"\bnew\b|\bdelete\b|malloc\s*\(", "Use RAII/smart pointers or managed containers where possible."),
        ("Medium", "Detached thread / async lifetime risk", r"\.detach\s*\(|async\s+|Task\.Run", "Ensure referenced data outlives async work; prefer structured concurrency or cancellation."),
        ("Medium", "Broad exception handling or missing error handling", r"catch\s*\(|except\s*:", "Catch specific exceptions and return useful errors."),
    ]
    security_patterns = [
        ("Critical", "Code execution from user input", r"\beval\s*\(|\bexec\s*\(|Function\s*\(", "Never execute raw user input. Use parsers, validation, or allowlists."),
        ("Critical", "SQL injection risk via string concatenation", r"SELECT .*\+|INSERT .*\+|UPDATE .*\+|DELETE .*\+|SqlCommand\(.*\+|executeQuery\(.*\+", "Use parameterized queries/prepared statements."),
        ("High", "DOM XSS risk", r"innerHTML\s*=|document\.write\s*\(", "Use textContent or sanitize trusted HTML carefully."),
        ("High", "Shell command injection risk", r"os\.system\s*\(|subprocess\.|Runtime\.getRuntime\(\)\.exec|ProcessStartInfo", "Avoid shell=True and pass arguments as arrays with validation."),
        ("Medium", "Hardcoded secret-like value", r"api[_-]?key\s*=|password\s*=|secret\s*=|token\s*=", "Move secrets to environment variables or secret managers."),
    ]
    perf_patterns = [
        ("Medium", "Potential inefficient nested loop", r"for .*:\s*$|for\s*\(.*;.*;.*\)", "Check algorithmic complexity; avoid accidental O(n²) on large inputs."),
        ("Medium", "Per-item async bug / not awaited properly", r"forEach\s*\(\s*async|map\s*\(\s*async", "Use Promise.all or for...of with await depending on desired concurrency."),
        ("Medium", "Hot-path console/log output", r"console\.log|System\.out\.println|Console\.WriteLine|std::cout|print\s*\(", "Avoid noisy logging in performance-sensitive paths; use structured log levels."),
        ("Medium", "Thread creation in local code path", r"std::thread|new Thread|Thread\(|Task\.Run", "Use a pool/job queue for high-frequency work."),
    ]
    refactor_patterns = [
        ("Low", "Magic number", r"\b(256|1024|1000|9999)\b", "Replace magic numbers with named constants."),
        ("Low", "Long conditional / possible readability issue", r"if\s*\(.*&&.*\)|if\s+.* and .*", "Extract condition into named boolean or helper function."),
        ("Low", "Mutable global/shared structure", r"static |global |public static|var .* = \[\]|let .* = \[\]", "Minimize shared mutable state and define ownership clearly."),
    ]
    parts = {
        "language": language_agent(files),
        "bugs": fallback_agent("Bug & Correctness Agent", files, bug_patterns, ["Add validation around inputs and boundary conditions.", "Prefer explicit ownership and deterministic cleanup."]),
        "security": fallback_agent("Security Agent", files, security_patterns, ["Treat all external input as untrusted.", "Use parameterized queries and output encoding."]),
        "performance": fallback_agent("Performance & Complexity Agent", files, perf_patterns, ["Measure before optimizing; profile CPU, memory, I/O, and network calls.", "Check Big-O complexity for loops over large collections."]),
        "refactor": fallback_agent("Refactor Agent", files, refactor_patterns, ["Improve naming, isolate side effects, and break large functions into testable units."]),
    }
    parts["tests"] = """## Test Planner Agent

Recommended tests:

- **Unit tests:** normal cases, edge cases, null/empty input, invalid input.
- **Regression tests:** reproduce each detected bug pattern before fixing it.
- **Security tests:** injection strings, script payloads, malformed data, permission checks.
- **Performance tests:** large input sizes, repeated calls, concurrency/load scenarios.
- **Property/fuzz tests:** random inputs to verify invariants and crash resistance.
- **Integration tests:** verify external APIs, databases, and file/network boundaries.
"""
    parts["summary"] = """## Executive Summary Agent

PatchPilot AI reviewed the uploaded code through a generic multi-language agentic workflow.

### Key outcomes

- Identifies likely correctness bugs and unsafe patterns.
- Flags common security risks such as injection, unsafe evaluation, XSS, and command execution.
- Highlights performance and complexity risks that can affect simple scripts or large systems.
- Produces practical refactoring suggestions and a test plan.

### Best next step

Fix Critical/High findings first, add regression tests for each fix, then use the performance and refactor sections to improve maintainability.
"""
    return parts


def run_model_review(files, api_key, model, base_url):
    combined = "\n\n".join([f"// FILE: {name} | LANGUAGE: {lang}\n{code}" for name, code, lang in files])
    system = """
You are PatchPilot AI, a senior multi-language code review and debugging system.
Review C++, Java, JavaScript/TypeScript, Python, and C# code.
Be practical, specific, and structured. Do not invent line numbers if uncertain.
Return Markdown with these sections:
1. Executive Summary
2. Language & Structure
3. Bug & Correctness Findings
4. Security Findings
5. Performance & Complexity Findings
6. Refactor Recommendations
7. Test Plan
8. Priority Fix Roadmap
"""
    user = "Review this code for both simple and complex issues. Focus on actionable fixes.\n\n" + combined[:50000]
    out = call_model(system, user, api_key, model, base_url)
    if out and not out.startswith("Model call failed"):
        return {"model_report": out, "full_report": "# PatchPilot AI Model-Powered Review\n\n" + out}
    fallback = run_fallback(files)
    fallback["summary"] = fallback.get("summary", "") + f"\n\n> Model mode was requested but failed or was unavailable. Fallback analyzer was used.\n\n{out or ''}"
    return fallback


def build_full_report(parts):
    if "model_report" in parts:
        return parts["full_report"]
    order = ["summary", "language", "bugs", "security", "performance", "refactor", "tests"]
    return "# PatchPilot AI Code Review Report\n\n" + "\n\n".join(parts[k] for k in order if k in parts)


st.set_page_config(page_title="PatchPilot AI", page_icon="🛠️", layout="wide")
st.title("🛠️ PatchPilot AI")
st.subheader("Generic agentic code review, debugging, security, performance, and test-planning copilot")

with st.sidebar:
    st.header("Model Settings")
    use_model = st.toggle("Use OpenAI-compatible model", value=False)
    api_key = st.text_input("API key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    model = st.text_input("Model", value=os.getenv("PATCHPILOT_MODEL", "gpt-5.5"))
    base_url = st.text_input("Base URL", value=os.getenv("PATCHPILOT_LLM_BASE_URL", "https://api.openai.com/v1"))
    st.caption("No key? Keep model mode off. The fallback analyzer still works.")

st.markdown("""
PatchPilot AI is now **generic**: it can review **simple scripts** and **complex systems** across:

**C++ · Java · JavaScript/TypeScript · Python · C#**
""")

sample_choice = st.selectbox("Optional sample code", ["None"] + list(SAMPLES.keys()), index=1)
uploaded = st.file_uploader(
    "Upload code files",
    type=["cpp", "cc", "cxx", "h", "hpp", "java", "js", "jsx", "ts", "tsx", "py", "cs", "txt", "md"],
    accept_multiple_files=True,
)

files = []
if sample_choice != "None":
    name = f"sample.{ {'Python':'py','JavaScript':'js','C++':'cpp','Java':'java','C#':'cs'}[sample_choice] }"
    files.append((name, SAMPLES[sample_choice], sample_choice))

for f in uploaded or []:
    code = f.read().decode("utf-8", errors="replace")
    files.append((f.name, code, detect_language(f.name, code)))

if files:
    with st.expander("Preview input", expanded=False):
        for name, code, lang in files:
            st.markdown(f"**{name}** — detected `{lang}`")
            st.code(code[:5000])

if st.button("Run PatchPilot Review", type="primary", disabled=not bool(files)):
    with st.spinner("PatchPilot agents are reviewing your code..."):
        if use_model and api_key:
            parts = run_model_review(files, api_key, model, base_url)
        else:
            parts = run_fallback(files)
        full = build_full_report(parts)

    st.success("Review complete")

    if "model_report" in parts:
        st.markdown(parts["model_report"])
    else:
        tabs = st.tabs(["Summary", "Languages", "Bugs", "Security", "Performance", "Refactor", "Tests"])
        keys = ["summary", "language", "bugs", "security", "performance", "refactor", "tests"]
        for tab, key in zip(tabs, keys):
            with tab:
                st.markdown(parts[key])

    st.download_button("Download Markdown Report", data=full, file_name="patchpilot_report.md", mime="text/markdown")
else:
    st.info("Pick a sample or upload files, then run the review.")

st.divider()
st.caption("PatchPilot AI — generic multi-language agentic code review copilot built for the AMD Developer Hackathon.")
