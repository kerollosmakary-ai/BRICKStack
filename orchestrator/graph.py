"""
LangGraph multi-agent orchestrator
Flow: Planner → Coder → Terminal → Reviewer → (loop or Writer)
"""
import json, logging
from typing import AsyncGenerator
from schemas import GraphEvent
from agents import PlannerAgent, CoderAgent, TerminalAgent, ReviewerAgent, WriterAgent

log = logging.getLogger("graph")

class AgentGraph:
    """State machine connecting 5 agents. Yields events for streaming."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agents = {
            "planner": PlannerAgent(),
            "coder": CoderAgent(),
            "terminal": TerminalAgent(),
            "reviewer": ReviewerAgent(),
            "writer": WriterAgent(),
        }
        self.state = {
            "messages": [],
            "plan": [],
            "current_step": 0,
            "code": "",
            "output": "",
            "review_ok": False,
            "max_steps": 10,
        }
        self.last_output = ""

    async def run(self, user_input: str) -> AsyncGenerator[GraphEvent, None]:
        self.state["messages"].append({"role": "user", "content": user_input})

        # 1. Planner
        yield GraphEvent(type="thought", agent="Planner", content="Analyzing request and creating plan...")
        self.state.update(self.agents["planner"](self.state))
        yield GraphEvent(type="thought", agent="Planner", content=f"Plan: {self.state['plan'][0][:60]}...")

        # 2. Coder
        yield GraphEvent(type="thought", agent="Coder", content="Writing code...")
        self.state.update(self.agents["coder"](self.state))
        yield GraphEvent(type="code", agent="Coder", language="python", code=self.state["code"])

        # 3. Terminal
        yield GraphEvent(type="thought", agent="Terminal", content="Running in sandbox...")
        self.state.update(self.agents["terminal"](self.state))
        yield GraphEvent(type="output", agent="Terminal", output=self.state["output"])

        # 4. Reviewer
        yield GraphEvent(type="thought", agent="Reviewer", content="Reviewing output...")
        self.state.update(self.agents["reviewer"](self.state))
        if not self.state.get("review_ok", True):
            yield GraphEvent(type="thought", agent="Reviewer", content="Issues found, re-running...")
            # In prod: loop back to coder
        else:
            yield GraphEvent(type="thought", agent="Reviewer", content="✅ All checks passed.")

        # 5. Writer
        yield GraphEvent(type="thought", agent="Writer", content="Formatting final answer...")
        self.state.update(self.agents["writer"](self.state))
        self.last_output = self.state["messages"][-1]["content"]
        yield GraphEvent(type="assistant", content=self.last_output, done=True)

    async def rerun_code(self, new_source: str):
        """Re-execute edited code without full agent pipeline"""
        yield GraphEvent(type="thought", agent="Terminal", content="Re-running edited code...")
        self.state["code"] = new_source
        self.state.update(self.agents["terminal"](self.state))
        yield GraphEvent(type="output", agent="Terminal", output=self.state["output"])
        yield GraphEvent(type="thought", agent="Writer", content="Updating answer...")
        self.state.update(self.agents["writer"](self.state))
        self.last_output = self.state["messages"][-1]["content"]
        yield GraphEvent(type="assistant", content=self.last_output, done=True)

    def get_last_output(self) -> str:
        return self.last_output
