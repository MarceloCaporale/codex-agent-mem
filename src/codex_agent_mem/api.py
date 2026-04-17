from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
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


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or AppConfig()
    config.ensure_dirs()
    store = CodexAgentMemStore(config.db_path)
    app = FastAPI(title="codex-agent-mem Local API", version=__version__)
    app.state.store = store

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
