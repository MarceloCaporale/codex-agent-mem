from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore


def test_sqlite_connection_uses_runtime_friendly_pragmas(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    try:
        journal_mode = store.conn.execute("PRAGMA journal_mode;").fetchone()[0]
        busy_timeout = store.conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        synchronous = store.conn.execute("PRAGMA synchronous;").fetchone()[0]
        temp_store = store.conn.execute("PRAGMA temp_store;").fetchone()[0]
        assert str(journal_mode).lower() == "wal"
        assert int(busy_timeout) == 5000
        assert int(synchronous) in {1, 2}
        assert int(temp_store) == 2
    finally:
        store.close()
