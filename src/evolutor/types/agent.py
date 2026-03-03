from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    planner = "planner"
    worker = "worker"
    critic = "critic"
    meta_improver = "meta_improver"


class MessageType(str, Enum):
    instruction = "instruction"
    result = "result"
    feedback = "feedback"
    escalation = "escalation"


class AgentState(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: AgentRole
    task_id: str | None = None
    iteration: int = 0
    context: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = False


class AgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: AgentRole
    receiver: AgentRole
    content: str
    task_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_type: MessageType = MessageType.instruction
