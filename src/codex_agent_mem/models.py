from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), str):
            return value["content"]
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


class GenericEventEnvelope(BaseModel):
    runtime: str
    project_key: str
    session_id: str
    turn_id: str
    cwd: str | None = None
    timestamp: str
    input_messages: list[str] = Field(default_factory=list)
    assistant_message: str = ""
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input_messages", mode="before")
    @classmethod
    def normalize_input_messages(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            return [_to_text(value)]
        return [_to_text(item) for item in value if _to_text(item)]

    @field_validator("assistant_message", mode="before")
    @classmethod
    def normalize_assistant_message(cls, value: Any) -> str:
        return _to_text(value)


class Observation(BaseModel):
    type: str
    title: str
    summary: str
    detail: str = ""
    confidence: float = 0.5
    importance: int = 2
    status: str = "snapshot"
    files: list[str] = Field(default_factory=list)
