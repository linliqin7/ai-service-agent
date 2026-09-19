from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class SessionState(BaseModel):
    session_id: str = Field(min_length=1)
    user_id: str | None = None
    authenticated: bool = False
    messages: list[dict[str, Any]] = Field(default_factory=list)
    pending_slots: dict[str, Any] = Field(default_factory=dict)
    loop_steps: int = Field(default=0, ge=0)
    traces: list["TraceEvent"] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")

class TraceEvent(BaseModel):
    type: str = Field(min_length=1)
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime

class AgentResponse(BaseModel):
    answer: str
    intent: str = "unknown"
    trace_id: str = ""
    observations: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    trace: list[TraceEvent] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    handoff: dict[str, Any] | None = None
