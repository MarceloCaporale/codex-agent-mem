from __future__ import annotations

import re

from codex_agent_mem.models import GenericEventEnvelope, Observation

DECISION_PATTERNS = [
    re.compile(r"^\s*(?:decision|decisión|resolved|resolution)\s*[:\-]\s*(.+)$", re.IGNORECASE),
    re.compile(r"^\s*[-*]\s*(?:decision|decisión)\s*[:\-]\s*(.+)$", re.IGNORECASE),
]


class HeuristicSummarizer:
    def summarize_turn(self, event: GenericEventEnvelope) -> str:
        intent = " | ".join(event.input_messages[-2:]).strip() or "No user message"
        assistant = event.assistant_message.strip().replace("\n", " ")
        if len(assistant) > 400:
            assistant = assistant[:397] + "..."
        return f"{intent} -> {assistant}".strip()

    def extract_observations(self, event: GenericEventEnvelope) -> list[Observation]:
        observations: list[Observation] = [
            Observation(
                type="session_summary",
                title=f"{event.runtime} turn summary",
                summary=self.summarize_turn(event),
                detail=event.assistant_message[:8000],
                confidence=0.45,
                importance=2,
                status="snapshot",
            )
        ]
        for line in event.assistant_message.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            for pattern in DECISION_PATTERNS:
                match = pattern.match(candidate)
                if match:
                    decision = match.group(1).strip()
                    observations.append(
                        Observation(
                            type="decision",
                            title=f"Decision: {decision[:72]}",
                            summary=decision,
                            detail=event.assistant_message[:8000],
                            confidence=0.75,
                            importance=4,
                            status="active",
                        )
                    )
                    break
        return observations
