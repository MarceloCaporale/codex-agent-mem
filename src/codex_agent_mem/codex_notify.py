from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib import request

from codex_agent_mem.config import AppConfig
from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import now_iso, normalize_event
from codex_agent_mem.project_identity import ProjectIdentity, resolve_project_identity
from codex_agent_mem.project_doc import sync_project_doc


def _flatten_input_messages(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [str(value)]
    messages: list[str] = []
    for item in value:
        if isinstance(item, str):
            messages.append(item)
        elif isinstance(item, dict):
            if isinstance(item.get("text"), str):
                messages.append(item["text"])
            elif isinstance(item.get("content"), str):
                messages.append(item["content"])
            else:
                messages.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
        else:
            messages.append(str(item))
    return messages


def derive_project_key(payload: dict[str, Any], explicit: str | None, project_from_cwd: bool) -> str:
    return derive_project_identity(payload, explicit, project_from_cwd).project_key


def derive_project_identity(
    payload: dict[str, Any],
    explicit: str | None,
    project_from_cwd: bool,
) -> ProjectIdentity:
    return resolve_project_identity(
        payload,
        explicit=explicit,
        project_from_cwd=project_from_cwd,
    )


def codex_notify_to_generic(
    payload: dict[str, Any],
    project_key: str,
    *,
    project_identity: ProjectIdentity | None = None,
) -> dict[str, Any]:
    metadata = {
        "codex_notification_type": payload.get("type"),
        "model_name": payload.get("model")
        or payload.get("model-name")
        or payload.get("model_name"),
    }
    if project_identity is not None:
        metadata.update(
            {
                "project_resolution_source": project_identity.source,
                "project_resolution_confidence": project_identity.confidence,
                "project_resolution_warnings": project_identity.warnings,
            }
        )
        if project_identity.root_path:
            metadata["project_root_path"] = project_identity.root_path
    return {
        "runtime": "codex",
        "project_key": project_key,
        "session_id": payload.get("thread-id") or payload.get("thread_id") or "unknown-session",
        "turn_id": payload.get("turn-id") or payload.get("turn_id") or "unknown-turn",
        "cwd": payload.get("cwd"),
        "timestamp": payload.get("timestamp") or payload.get("emitted-at") or now_iso(),
        "input_messages": _flatten_input_messages(payload.get("input-messages") or payload.get("input_messages")),
        "assistant_message": payload.get("last-assistant-message") or payload.get("last_assistant_message") or "",
        "tool_events": [],
        "artifacts": [],
        "metadata": metadata,
    }


def ingest_via_http(
    api_base: str,
    raw_payload: dict[str, Any],
    project_key: str,
    *,
    sync_project_doc_after_ingest: bool = False,
) -> None:
    body = {
        "payload": raw_payload,
        "project_key": project_key,
        "project_from_cwd": False,
        "sync_project_doc": sync_project_doc_after_ingest,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        api_base.rstrip("/") + "/ingest/codex-notify",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=5) as resp:
        _ = resp.read()


def ingest_direct(
    db_path: Path,
    raw_payload: dict[str, Any],
    generic_payload: dict[str, Any],
    *,
    sync_project_doc_after_ingest: bool = False,
) -> dict[str, Any]:
    store = CodexAgentMemStore(db_path=db_path)
    event = normalize_event(generic_payload)
    result = store.ingest_event(raw_payload, event)
    if sync_project_doc_after_ingest and event.cwd:
        sync_result = sync_project_doc(
            store=store,
            project_key=event.project_key,
            cwd=Path(event.cwd),
        )
        result["project_doc_sync"] = sync_result
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persist Codex notify events into codex_agent_mem")
    parser.add_argument("payload_json", nargs="?", help="Raw JSON payload emitted by Codex notify")
    parser.add_argument("--project-key", dest="project_key")
    parser.add_argument("--project-from-cwd", action="store_true")
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    parser.add_argument("--api-base", help="Optional local API base, e.g. http://127.0.0.1:37770")
    parser.add_argument("--sync-project-doc", action="store_true", help="Sync a compact generated working-memory block into AGENTS.md after ingest")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    raw = args.payload_json or sys.stdin.read().strip()
    if not raw:
        return 0
    payload = json.loads(raw)
    if payload.get("type") != "agent-turn-complete":
        return 0
    project_identity = derive_project_identity(
        payload,
        explicit=args.project_key,
        project_from_cwd=args.project_from_cwd,
    )
    project_key = project_identity.project_key
    generic_payload = codex_notify_to_generic(payload, project_key, project_identity=project_identity)
    if args.api_base:
        ingest_via_http(
            args.api_base,
            payload,
            project_key,
            sync_project_doc_after_ingest=args.sync_project_doc,
        )
    else:
        ingest_direct(
            args.db_path,
            payload,
            generic_payload,
            sync_project_doc_after_ingest=args.sync_project_doc,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
