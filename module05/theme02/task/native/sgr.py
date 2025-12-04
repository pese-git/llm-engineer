from typing import Any, Dict, Optional, Union, Literal
from pydantic import BaseModel, Field

class AskAgent(BaseModel):
    action: Literal["ask_agent"] = "ask_agent"
    target: Literal["planner", "coder", "tester", "reviewer"]
    message: str

class UseTool(BaseModel):
    action: Literal["use_tool"] = "use_tool"
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)

class Reply(BaseModel):
    action: Literal["reply"] = "reply"
    content: str

class Finish(BaseModel):
    action: Literal["finish"] = "finish"
    summary: str

class AgentStep(BaseModel):
    step: Union[AskAgent, UseTool, Reply, Finish]

class BusMessage(BaseModel):
    sender: str
    recipient: str  # имя агента или "broadcast"
    content: str
    meta: Optional[Dict[str, Any]] = None
