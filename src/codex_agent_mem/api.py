from __future__ import annotations

import argparse
import json
from datetime import datetime
from importlib.resources import files
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from codex_agent_mem import __version__
from codex_agent_mem.codex_notify import codex_notify_to_generic, derive_project_key
from codex_agent_mem.config import AppConfig
from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event


class GenericIngestRequest(BaseModel):
    payload: dict


class CodexNotifyRequest(BaseModel):
    payload: dict
    project_key: str | None = None
    project_from_cwd: bool = True


def _loads_json(raw: str | None, fallback):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _shorten(text: str, limit: int = 72) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


def _format_timestamp(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw


def _humanize_name(raw: str) -> str:
    return raw.replace("_", " ").replace("-", " ").strip()


def _session_display_parts(session: dict, project: dict | None = None) -> dict[str, str | None]:
    cwd = session.get("cwd") or (project or {}).get("root_path") or ""
    raw_source_name = Path(cwd).name if cwd else ((project or {}).get("name") or "Session")
    source_name = _humanize_name(raw_source_name) or ((project or {}).get("name") or "Session")
    started_label = _format_timestamp(session.get("started_at")) or "Unknown time"
    first_messages = _loads_json(session.get("first_input_messages_json"), [])
    first_prompt = ""
    for item in first_messages:
        if isinstance(item, str) and item.strip():
            first_prompt = item.strip()
            break
    prompt_excerpt = _shorten(first_prompt, limit=82) if first_prompt else ""
    label = f"{source_name} · {started_label}"
    subtitle = prompt_excerpt or (cwd or "No path captured")
    return {
        "display_label": label,
        "display_subtitle": subtitle,
        "display_started_at": started_label,
    }


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or AppConfig()
    config.ensure_dirs()
    store = CodexAgentMemStore(config.db_path)
    app = FastAPI(title="codex-agent-mem Local API", version=__version__)
    app.state.store = store
    templates = Jinja2Templates(directory=str(files("codex_agent_mem").joinpath("templates")))
    app.mount("/static", StaticFiles(directory=str(files("codex_agent_mem").joinpath("static"))), name="static")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/ui")

    @app.get("/health")
    def health():
        return {"ok": True, "db_path": str(config.db_path)}

    @app.post("/ingest/generic")
    def ingest_generic(req: GenericIngestRequest):
        event = normalize_event(req.payload)
        return store.ingest_event(req.payload, event)

    @app.post("/ingest/codex-notify")
    def ingest_codex_notify(req: CodexNotifyRequest):
        project_key = derive_project_key(req.payload, explicit=req.project_key, project_from_cwd=req.project_from_cwd)
        generic_payload = codex_notify_to_generic(req.payload, project_key)
        event = normalize_event(generic_payload)
        return store.ingest_event(req.payload, event)

    @app.get("/search")
    def search(q: str, project_key: str | None = None, limit: int = 10):
        return {"query": q, "project_key": project_key, "results": store.search_observations(q, project_key, limit)}

    @app.get("/recent")
    def recent(project_key: str | None = None, limit: int = 10):
        return {"project_key": project_key, "results": store.recent_observations(project_key, limit)}

    @app.get("/projects")
    def projects():
        return store.list_projects()

    @app.get("/projects/{project_key}/brief")
    def project_brief(project_key: str):
        result = store.project_brief(project_key)
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return result

    @app.get("/observations/{observation_id}")
    def get_observation(observation_id: int):
        result = store.get_observation(observation_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Observation not found")
        return result

    @app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
    def ui_home(request: Request, q: str | None = None, project_key: str | None = None):
        query = (q or "").strip()
        context = {
            "request": request,
            "db_path": str(config.db_path),
            "projects": store.list_projects(),
            "recent_observations": store.recent_observations(limit=12),
            "query": query,
            "project_key": project_key or "",
            "search_results": store.search_observations(query, project_key=project_key or None, limit=20) if query else [],
        }
        return templates.TemplateResponse(request=request, name="index.html", context=context)

    @app.get("/ui/projects/{project_key}", response_class=HTMLResponse, include_in_schema=False)
    def ui_project(
        request: Request,
        project_key: str,
        session_id: int | None = None,
        turn_id: int | None = None,
        q: str | None = None,
    ):
        brief = store.project_brief(project_key)
        if brief is None:
            raise HTTPException(status_code=404, detail="Project not found")

        sessions = store.list_sessions(project_key, limit=100)
        for session in sessions:
            session.update(_session_display_parts(session, brief["project"]))
        sessions_by_id = {int(item["id"]): item for item in sessions}
        chosen_session_row = sessions_by_id.get(session_id) if session_id is not None else None
        if chosen_session_row is None and sessions:
            chosen_session_row = sessions[0]

        selected_session = None
        turns: list[dict] = []
        turn_detail = None
        if chosen_session_row is not None:
            selected_session = store.get_session(int(chosen_session_row["id"]))
            if selected_session is not None:
                selected_session["metadata"] = _loads_json(selected_session.get("metadata_json"), {})
                selected_session.update(_session_display_parts(selected_session, brief["project"]))
                turns = store.list_turns(int(selected_session["id"]), limit=100)
                turns_by_id = {int(item["id"]): item for item in turns}
                chosen_turn_row = turns_by_id.get(turn_id) if turn_id is not None else None
                if chosen_turn_row is None and turns:
                    chosen_turn_row = turns[0]
                if chosen_turn_row is not None:
                    turn_detail = store.get_turn(int(chosen_turn_row["id"]))
                    if turn_detail is not None:
                        turn_detail["input_messages"] = _loads_json(turn_detail.get("input_messages_json"), [])
                        turn_detail["tool_events"] = _loads_json(turn_detail.get("tool_events_json"), [])
                        turn_detail["raw_payload"] = _loads_json(turn_detail.get("raw_payload_json"), {})

        query = (q or "").strip()
        context = {
            "request": request,
            "db_path": str(config.db_path),
            "project": brief["project"],
            "counts": brief["counts"],
            "sessions": sessions,
            "selected_session": selected_session,
            "turns": turns,
            "selected_turn": turn_detail,
            "recent_observations": store.recent_observations(project_key=project_key, limit=25),
            "recent_decisions": brief["recent_decisions"],
            "query": query,
            "search_results": store.search_observations(query, project_key=project_key, limit=25) if query else [],
        }
        return templates.TemplateResponse(request=request, name="project.html", context=context)

    @app.get("/ui/turns/{turn_id}", response_class=HTMLResponse, include_in_schema=False)
    def ui_turn(request: Request, turn_id: int):
        turn_detail = store.get_turn(turn_id)
        if turn_detail is None:
            raise HTTPException(status_code=404, detail="Turn not found")
        turn_detail["input_messages"] = _loads_json(turn_detail.get("input_messages_json"), [])
        turn_detail["tool_events"] = _loads_json(turn_detail.get("tool_events_json"), [])
        turn_detail["raw_payload"] = _loads_json(turn_detail.get("raw_payload_json"), {})
        context = {
            "request": request,
            "db_path": str(config.db_path),
            "turn": turn_detail,
        }
        return templates.TemplateResponse(request=request, name="turn.html", context=context)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the codex-agent-mem local API")
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    parser.add_argument("--host", default=AppConfig().host)
    parser.add_argument("--port", type=int, default=AppConfig().port)
    args = parser.parse_args(argv)
    config = AppConfig(db_path=args.db_path, host=args.host, port=args.port)
    app = create_app(config)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
