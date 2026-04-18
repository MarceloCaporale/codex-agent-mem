from pathlib import Path

from codex_agent_mem.smoke import run_smoke


def test_smoke_runs_end_to_end(tmp_path: Path):
    result = run_smoke(db_path=tmp_path / "codex_agent_mem.db", project_key="smoke-project")
    assert result["ingest"]["ok"] is True
    assert result["brief"]["counts"]["observations"] >= 1
    assert result["recent"]
    assert result["provenance"]["memory_kind"] == "observation"
    assert result["health"]["score"] >= 0
    assert result["snapshot"]["snapshot_hash"]
