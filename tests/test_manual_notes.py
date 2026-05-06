from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event
from codex_agent_mem.mcp_stdio import CodexAgentMemMCPServer, MCPRuntimeState


def _seed_session(
    store: CodexAgentMemStore,
    tmp_path: Path,
    *,
    project_key: str = "manual-note-demo",
    external_session_id: str = "manual-thread",
    turn_id: str = "turn-1",
) -> int:
    payload = {
        "runtime": "codex",
        "project_key": project_key,
        "session_id": external_session_id,
        "turn_id": turn_id,
        "cwd": str(tmp_path),
        "timestamp": "2026-04-29T00:00:00Z",
        "input_messages": ["Objective: validate manual operational notes."],
        "assistant_message": "Decision: keep manual notes separate from snapshots.",
        "metadata": {"source": "manual-note-test"},
    }
    store.ingest_event(payload, normalize_event(payload))
    sessions = store.list_sessions(project_key)
    match = [item for item in sessions if item["external_session_id"] == external_session_id]
    assert match
    return int(match[0]["session_id"])


def _insert_inferred_observation(
    store: CodexAgentMemStore,
    *,
    project_key: str,
    text: str,
    title: str = "Inferred similar memory",
    session_id: int | None = None,
    importance: int = 5,
) -> int:
    project = store._project_row(project_key)
    assert project is not None
    now = store._now()
    dedupe_hash = sha256(f"{project_key}\0{session_id}\0{title}\0{text}".encode("utf-8")).hexdigest()
    with store.conn:
        cur = store.conn.execute(
            """
            INSERT INTO observations(
              project_id, session_id, turn_id, type, title, summary, detail,
              confidence, importance, status, source_runtime, source_kind,
              dedupe_hash, created_at, updated_at
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(project["id"]),
                session_id,
                "session_summary",
                title,
                text,
                text,
                0.6,
                importance,
                "active",
                "codex",
                "turn_extract",
                dedupe_hash,
                now,
                now,
            ),
        )
    return int(cur.lastrowid)


def _create_codex_release_freeze_note(store: CodexAgentMemStore, project_key: str = "manual-note-demo") -> dict:
    note = store.create_manual_note(
        project_key,
        (
            "codex-agent-mem v1.0.1 quedo congelada tecnicamente. "
            "Auditoria externa GPT_5.5_PRO aprobo iteracion 17. "
            "No publicar GitHub todavia. Pendientes: sitios visualaimedia.com "
            "y visualsystemslab.com online, revisar tag, pedir autorizacion antes de release."
        ),
        title="codex-agent-mem v1.0.1 freeze tecnico iteracion 17",
        tags=["codex-agent-mem", "v1.0.1", "freeze", "release", "publish-hold"],
        importance=5,
    )
    assert note is not None
    return note


def test_manual_note_create_is_searchable_packable_and_auditable(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    session_id = _seed_session(store, tmp_path)
    phrase = "manual-note-e2e-phrase-20260429 session scoped continuity"

    note = store.create_manual_note(
        "manual-note-demo",
        phrase,
        session_id=session_id,
        title="Manual continuity note",
        tags=["continuity", "manual"],
        importance=5,
    )

    assert note is not None
    assert note["created"] is True
    assert note["session_id"] == session_id
    assert note["external_session_id"] == "manual-thread"
    assert note["source_kind"] == "manual_note"
    assert note["provenance_confidence"] == "high"
    assert note["provenance_warning"] is None

    search = store.search_observations(phrase, project_key="manual-note-demo", session_id=session_id)
    assert search
    assert search[0]["id"] == note["observation_id"]
    assert search[0]["source_kind"] == "manual_note"

    pack = store.context_pack("manual-note-demo", budget="full", session_id=session_id)
    assert pack is not None
    assert phrase in pack["text"]
    assert pack["stats"]["session_filter_applied"] is True

    provenance = store.get_provenance(memory_id=note["observation_id"], memory_kind="observation")
    assert provenance is not None
    assert provenance["source_turn"] is None
    assert provenance["source_session"]["external_session_id"] == "manual-thread"
    assert provenance["source_span"]["source_kind"] == "manual_note"
    assert provenance["source_span"]["tags"] == ["continuity", "manual"]


def test_manual_note_without_session_is_project_scoped_not_inferred(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)

    note = store.create_manual_note("manual-note-demo", "project scoped manual note")

    assert note is not None
    assert note["session_id"] is None
    assert note["external_session_id"] is None
    assert note["provenance_confidence"] == "project"
    assert "project-scoped" in note["provenance_warning"]


def test_manual_note_session_id_must_belong_to_project(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    other_session_id = _seed_session(
        store,
        tmp_path,
        project_key="other-project",
        external_session_id="other-thread",
    )
    _seed_session(store, tmp_path, project_key="manual-note-demo")

    with pytest.raises(ValueError, match="Session not found for project"):
        store.create_manual_note(
            "manual-note-demo",
            "wrong project session should fail",
            session_id=other_session_id,
        )


def test_important_manual_note_wins_against_similar_inferred_memory(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    text = "codex-agent-mem v1.0.1 congelada sitios pendientes no publicar GitHub"
    inferred_id = _insert_inferred_observation(
        store,
        project_key="manual-note-demo",
        text=text,
    )
    note = store.create_manual_note(
        "manual-note-demo",
        text,
        title="codex-agent-mem v1.0.1 freeze tecnico iteracion 17",
        tags=["codex-agent-mem", "v1.0.1", "freeze", "release", "publish-hold"],
        importance=5,
    )

    results = store.search_observations(
        "v1.0.1 congelada sitios pendientes",
        project_key="manual-note-demo",
    )

    assert results[0]["id"] == note["observation_id"]
    assert results[0]["id"] != inferred_id
    assert results[0]["source_kind"] == "manual_note"
    assert results[0]["importance"] == 5
    assert "publish-hold" in results[0]["tags"]
    assert results[0]["ranking_reason"]["manual_note_score"] > 0
    assert "manual_note" in results[0]["retrieval_boosts"]


def test_manual_note_alias_finds_freeze_tag_from_congelada_query(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    note = store.create_manual_note(
        "manual-note-demo",
        "codex-agent-mem v1.0.1 freeze tecnico iteracion 17. No publicar GitHub todavia.",
        title="codex-agent-mem v1.0.1 freeze tecnico iteracion 17",
        tags=["freeze", "release", "publish-hold"],
        importance=5,
    )

    results = store.search_observations("congelada", project_key="manual-note-demo")

    assert results
    assert results[0]["id"] == note["observation_id"]
    assert results[0]["fallback_applied"] is True
    assert "freeze" in results[0]["ranking_reason"]["alias_matches"]


def test_manual_note_publish_hold_found_by_estado_publicacion_github(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    note = store.create_manual_note(
        "manual-note-demo",
        (
            "codex-agent-mem v1.0.1 quedo congelada tecnicamente. "
            "No publicar GitHub todavia. Pedir autorizacion antes de commit/tag/push/release."
        ),
        title="codex-agent-mem v1.0.1 freeze tecnico iteracion 17",
        tags=["release", "publish-hold", "version-state"],
        importance=5,
    )

    results = store.search_observations("estado publicacion github", project_key="manual-note-demo")

    assert results
    assert results[0]["id"] == note["observation_id"]
    assert results[0]["source_kind"] == "manual_note"
    assert "publish-hold" in results[0]["tags"]
    assert results[0]["fallback_applied"] is True


def test_manual_note_freeze_query_still_returns_release_note(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    note = _create_codex_release_freeze_note(store)

    results = store.search_observations(
        "v1.0.1 congelada sitios pendientes",
        project_key="manual-note-demo",
    )

    assert results
    assert results[0]["id"] == note["observation_id"]
    assert results[0]["source_kind"] == "manual_note"
    assert "manual_note" in results[0]["retrieval_boosts"]
    assert results[0]["ranking_reason"]["relevance_gate_passed"] is True
    assert results[0]["ranking_reason"]["relevance_gate_reason"]


def test_freeze_query_prefers_operational_note_over_meta_validation_literal(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    release_note = _create_codex_release_freeze_note(store)
    meta_note = store.create_manual_note(
        "manual-note-demo",
        (
            "Validation note: v1.0.1 congelada sitios pendientes must keep returning "
            "the operational freeze note above meta validation notes."
        ),
        title="codex-agent-mem v1.0.1 manual-note relevance gate local",
        tags=["codex-agent-mem", "manual-note-search", "relevance-gate", "local-install"],
        importance=5,
    )

    results = store.search_observations(
        "v1.0.1 congelada sitios pendientes",
        project_key="manual-note-demo",
    )

    assert release_note is not None
    assert meta_note is not None
    assert results
    assert results[0]["id"] == release_note["observation_id"]
    assert meta_note["observation_id"] not in {item["id"] for item in results}


def test_manual_note_publication_query_still_returns_release_note(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    note = _create_codex_release_freeze_note(store)

    results = store.search_observations("estado publicacion github", project_key="manual-note-demo")

    assert results
    assert results[0]["id"] == note["observation_id"]
    assert results[0]["ranking_reason"]["relevance_gate_passed"] is True


def test_important_manual_note_does_not_match_unrelated_audit_package_query(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    note = _create_codex_release_freeze_note(store)

    results = store.search_observations(
        "paquetes_gpt5.5-PRO codigo planes_y_roadmaps reportes_PTOI manifiesto auditoria",
        project_key="manual-note-demo",
    )

    assert note["observation_id"] not in {item["id"] for item in results}


def test_meta_manual_note_does_not_match_negative_validation_query(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    note = store.create_manual_note(
        "manual-note-demo",
        (
            "Validation note: paquetes_gpt5.5-PRO codigo planes_y_roadmaps "
            "reportes_PTOI manifiesto auditoria devuelve count=0."
        ),
        title="codex-agent-mem v1.0.1 manual-note relevance gate local",
        tags=[
            "codex-agent-mem",
            "manual-note-search",
            "relevance-gate",
            "local-install",
            "publish-hold",
        ],
        importance=5,
    )

    results = store.search_observations(
        "paquetes_gpt5.5-PRO codigo planes_y_roadmaps reportes_PTOI manifiesto auditoria",
        project_key="manual-note-demo",
    )

    assert note is not None
    assert note["observation_id"] not in {item["id"] for item in results}


def test_meta_manual_note_matches_explicit_meta_query(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    note = store.create_manual_note(
        "manual-note-demo",
        (
            "Validation note: paquetes_gpt5.5-PRO codigo planes_y_roadmaps "
            "reportes_PTOI manifiesto auditoria devuelve count=0."
        ),
        title="codex-agent-mem v1.0.1 manual-note relevance gate local",
        tags=[
            "codex-agent-mem",
            "manual-note-search",
            "relevance-gate",
            "local-install",
            "publish-hold",
        ],
        importance=5,
    )

    results = store.search_observations(
        "codex-agent-mem relevance gate manual-note-search",
        project_key="manual-note-demo",
    )

    assert note is not None
    assert results
    assert results[0]["id"] == note["observation_id"]
    assert results[0]["ranking_reason"]["meta_gate_passed"] is True
    assert results[0]["ranking_reason"]["meta_gate_reason"]


def test_manual_note_project_specific_terms_win(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    codex_note = _create_codex_release_freeze_note(store)
    clean_note = store.create_manual_note(
        "manual-note-demo",
        (
            "clean-process-ended v0.2 current state. SPEC_TARGET_v0.2, "
            "VALIDATION_LOG_v0.1 and README_VERSION_v0.1 are the package audit anchors. "
            "Use paquetes_gpt5.5-PRO as external feedback evidence."
        ),
        title="clean-process-ended v0.2 validation package",
        tags=["clean-process-ended", "current-state", "baseline"],
        importance=5,
    )

    results = store.search_observations(
        "SPEC_TARGET_v0.2 VALIDATION_LOG_v0.1 README_VERSION_v0.1 paquetes_gpt5.5-PRO",
        project_key="manual-note-demo",
    )

    assert clean_note is not None
    assert results
    assert results[0]["id"] == clean_note["observation_id"]
    assert results[0]["id"] != codex_note["observation_id"]


def test_lab_stress_clean_process_query_is_not_contaminated_by_codex_notes(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    project_key = "__LAB_desarrollo_IDEAS"
    _seed_session(store, tmp_path, project_key=project_key, external_session_id="codex-agent-mem-thread")
    _seed_session(store, tmp_path, project_key=project_key, external_session_id="clean-process-ended-thread")
    codex_note = _create_codex_release_freeze_note(store, project_key=project_key)
    meta_note = store.create_manual_note(
        project_key,
        (
            "Validation note for codex-agent-mem manual-note search: "
            "paquetes_gpt5.5-PRO codigo planes_y_roadmaps reportes_PTOI manifiesto auditoria "
            "must not retrieve codex-agent-mem."
        ),
        title="codex-agent-mem v1.0.1 manual-note relevance gate local",
        tags=["codex-agent-mem", "manual-note-search", "relevance-gate", "local-install"],
        importance=5,
    )
    clean_note = store.create_manual_note(
        project_key,
        (
            "clean-process-ended v0.2 current state. SPEC_TARGET_v0.2, "
            "VALIDATION_LOG_v0.1 and README_VERSION_v0.1 define the package audit plan. "
            "Use paquetes_gpt5.5-PRO as external feedback evidence."
        ),
        title="clean-process-ended v0.2 validation package",
        tags=["clean-process-ended", "current-state", "baseline"],
        importance=5,
    )

    results = store.search_observations(
        "SPEC_TARGET_v0.2 VALIDATION_LOG_v0.1 README_VERSION_v0.1 paquetes_gpt5.5-PRO",
        project_key=project_key,
    )

    ids = {item["id"] for item in results}
    assert clean_note is not None
    assert meta_note is not None
    assert results
    assert results[0]["id"] == clean_note["observation_id"]
    assert codex_note["observation_id"] not in ids
    assert meta_note["observation_id"] not in ids


def test_lab_stress_negative_package_query_does_not_return_meta_note(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    project_key = "__LAB_desarrollo_IDEAS"
    _seed_session(store, tmp_path, project_key=project_key)
    meta_note = store.create_manual_note(
        project_key,
        (
            "Validation note for codex-agent-mem manual-note search: "
            "paquetes_gpt5.5-PRO codigo planes_y_roadmaps reportes_PTOI manifiesto auditoria "
            "must remain empty for unrelated project searches."
        ),
        title="codex-agent-mem v1.0.1 manual-note relevance gate local",
        tags=["codex-agent-mem", "manual-note-search", "relevance-gate", "local-install"],
        importance=5,
    )

    results = store.search_observations(
        "paquetes_gpt5.5-PRO codigo planes_y_roadmaps reportes_PTOI manifiesto auditoria",
        project_key=project_key,
    )

    assert meta_note is not None
    assert meta_note["observation_id"] not in {item["id"] for item in results}


def test_normal_multithread_project_natural_query_finds_manual_note_without_session_filter(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    project_key = "single-product"
    session_a = _seed_session(store, tmp_path, project_key=project_key, external_session_id="release-thread")
    _seed_session(store, tmp_path, project_key=project_key, external_session_id="design-thread", turn_id="turn-2")
    release_note = store.create_manual_note(
        project_key,
        (
            "El importador de facturacion queda congelado hasta revisar export CSV con Sofia. "
            "Mantener staging activo; no publicar produccion."
        ),
        session_id=session_a,
        title="Decision operativa de release",
        tags=["decision"],
        importance=5,
    )
    design_note = store.create_manual_note(
        project_key,
        "La pantalla de bienvenida necesita revisar contraste y spacing antes de demo interna.",
        title="Revision visual pendiente",
        tags=["ui"],
        importance=4,
    )

    results = store.search_observations("que falta antes de publicar a produccion", project_key=project_key)

    assert release_note is not None
    assert design_note is not None
    assert results
    assert results[0]["id"] == release_note["observation_id"]
    assert results[0]["id"] != design_note["observation_id"]
    assert results[0]["session_id"] == session_a
    assert results[0]["ranking_reason"]["relevance_gate_passed"] is True


def test_normal_project_scoped_note_is_tolerant_without_perfect_tags_or_session_id(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    project_key = "single-product"
    _seed_session(store, tmp_path, project_key=project_key, external_session_id="thread-a")
    _seed_session(store, tmp_path, project_key=project_key, external_session_id="thread-b", turn_id="turn-b")
    note = store.create_manual_note(
        project_key,
        (
            "Estado actual: el flujo de cobros esta bloqueado hasta validar facturas CSV. "
            "No publicar produccion antes de la revision final."
        ),
        title="Estado operativo",
        tags=["ops"],
        importance=5,
    )

    results = store.search_observations("estado cobros publicar produccion", project_key=project_key)

    assert note is not None
    assert results
    assert results[0]["id"] == note["observation_id"]
    assert results[0]["session_id"] is None
    assert results[0]["source_kind"] == "manual_note"


def test_manual_note_exact_opaque_identifier_ranks_first(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    project_key = "manual-note-demo"
    _seed_session(store, tmp_path, project_key=project_key)
    token = "MCP_DIAGNOSTIC_NOTE_20260429_2255"
    for index in range(4):
        store.create_manual_note(
            project_key,
            (
                f"Generic MCP diagnostic release note {index}. "
                "Important manual_note for freeze/release/publish-hold validation."
            ),
            title=f"Generic MCP diagnostic release note {index}",
            tags=["codex-agent-mem", "freeze", "release", "publish-hold"],
            importance=5,
        )
    diagnostic_note = store.create_manual_note(
        project_key,
        f"Diagnostic literal marker for this run: {token}.",
        title="MCP diagnostic literal marker",
        tags=["diagnostic", "manual-note-search"],
        importance=3,
    )

    results = store.search_observations(token, project_key=project_key)

    assert diagnostic_note is not None
    assert results
    assert results[0]["id"] == diagnostic_note["observation_id"]
    reason = results[0]["ranking_reason"]
    assert reason["exact_identifier_match"] is True
    assert reason["literal_query_match"] is True
    assert "exact_identifier_match" in reason["relevance_gate_reason"]


def test_manual_note_session_filter_does_not_mix_other_sessions(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    session_a = _seed_session(store, tmp_path, external_session_id="thread-a", turn_id="turn-a")
    session_b = _seed_session(store, tmp_path, external_session_id="thread-b", turn_id="turn-b")
    note_a = store.create_manual_note(
        "manual-note-demo",
        "thread A release hold GitHub no publicar",
        session_id=session_a,
        title="Thread A publish hold",
        tags=["release", "publish-hold"],
        importance=5,
    )
    note_b = store.create_manual_note(
        "manual-note-demo",
        "thread B release hold GitHub no publicar",
        session_id=session_b,
        title="Thread B publish hold",
        tags=["release", "publish-hold"],
        importance=5,
    )

    results = store.search_observations(
        "estado publicacion github",
        project_key="manual-note-demo",
        session_id=session_a,
    )

    ids = {item["id"] for item in results}
    assert note_a["observation_id"] in ids
    assert note_b["observation_id"] not in ids
    assert all(item["session_id"] == session_a for item in results)


def test_project_scoped_manual_note_appears_in_project_wide_search(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _seed_session(store, tmp_path)
    note = store.create_manual_note(
        "manual-note-demo",
        "Project scoped freeze note for v1.0.1 sites pending and GitHub hold.",
        title="Project scoped freeze",
        tags=["freeze", "release", "publish-hold"],
        importance=5,
    )

    results = store.search_observations(
        "v1.0.1 congelada sitios pendientes",
        project_key="manual-note-demo",
    )

    assert results
    assert results[0]["id"] == note["observation_id"]
    assert results[0]["session_id"] is None
    assert results[0]["source_kind"] == "manual_note"


def test_manual_note_weak_numeric_match_does_not_trigger_fallback(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    item = {
        "source_kind": "manual_note",
        "status": "active",
        "importance": 5,
        "title": "clean process ended 1",
        "summary": "clean process ended 1",
        "detail": "Tags: release\n\nclean process ended 1",
        "tags": ["release"],
    }

    score, metadata = store._manual_note_retrieval_score(  # noqa: SLF001
        item,
        query="v1.0.1 congelada sitios pendientes",
        fallback_applied=True,
    )

    assert score == 0.0
    assert metadata == {}


def test_mcp_mem_note_create_contract_and_read_only_guard(tmp_path: Path):
    db_path = tmp_path / "codex_agent_mem.db"
    store = CodexAgentMemStore(db_path)
    session_id = _seed_session(store, tmp_path)
    runtime = MCPRuntimeState(db_path=db_path, idle_timeout_seconds=300, profile="full")
    server = CodexAgentMemMCPServer(store, runtime)
    phrase = "mcp-note-create-e2e-phrase-20260429"

    tools = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "mem_note_create" in names

    created = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "mem_note_create",
                "arguments": {
                    "project_key": "manual-note-demo",
                    "text": phrase,
                    "session_id": session_id,
                    "title": "MCP manual note",
                    "tags": ["mcp", "continuity"],
                    "importance": 5,
                },
            },
        }
    )
    assert created["result"]["isError"] is False
    note_id = created["result"]["structuredContent"]["observation_id"]

    search = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "mem_search",
                "arguments": {"project_key": "manual-note-demo", "query": phrase, "session_id": session_id},
            },
        }
    )
    assert search["result"]["structuredContent"]["items"][0]["id"] == note_id

    pack = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "mem_context_pack",
                "arguments": {"project_key": "manual-note-demo", "budget": "full", "session_id": session_id},
            },
        }
    )
    assert phrase in pack["result"]["structuredContent"]["text"]

    read_only_server = CodexAgentMemMCPServer(
        store,
        MCPRuntimeState(db_path=db_path, idle_timeout_seconds=300, profile="full", read_only=True),
    )
    blocked = read_only_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "mem_note_create",
                "arguments": {"project_key": "manual-note-demo", "text": "blocked"},
            },
        }
    )
    assert blocked["result"]["isError"] is True
    assert "read-only" in blocked["result"]["structuredContent"]["error"]
