from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeKind(str, Enum):
    module = "module"
    cls = "class"
    function = "function"
    variable = "variable"
    import_ = "import"


class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = ""


class KnowledgeNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: NodeKind
    name: str
    file_path: str
    start_line: int = 0
    end_line: int = 0
    signature: str = ""
    docstring: str = ""
    children: list[str] = Field(default_factory=list)
    edges: list[str] = Field(default_factory=list)


class Playbook(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: str | None = None
    name: str
    language: str
    content: str
    helpful_count: int = 0
    harmful_count: int = 0
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def score(self) -> float:
        total = self.helpful_count + self.harmful_count
        if total == 0:
            return 0.5
        return self.helpful_count / total
