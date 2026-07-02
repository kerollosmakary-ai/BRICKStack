"""
Message & State schemas for the multi-agent graph
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal

class Message(BaseModel):
    role: Literal["user", "assistant", "system", "agent"]
    content: str
    agent: Optional[str] = None
    metadata: dict = {}

class ToolCall(BaseModel):
    name: str
    args: dict = {}

class AgentState(BaseModel):
    messages: list[Message] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    current_step: int = 0
    code: str = ""
    output: str = ""
    review_ok: bool = False
    max_steps: int = 10

class GraphEvent(BaseModel):
    type: str
    content: str = ""
    agent: Optional[str] = None
    language: Optional[str] = None
    code: Optional[str] = None
    output: Optional[str] = None
    done: bool = False
    chunk: Optional[str] = None  # streaming token
