from codex_agent_mem.models import GenericEventEnvelope


def test_generic_event_envelope_minimal():
    payload = {
        "runtime": "codex",
        "project_key": "demo",
        "session_id": "s1",
        "turn_id": "t1",
        "timestamp": "2026-04-17T00:00:00Z",
        "input_messages": ["hello"],
        "assistant_message": "world",
    }
    event = GenericEventEnvelope.model_validate(payload)
    assert event.runtime == "codex"
    assert event.project_key == "demo"
