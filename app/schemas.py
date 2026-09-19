from datetime import date, datetime, timezone
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

SupportKey = Literal['PUBLIC_DEFINITION','ACCOUNT_STATUS','ACCOUNT_BALANCE',
    'RISK_LEVEL','HOLDING_LIST','ORDER_STATUS','ORDER_REASON','ORDER_RULE',
    'PROFILE','QUALIFICATION_RULE']
AnswerabilityStatus = Literal['sufficient','missing_user_information',
    'missing_business_evidence','conflicting_evidence','expired_or_unusable_evidence',
    'unauthorized','unsafe','out_of_scope']

class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str = Field(min_length=1)
    kind: Literal['business_fact','knowledge']
    source: str
    source_id: str = Field(min_length=1)
    version: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    audience: Literal['public','private','staff']
    scope: str
    content: dict[str, Any]
    verified: bool = False
    supports: list[SupportKey] = Field(default_factory=list)
    entity_binding: dict[str, str] = Field(default_factory=dict)
    conflict_key: str
    model_config = ConfigDict(extra='forbid')

class AnswerabilityDecision(BaseModel):
    task_id: str
    status: AnswerabilityStatus
    required_supports: list[SupportKey] = Field(default_factory=list)
    satisfied_supports: list[SupportKey] = Field(default_factory=list)
    missing_supports: list[SupportKey] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    next_action: Literal['answer','clarify','retrieve','reject','handoff']
    reason_code: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
    evidence: list[Evidence] = Field(default_factory=list)
    answerability: AnswerabilityDecision | None = None
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
    answerability: AnswerabilityDecision | None = None
