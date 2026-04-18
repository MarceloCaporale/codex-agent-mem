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
PROJECT_DOD_PATTERNS = [
    re.compile(r"^\s*(?:project\s+(?:dod|definition of done))\s*[:\-]\s*(.+)$", re.IGNORECASE),
]
MISSION_DOD_PATTERNS = [
    re.compile(r"^\s*(?:mission\s+(?:dod|definition of done))\s*[:\-]\s*(.+)$", re.IGNORECASE),
]
SESSION_DOD_PATTERNS = [
    re.compile(r"^\s*(?:session\s+(?:dod|definition of done))\s*[:\-]\s*(.+)$", re.IGNORECASE),
    re.compile(r"^\s*(?:dod|definition of done)\s*[:\-]\s*(.+)$", re.IGNORECASE),
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
INLINE_LABEL_SPLIT_RE = re.compile(
    r"\s+(?=(?:decision|decisión|objective|goal|target|mission|constraint|restriction|rule|"
    r"project\s+(?:dod|definition of done)|mission\s+(?:dod|definition of done)|"
    r"session\s+(?:dod|definition of done)|(?<!project )(?<!mission )(?<!session )"
    r"(?:dod|definition of done)|pending|todo|to do|remaining|"
    r"open item|done|completed|finished|blocker|blocked|risk|status)\s*[:\-])",
    re.IGNORECASE,
)
STATE_VALUE_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
NOISY_STATE_VALUES = {"and", "or"}
DIAGNOSTIC_TURN_PATTERNS = [
    re.compile(r"use the codex-agent-mem mcp tool", re.IGNORECASE),
    re.compile(
        r"\b(?:use|call|invoke)\b.{0,160}\bmem_(?:search|get|recent|project_brief|open_work|completion_check|recent_changes|scope_guard|context_pack|provenance|health|snapshot_(?:list|create|restore))\b",
        re.IGNORECASE,
    ),
    re.compile(r"respond exactly as\s*:", re.IGNORECASE),
    re.compile(r"without using tools or reading files", re.IGNORECASE),
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
            raw_parts = [part.strip() for part in re.split(r"\s*;\s*", stripped) if part.strip()]
            for raw_part in raw_parts or [stripped]:
                inline_parts = [part.strip() for part in INLINE_LABEL_SPLIT_RE.split(raw_part) if part.strip()]
                segments.extend(inline_parts or [raw_part])
        return segments

    def _operation_observation(self, *, kind: str, text: str, detail: str, importance: int, confidence: float) -> Observation:
        label_map = {
            "objective": "Objective",
            "user_request": "User request",
            "constraint": "Constraint",
            "project_dod": "Project DoD",
            "mission_dod": "Mission DoD",
            "session_dod": "Session DoD",
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

    @staticmethod
    def _clean_state_value(value: str) -> str:
        compact = " ".join((value or "").split()).strip(" -")
        parts = [part.strip() for part in STATE_VALUE_SENTENCE_SPLIT_RE.split(compact, maxsplit=1) if part.strip()]
        return parts[0] if parts else compact

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
            ("project_dod", PROJECT_DOD_PATTERNS, 5, 0.76),
            ("mission_dod", MISSION_DOD_PATTERNS, 5, 0.76),
            ("session_dod", SESSION_DOD_PATTERNS, 5, 0.74),
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
                    value = self._clean_state_value(match.group(1).strip())
                    norm = normalize_state_text(value)
                    if not norm or norm in NOISY_STATE_VALUES:
                        matched = True
                        break
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

    @staticmethod
    def _is_diagnostic_turn(event: GenericEventEnvelope) -> bool:
        combined = "\n".join(event.input_messages or [])
        return any(pattern.search(combined) for pattern in DIAGNOSTIC_TURN_PATTERNS)

    def extract_observations(self, event: GenericEventEnvelope) -> list[Observation]:
        if self._is_diagnostic_turn(event):
            return []
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
