from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event


def test_diagnostic_turns_do_not_mutate_operational_state(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    baseline = {
        "runtime": "codex",
        "project_key": "diagnostic-demo",
        "session_id": "thread-1",
        "cwd": str(tmp_path),
        "metadata": {},
    }
    store.ingest_event(
        {
            **baseline,
            "turn_id": "turn-1",
            "timestamp": "2026-04-18T00:00:00Z",
            "input_messages": [
                "Objective: preserve scope.\n"
                "Pending: expose mem_completion_check.\n"
                "Blocker: no human validation yet."
            ],
            "assistant_message": "Decision: keep closure deterministic.\nStatus: complete",
        },
        normalize_event(
            {
                **baseline,
                "turn_id": "turn-1",
                "timestamp": "2026-04-18T00:00:00Z",
                "input_messages": [
                    "Objective: preserve scope.\n"
                    "Pending: expose mem_completion_check.\n"
                    "Blocker: no human validation yet."
                ],
                "assistant_message": "Decision: keep closure deterministic.\nStatus: complete",
            }
        ),
    )
    before = store.operational_state("diagnostic-demo")
    assert before is not None

    diagnostic_payload = {
        **baseline,
        "turn_id": "turn-2",
        "timestamp": "2026-04-18T00:01:00Z",
        "input_messages": [
            "Use the codex-agent-mem MCP tool mem_open_work for this project and respond exactly as: pending=<n>"
        ],
        "assistant_message": "pending=1 blocker=1",
    }
    store.ingest_event(diagnostic_payload, normalize_event(diagnostic_payload))
    after = store.operational_state("diagnostic-demo")
    assert after is not None
    assert [item["summary"] for item in after["pending_items"]] == [item["summary"] for item in before["pending_items"]]
    assert [item["summary"] for item in after["blockers"]] == [item["summary"] for item in before["blockers"]]
