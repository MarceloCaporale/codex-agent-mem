from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    data_dir: Path = Field(default=Path.home() / ".codex_agent_mem")
    db_path: Path = Field(default=Path.home() / ".codex_agent_mem" / "codex_agent_mem.db")
    host: str = "127.0.0.1"
    port: int = 37770

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
