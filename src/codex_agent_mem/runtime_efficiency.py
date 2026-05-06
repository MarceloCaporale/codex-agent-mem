from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codex_agent_mem.ingest import now_iso


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(stable_json_dumps(value).encode("utf-8")).hexdigest()


def db_identity(db_path: Path) -> str:
    return hashlib.sha256(str(db_path.resolve()).encode("utf-8", errors="replace")).hexdigest()[:16]


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0


class ShortTTLCache:
    def __init__(self, ttl_seconds: int = 15):
        self.ttl_seconds = max(0, ttl_seconds)
        self._items: dict[str, tuple[float, Any]] = {}
        self.stats = CacheStats()

    def get(self, key: Any) -> Any | None:
        if self.ttl_seconds <= 0:
            self.stats.misses += 1
            return None
        cache_key = stable_hash(key)
        item = self._items.get(cache_key)
        if item is None:
            self.stats.misses += 1
            return None
        expires_at, value = item
        if time.monotonic() >= expires_at:
            self._items.pop(cache_key, None)
            self.stats.misses += 1
            return None
        self.stats.hits += 1
        return value

    def set(self, key: Any, value: Any) -> None:
        if self.ttl_seconds <= 0:
            return
        cache_key = stable_hash(key)
        self._items[cache_key] = (time.monotonic() + self.ttl_seconds, value)


def compact_text_summary(data: Any, *, is_error: bool = False) -> str:
    if is_error:
        if isinstance(data, dict) and data.get("error"):
            return f"codex-agent-mem error: {data['error']}"
        return "codex-agent-mem error"
    if isinstance(data, dict):
        if data.get("not_modified"):
            return f"codex-agent-mem: continuity pack unchanged ({data.get('pack_hash', 'no-hash')})"
        if "selection_mode" in data and "scope_resolution" in data:
            resolution = data.get("scope_resolution") or {}
            lanes = resolution.get("candidate_lanes") or []
            context_pack = data.get("context_pack")
            mode = data.get("selection_mode")
            recommended = resolution.get("recommended_call") or {}
            next_action = recommended.get("tool") if isinstance(recommended, dict) else str(recommended or "choose_scope")
            guard = bool(resolution.get("do_not_fetch_project_wide_pack"))
            return (
                "codex-agent-mem: bootstrap_context "
                f"selection_mode={mode} context_pack_present={bool(context_pack)} "
                f"routing={resolution.get('routing_decision', 'unknown')} "
                f"candidate_lanes={len(lanes)} "
                f"do_not_fetch_project_wide_pack={guard} "
                f"next_action={next_action}"
            )
        if "routing_decision" in data and "candidate_lanes" in data:
            lanes = data.get("candidate_lanes") or []
            recommended = data.get("recommended_call") or {}
            next_action = recommended.get("tool") if isinstance(recommended, dict) else str(recommended or "choose_scope")
            guard = bool(data.get("do_not_fetch_project_wide_pack"))
            return (
                "codex-agent-mem: scope_resolve "
                f"routing={data.get('routing_decision', 'unknown')} "
                f"confidence={data.get('confidence', 'unknown')} "
                f"candidate_lanes={len(lanes)} "
                f"do_not_fetch_project_wide_pack={guard} "
                f"next_action={next_action}"
            )
        if "done" in data and "reasons" in data:
            return f"codex-agent-mem: completion_check done={data.get('done')} reasons={len(data.get('reasons') or [])}"
        if "has_open_work" in data:
            pending = len(data.get("pending_items") or [])
            blockers = len(data.get("blockers") or [])
            dod = len(data.get("dod_gaps") or [])
            return f"codex-agent-mem: open_work pending={pending} blockers={blockers} dod_gaps={dod}"
        if "text" in data and "stats" in data:
            stats = data.get("stats") or {}
            saved = stats.get("compression_ratio")
            pack_hash = data.get("pack_hash")
            suffix = f" hash={pack_hash}" if pack_hash else ""
            base = (
                "codex-agent-mem: context_pack "
                f"budget={stats.get('budget', 'unknown')} "
                f"pack_tokens={stats.get('approx_pack_tokens', '?')} "
                f"source_tokens={stats.get('approx_source_tokens', '?')} "
                f"ratio={saved if saved is not None else '?'}"
                f"{suffix}"
            )
            source_session_count = stats.get("source_session_count")
            if source_session_count is None:
                return base
            lines = [base]
            freshness = ""
            if stats.get("last_operational_capture_at"):
                freshness = (
                    f"last_operational_capture_at={stats.get('last_operational_capture_at')} "
                    "memory=persisted local context not live current-turn awareness"
                )
                if (
                    stats.get("last_captured_turn_at")
                    and stats.get("last_captured_turn_at") != stats.get("last_operational_capture_at")
                ):
                    freshness = (
                        f"{freshness} "
                        f"last_captured_turn_at={stats.get('last_captured_turn_at')}"
                    )
            elif stats.get("last_captured_turn_at"):
                freshness = (
                    f"last_captured_turn_at={stats.get('last_captured_turn_at')} "
                    "memory=persisted local context not live current-turn awareness"
                )
            if stats.get("session_filter_applied"):
                source_sessions = stats.get("source_sessions") or []
                source = source_sessions[0] if source_sessions else {}
                external_session_id = source.get("external_session_id") or source.get("id") or "unknown"
                lines.append(f"session_filter=applied source_sessions=1 external_session_id={external_session_id}")
                if freshness:
                    lines.append(freshness)
                return "\n".join(lines)
            scope_warning = stats.get("scope_warning") or {}
            warning_code = scope_warning.get("code") if isinstance(scope_warning, dict) else None
            hint = ""
            if isinstance(source_session_count, int) and source_session_count > 1:
                hint = " use mem_session_list + session_id to narrow broad project scopes"
            warning = f" scope_warning={warning_code}" if warning_code else ""
            sub_scopes = stats.get("source_sub_scope_count")
            sub_scope_text = f" sub_scopes={sub_scopes}" if sub_scopes is not None else ""
            lines.append(f"session_filter=not_applied source_sessions={source_session_count}{sub_scope_text}{warning}{hint}")
            recommended_narrowing = stats.get("recommended_narrowing")
            if isinstance(recommended_narrowing, dict):
                query_target = "<target sub-scope>"
                lines.append(
                    "Suggested narrowing: choose a target from candidate_sub_scopes, then call "
                    f'mem_session_list(project_key, query="{query_target}") before treating this '
                    "project-wide pack as active context."
                )
            if freshness:
                lines.append(freshness)
            return "\n".join(lines)
        if "score" in data and "duplicate_count" in data:
            return f"codex-agent-mem: health score={data.get('score')} open_work={data.get('open_work_count', '?')}"
        if "pid" in data and "connection_model" in data:
            warning = " spawn_storm_warning=true" if data.get("spawn_storm_warning") else ""
            return (
                "codex-agent-mem: runtime "
                f"pid={data.get('pid')} profile={data.get('profile', 'full')} "
                f"read_only={data.get('read_only', False)} "
                f"requests={data.get('requests_count', 0)}{warning}"
            )
        return f"codex-agent-mem: result object keys={len(data)}"
    if isinstance(data, list):
        return f"codex-agent-mem: result list items={len(data)}"
    return f"codex-agent-mem: result type={type(data).__name__}"


class HeartbeatRegistry:
    def __init__(self, db_path: Path, runtime_dir: Path | None = None, stale_after_seconds: int = 120):
        self.db_path = db_path
        self.stale_after_seconds = stale_after_seconds
        base_dir = runtime_dir or Path(os.environ.get("CODEX_AGENT_MEM_RUNTIME_DIR", Path.home() / ".codex_agent_mem" / "runtime"))
        self.dir = base_dir / db_identity(db_path)
        self.path = self.dir / f"{os.getpid()}.json"

    def write(self, *, profile: str, read_only: bool, response_mode: str, started_at: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "db_path": str(self.db_path),
            "profile": profile,
            "read_only": read_only,
            "response_mode": response_mode,
            "started_at": started_at,
            "last_seen": now_iso(),
        }
        self.path.write_text(stable_json_dumps(payload), encoding="utf-8")

    def cleanup_stale(self) -> None:
        if not self.dir.exists():
            return
        cutoff = time.time() - self.stale_after_seconds
        for path in self.dir.glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                continue

    def count_recent(self) -> int:
        self.cleanup_stale()
        if not self.dir.exists():
            return 0
        cutoff = time.time() - self.stale_after_seconds
        count = 0
        for path in self.dir.glob("*.json"):
            try:
                if path.stat().st_mtime >= cutoff:
                    count += 1
            except OSError:
                continue
        return count


class RuntimeTelemetry:
    def __init__(self, mode: str = "off", log_dir: Path | None = None, max_bytes: int = 1_000_000):
        self.mode = mode
        self.max_bytes = max(10_000, max_bytes)
        base_dir = log_dir or Path(os.environ.get("CODEX_AGENT_MEM_RUNTIME_DIR", Path.home() / ".codex_agent_mem" / "runtime"))
        self.path = base_dir / "events.jsonl"

    def enabled_for(self, event: str) -> bool:
        if self.mode == "debug":
            return True
        if self.mode == "summary":
            return event in {
                "process_start",
                "initialize",
                "tools_list",
                "tool_call",
                "idle_timeout",
                "stdin_eof",
                "signal",
                "process_exit",
            }
        return False

    def emit(self, event: str, **fields: Any) -> None:
        if not self.enabled_for(event):
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rotate_if_needed()
        payload = {"ts": now_iso(), "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(stable_json_dumps(payload) + "\n")

    def _rotate_if_needed(self) -> None:
        try:
            if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                rotated = self.path.with_suffix(".jsonl.1")
                rotated.unlink(missing_ok=True)
                self.path.replace(rotated)
        except OSError:
            return
