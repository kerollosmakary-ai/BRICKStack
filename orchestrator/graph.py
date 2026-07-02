import asyncio
from typing import AsyncGenerator, Dict, Any
from .agents import planner_agent, coder_agent, terminal_agent, reviewer_agent, writer_agent, handle_edit
from .schemas import GraphEvent
from .llm import LLMClient

class GraphRunner:
    def __init__(self, state: Dict[str, Any]):
        self.state = state
        self.agents = {
            "planner": planner_agent,
            "coder": coder_agent,
            "terminal": terminal_agent,
            "reviewer": reviewer_agent,
            "writer": writer_agent,
        }

    async def step(self, agent_name: str) -> AsyncGenerator[Dict[str, Any], None]:
        agent = self.agents[agent_name]
        async for event in agent(self.state):
            yield event
        yield {"type": "thought", "content": f"{agent_name} finished", "agent": agent_name, "task_id": self.state["task_id"]}

    async def run_pipeline(self) -> AsyncGenerator[Dict[str, Any], None]:
        for name in ["planner", "coder", "terminal", "reviewer", "writer"]:
            async for event in self.step(name):
                yield event

    async def handle_edit(self, updated_code: str) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in handle_edit(self.state, updated_code):
            yield event

async def run_graph(state: Dict[str, Any]) -> AsyncGenerator[GraphEvent, None]:
    runner = GraphRunner(state)
    async for event in runner.run_pipeline():
        yield GraphEvent(**event)

async def run_edit(state: Dict[str, Any], updated_code: str) -> AsyncGenerator[GraphEvent, None]:
    runner = GraphRunner(state)
    async for event in runner.handle_edit(updated_code):
        yield GraphEvent(**event)
