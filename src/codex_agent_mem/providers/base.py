from __future__ import annotations

from typing import Protocol

from codex_agent_mem.models import GenericEventEnvelope, Observation


class Summarizer(Protocol):
    def summarize_turn(self, event: GenericEventEnvelope) -> str: ...
    def extract_observations(self, event: GenericEventEnvelope) -> list[Observation]: ...
