from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

class TaskStatus(str, Enum):
    NEW='new'
    CLARIFYING='clarifying'
    EXECUTING='executing'
    COMPLETED='completed'
    HANDOFF='handoff'
    REJECTED='rejected'
    ABANDONED='abandoned'

class EntityValue(BaseModel):
    name: str = Field(min_length=1)
    value: Any
    source: Literal['user','system','tool']
    confirmed: bool = False
    model_config = ConfigDict(extra='forbid')

class TaskState(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    task_type: str = Field(default='unknown', min_length=1)
    domain: str | None = None
    objective: str = ''
    entities: dict[str, EntityValue] = Field(default_factory=dict)
    required_slots: list[str] = Field(default_factory=list)
    missing_slots: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.NEW
    clarification_count: int = Field(default=0, ge=0)
    completion_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = ConfigDict(extra='forbid')

class SessionState(BaseModel):
    session_id: str = Field(min_length=1)
    user_id: str | None = None
    authenticated: bool = False
    messages: list[dict[str, Any]] = Field(default_factory=list)
    pending_slots: dict[str, Any] = Field(default_factory=dict)
    active_task: TaskState | None = None
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
