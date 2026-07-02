"""
5 Agent definitions for the LangGraph orchestrator

Agent      Job                                    Tools
──────────────────────────────────────────────────────────
Planner    Break task into steps                   None (thinks)
Coder      Write/edit code                         write_file, read_file
Terminal   Run commands in sandbox PTY             run_command
Reviewer   Check code quality + safety             None (thinks)
Writer     Format final markdown answer            None (thinks)
"""
import logging
log = logging.getLogger("agents")

# ── Planner ──

class PlannerAgent:
    def __call__(self, state):
        task = state["messages"][-1]["content"] if state["messages"] else ""
        log.info(f"Planner: planning for: {task[:50]}...")
        # In prod: call LLM to generate steps
        plan = [
            f"Write code for: {task}",
            "Terminal: execute the code",
            "Reviewer: check the output",
            "Writer: format the answer"
        ]
        return {"plan": plan, "current_step": 0}

# ── Coder ──

class CoderAgent:
    def __call__(self, state):
        step = state["plan"][state["current_step"]] if state["plan"] else ""
        log.info(f"Coder: executing step: {step[:40]}...")
        code = """import os, sys

def main():
    path = "."
    files = [f for f in os.listdir(path) if os.path.isfile(f)]
    print(f"Found {len(files)} files")
    for f in files:
        size = os.path.getsize(f)
        print(f"  {f} ({size} bytes)")

if __name__ == "__main__":
    main()
"""
        return {"code": code}

# ── Terminal ──

class TerminalAgent:
    def __call__(self, state):
        code = state.get("code", "")
        log.info("Terminal: executing code in sandbox...")
        # In prod: run in Docker PTY
        output = "Found 8 files\n  main.py (320 bytes)\n  app.py (1200 bytes)\n  style.css (6200 bytes)\n  app.js (9800 bytes)\n  requirements.txt (450 bytes)\n  Dockerfile (280 bytes)\n  README.md (1440 bytes)\n  config.json (180 bytes)"
        return {"output": output}

# ── Reviewer ──

class ReviewerAgent:
    def __call__(self, state):
        output = state.get("output", "")
        log.info("Reviewer: checking output...")
        # In prod: LLM checks for errors, safety
        issues = []
        if not output:
            issues.append("No output produced")
        if "error" in output.lower():
            issues.append("Errors detected")
        return {"review_ok": len(issues) == 0}

# ── Writer ──

class WriterAgent:
    def __call__(self, state):
        code = state.get("code", "")
        output = state.get("output", "")
        log.info("Writer: formatting answer...")
        markdown = f"""Here's the result:

```python
{code}
```

**Output:**
```
{output}
```

The script counts files in the current directory using `os.listdir()` and `os.path.isfile()`.
"""
        return {"messages": [{"role": "assistant", "content": markdown}]}
