from __future__ import annotations

import re

from codex_agent_mem.models import GenericEventEnvelope, Observation
from codex_agent_mem.operational_state import normalize_state_text

DECISION_PATTERNS = [
    re.compile(r"^\s*(?:decision|decisión|resolved|resolution)\s*[:\-]\s*(.+)$", re.IGNORECASE),
    re.compile(r"^\s*[-*]\s*(?:decision|decisión)\s*[:\-]\s*(.+)$", re.IGNORECASE),
]

OBJECTIVE_PATTERNS = [
    re.compile(r"^\s*(?:objective|goal|target|mission)\s*[:\-]\s*(.+)$", re.IGNORECASE),
]
CONSTRAINT_PATTERNS = [
    re.compile(r"^\s*(?:constraint|restriction|rule)\s*[:\-]\s*(.+)$", re.IGNORECASE),
]
PENDING_PATTERNS = [
    re.compile(r"^\s*(?:pending|todo|to do|remaining|open item)\s*[:\-]\s*(.+)$", re.IGNORECASE),
]
COMPLETED_PATTERNS = [
    re.compile(r"^\s*(?:done|completed|finished)\s*[:\-]\s*(.+)$", re.IGNORECASE),
]
BLOCKER_PATTERNS = [
    re.compile(r"^\s*(?:blocker|blocked|risk)\s*[:\-]\s*(.+)$", re.IGNORECASE),
]
COMPLETION_CLAIM_PATTERNS = [
    re.compile(r"^\s*(?:status)\s*[:\-]\s*(?:done|complete|completed|finished)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:we are|we're|it is)\s+(?:done|finished|complete(?:d)?)\s*$", re.IGNORECASE),
]


class HeuristicSummarizer:
    def summarize_turn(self, event: GenericEventEnvelope) -> str:
        intent = " | ".join(event.input_messages[-2:]).strip() or "No user message"
        assistant = event.assistant_message.strip().replace("\n", " ")
        if len(assistant) > 400:
            assistant = assistant[:397] + "..."
        return f"{intent} -> {assistant}".strip()

    @staticmethod
    def _candidate_segments(text: str) -> list[str]:
        segments: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            parts = [part.strip() for part in re.split(r"\s*;\s*", stripped) if part.strip()]
            segments.extend(parts or [stripped])
        return segments

    def _operation_observation(self, *, kind: str, text: str, detail: str, importance: int, confidence: float) -> Observation:
        label_map = {
            "objective": "Objective",
            "user_request": "User request",
            "constraint": "Constraint",
            "pending_item": "Pending",
            "completed_item": "Completed",
            "blocker": "Blocker",
            "completion_claim": "Completion claim",
        }
        label = label_map[kind]
        return Observation(
            type=kind,
            title=f"{label}: {text[:72]}",
            summary=text,
            detail=detail[:8000],
            confidence=confidence,
            importance=importance,
            status="active",
        )

    def _extract_from_lines(
        self,
        text: str,
        *,
        source_kind: str,
        detail: str,
    ) -> list[Observation]:
        observations: list[Observation] = []
        seen: set[tuple[str, str]] = set()
        pattern_specs = [
            ("objective", OBJECTIVE_PATTERNS, 4, 0.72),
            ("constraint", CONSTRAINT_PATTERNS, 4, 0.7),
            ("pending_item", PENDING_PATTERNS, 5, 0.74),
            ("completed_item", COMPLETED_PATTERNS, 3, 0.7),
            ("blocker", BLOCKER_PATTERNS, 5, 0.78),
        ]
        for candidate in self._candidate_segments(text):
            if not candidate:
                continue
            for kind, patterns, importance, confidence in pattern_specs:
                matched = False
                for pattern in patterns:
                    match = pattern.match(candidate)
                    if not match:
                        continue
                    value = match.group(1).strip()
                    norm = normalize_state_text(value)
                    dedupe_key = (kind, norm)
                    if value and dedupe_key not in seen:
                        observations.append(
                            self._operation_observation(
                                kind=kind,
                                text=value,
                                detail=detail,
                                importance=importance,
                                confidence=confidence,
                            )
                        )
                        seen.add(dedupe_key)
                    matched = True
                    break
                if matched:
                    break
            else:
                for pattern in COMPLETION_CLAIM_PATTERNS:
                    if pattern.match(candidate):
                        norm = normalize_state_text(candidate)
                        dedupe_key = ("completion_claim", norm)
                        if dedupe_key not in seen:
                            observations.append(
                                self._operation_observation(
                                    kind="completion_claim",
                                    text="assistant claimed the work was complete",
                                    detail=detail,
                                    importance=5,
                                    confidence=0.62,
                                )
                            )
                            seen.add(dedupe_key)
                        break

        if source_kind == "input":
            compact = " | ".join(part.strip() for part in text.splitlines() if part.strip()).strip()
            if compact:
                request_text = compact[:280]
                norm = normalize_state_text(request_text)
                dedupe_key = ("user_request", norm)
                if dedupe_key not in seen:
                    observations.append(
                        self._operation_observation(
                            kind="user_request",
                            text=request_text,
                            detail=detail,
                            importance=4,
                            confidence=0.38,
                        )
                    )
                    seen.add(dedupe_key)
        return observations

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
        seen_decisions: set[str] = set()
        for candidate in self._candidate_segments(event.assistant_message):
            if not candidate:
                continue
            for pattern in DECISION_PATTERNS:
                match = pattern.match(candidate)
                if match:
                    decision = match.group(1).strip()
                    normalized = normalize_state_text(decision)
                    if not normalized or normalized in seen_decisions:
                        break
                    seen_decisions.add(normalized)
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
        for message in event.input_messages:
            observations.extend(
                self._extract_from_lines(
                    message,
                    source_kind="input",
                    detail=message,
                )
            )
        observations.extend(
            self._extract_from_lines(
                event.assistant_message,
                source_kind="assistant",
                detail=event.assistant_message,
            )
        )
        return observations
