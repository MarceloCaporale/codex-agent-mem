from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from codex_agent_mem.models import GenericEventEnvelope
from codex_agent_mem.providers.noop import HeuristicSummarizer


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize_event(payload: dict[str, Any]) -> GenericEventEnvelope:
    event = GenericEventEnvelope.model_validate(payload)
    if not event.timestamp:
        event.timestamp = now_iso()
    return event


def classify_event(event: GenericEventEnvelope):
    provider = HeuristicSummarizer()
    summary = provider.summarize_turn(event)
    observations = provider.extract_observations(event)
    return summary, observations
