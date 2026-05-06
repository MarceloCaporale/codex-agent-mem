from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from codex_agent_mem import __version__
from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def approx_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def savings_percent(source_tokens: int, pack_tokens: int) -> float:
    if source_tokens <= 0:
        return 0.0
    return round((1 - (pack_tokens / source_tokens)) * 100, 2)


def bar(percent: float, width: int = 28) -> str:
    bounded = max(0.0, min(100.0, percent))
    filled = round((bounded / 100) * width)
    return "[" + "#" * filled + "." * (width - filled) + f"] {bounded:.2f}%"


def synthetic_detail(scenario_id: str, turn_index: int, repetitions: int) -> str:
    base = (
        f"Evidence block {turn_index} for {scenario_id}. "
        "The agent must preserve the current objective, active constraints, open work, blockers, "
        "definition of done, and concrete evidence. This repeated paragraph simulates context that "
        "would otherwise be pasted again in later turns. "
    )
    return base * repetitions


def raw_event_for_scenario(scenario: dict[str, Any], turn_index: int, root: Path) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    title = str(scenario["title"])
    detail_repetitions = int(scenario["detail_repetitions"])
    labels = [
        f"Objective: keep operational continuity for {title}",
        f"Constraint: do not drop active scope or evidence for {title}",
        f"Decision: use compact reinjection for {title}",
        f"Project DoD: pack must preserve objective, pending work, blockers and evidence for {title}",
        f"Pending: verify reproducible metrics for {title}",
    ]
    if scenario.get("include_blocker"):
        labels.append(f"Blocker: human release approval is still required for {title}")
    if scenario.get("include_completion_claim") and turn_index == int(scenario["turn_count"]):
        labels.append(f"Completion claim: {title} looks complete but must not close without evidence")

    subagents = scenario.get("subagents") or []
    subagent_text = ""
    if subagents:
        parts = [f"Subagent {item['role']}: {item['task']}" for item in subagents]
        subagent_text = " ".join(parts)

    detail = synthetic_detail(scenario_id, turn_index, detail_repetitions)
    assistant_message = "; ".join(labels) + "\n" + subagent_text + "\n" + detail
    return {
        "runtime": "codex",
        "project_key": scenario_id,
        "session_id": f"{scenario_id}-thread",
        "turn_id": f"{scenario_id}-turn-{turn_index:03d}",
        "cwd": str(root),
        "timestamp": f"2026-04-21T12:{turn_index:02d}:00Z",
        "input_messages": [
            f"Please continue {title}. Keep all constraints and pending work visible.",
            synthetic_detail(scenario_id, turn_index, max(1, detail_repetitions // 3)),
        ],
        "assistant_message": assistant_message,
        "metadata": {
            "fixture": "synthetic_public_verification",
            "scenario": scenario_id,
            "turn_index": turn_index,
        },
    }


def seed_scenario(db_path: Path, scenario: dict[str, Any], root: Path) -> dict[str, Any]:
    store = CodexAgentMemStore(db_path)
    observation_count = 0
    try:
        for index in range(1, int(scenario["turn_count"]) + 1):
            raw = raw_event_for_scenario(scenario, index, root)
            result = store.ingest_event(raw, normalize_event(raw))
            observation_count += len(result.get("observation_ids", []))
    finally:
        store.close()
    return {
        "turn_count": int(scenario["turn_count"]),
        "observation_count": observation_count,
    }


class MCPProcess:
    def __init__(
        self,
        *,
        python: Path,
        db_path: Path,
        profile: str = "minimal",
        read_only: bool = True,
        response_mode: str = "compact",
        telemetry_mode: str = "off",
        runtime_log_dir: Path | None = None,
    ) -> None:
        args = [
            str(python),
            "-m",
            "codex_agent_mem.mcp_stdio",
            "--db-path",
            str(db_path),
            "--profile",
            profile,
            "--response-mode",
            response_mode,
            "--telemetry-mode",
            telemetry_mode,
            "--idle-timeout-seconds",
            "15",
        ]
        if read_only:
            args.append("--read-only")
        if runtime_log_dir is not None:
            args.extend(["--runtime-log-dir", str(runtime_log_dir)])
        self.proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._next_id = 1

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.proc.stdin is None:
            raise RuntimeError("stdin unavailable")
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
            "params": params or {},
        }
        self._next_id += 1
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=True) + "\n")
        self.proc.stdin.flush()
        if self.proc.stdout is None:
            raise RuntimeError("stdout unavailable")
        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read() if self.proc.stderr is not None else ""
            raise RuntimeError(f"MCP process closed unexpectedly: {stderr}")
        return json.loads(line)

    def tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        if self.proc.stdin is not None:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=10)


def result_payload(response: dict[str, Any]) -> Any:
    result = response.get("result") or {}
    return result.get("structuredContent")


def result_text_chars(response: dict[str, Any]) -> int:
    result = response.get("result") or {}
    content = result.get("content") or []
    if not content:
        return 0
    return len(str(content[0].get("text", "")))


def run_profile_smoke(python: Path, db_path: Path) -> dict[str, Any]:
    mcp = MCPProcess(python=python, db_path=db_path, profile="minimal", read_only=True, response_mode="compact")
    try:
        mcp.request("initialize", {})
        tools = mcp.request("tools/list", {})
        health_before = result_payload(mcp.tool("mem_health_runtime", {}))
    finally:
        mcp.close()
    return {
        "minimal_tools": [tool["name"] for tool in tools["result"]["tools"]],
        "health_before_db_tool": health_before,
    }


def run_scenario(python: Path, scenario: dict[str, Any], work_root: Path) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    scenario_root = work_root / scenario_id
    scenario_root.mkdir(parents=True, exist_ok=True)
    db_path = scenario_root / "memory.db"
    seed = seed_scenario(db_path, scenario, scenario_root)
    profile = run_profile_smoke(python, db_path)

    mcp = MCPProcess(python=python, db_path=db_path, profile="minimal", read_only=True, response_mode="compact")
    try:
        mcp.request("initialize", {})
        first_response = mcp.tool("mem_context_pack", {"project_key": scenario_id, "budget": "normal"})
        first_pack = result_payload(first_response)
        pack_hash = first_pack.get("pack_hash")
        second_response = mcp.tool(
            "mem_context_pack",
            {"project_key": scenario_id, "budget": "normal", "known_pack_hash": pack_hash},
        )
        not_modified = result_payload(second_response)
        open_work = result_payload(mcp.tool("mem_open_work", {"project_key": scenario_id}))
        completion = result_payload(mcp.tool("mem_completion_check", {"project_key": scenario_id}))
        health_after = result_payload(mcp.tool("mem_health_runtime", {}))
    finally:
        mcp.close()

    response_modes: dict[str, dict[str, int]] = {}
    for mode in ("compact", "balanced", "verbose"):
        mode_mcp = MCPProcess(python=python, db_path=db_path, profile="minimal", read_only=True, response_mode=mode)
        try:
            mode_mcp.request("initialize", {})
            mode_response = mode_mcp.tool("mem_context_pack", {"project_key": scenario_id, "budget": "normal"})
            response_modes[mode] = {
                "content_text_chars": result_text_chars(mode_response),
                "content_text_tokens_estimate": approx_tokens(
                    ((mode_response.get("result") or {}).get("content") or [{}])[0].get("text", "")
                ),
            }
        finally:
            mode_mcp.close()

    read_only_mcp = MCPProcess(python=python, db_path=db_path, profile="full", read_only=True, response_mode="compact")
    try:
        read_only_mcp.request("initialize", {})
        blocked = read_only_mcp.tool("mem_snapshot_create", {"project_key": scenario_id, "label": "blocked-write"})
    finally:
        read_only_mcp.close()

    stats = first_pack["stats"]
    source_tokens = int(stats["approx_source_tokens"])
    pack_tokens = int(stats["approx_pack_tokens"])
    return {
        "id": scenario_id,
        "title": scenario["title"],
        "plain_language": scenario["plain_language"],
        "subagents": scenario.get("subagents") or [],
        "seed": seed,
        "context_compression": {
            "source_tokens": source_tokens,
            "pack_tokens": pack_tokens,
            "saved_tokens": max(0, source_tokens - pack_tokens),
            "savings_percent": savings_percent(source_tokens, pack_tokens),
            "compression_ratio": stats["compression_ratio"],
            "build_ms": stats["build_ms"],
            "pack_hash": pack_hash,
        },
        "not_modified": {
            "supported": bool(not_modified.get("not_modified")),
            "pack_hash": not_modified.get("pack_hash"),
            "message": not_modified.get("message"),
        },
        "minimal_profile": {
            "tool_count": len(profile["minimal_tools"]),
            "tools": profile["minimal_tools"],
        },
        "lazy_init": {
            "before_db_tool": bool(profile["health_before_db_tool"].get("lazy_initialized")),
            "after_context_pack": bool(health_after.get("lazy_initialized")),
        },
        "runtime": {
            "server_version": health_after.get("server_version"),
            "profile": health_after.get("profile"),
            "read_only": health_after.get("read_only"),
            "response_mode": health_after.get("response_mode"),
            "cache_hits": health_after.get("cache_hits"),
            "cache_misses": health_after.get("cache_misses"),
            "spawn_storm_warning": health_after.get("spawn_storm_warning"),
            "same_db_process_count": health_after.get("same_db_process_count"),
        },
        "response_diet": response_modes,
        "read_only_safety": {
            "mutating_tool_tested": "mem_snapshot_create",
            "blocked": bool((blocked.get("result") or {}).get("isError")),
            "error": result_payload(blocked),
        },
        "closure_control": {
            "done": completion.get("done"),
            "primary_reason": completion.get("primary_reason"),
            "pending_count": completion.get("pending_count"),
            "blocker_count": completion.get("blocker_count"),
            "dod_missing_count": completion.get("dod_missing_count"),
            "has_open_work": open_work.get("has_open_work"),
        },
    }


def run_telemetry_smoke(python: Path, work_root: Path) -> dict[str, Any]:
    db_path = work_root / "telemetry" / "memory.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_log_dir = work_root / "telemetry" / "runtime"
    mcp = MCPProcess(
        python=python,
        db_path=db_path,
        profile="minimal",
        read_only=True,
        response_mode="compact",
        telemetry_mode="summary",
        runtime_log_dir=runtime_log_dir,
    )
    try:
        mcp.request("initialize", {})
        mcp.request("tools/list", {})
        mcp.tool("mem_health_runtime", {})
    finally:
        mcp.close()
    event_files = list(runtime_log_dir.rglob("events.jsonl"))
    if not event_files:
        return {"ok": False, "events": []}
    events = [json.loads(line) for line in event_files[0].read_text(encoding="utf-8").splitlines() if line.strip()]
    return {
        "ok": True,
        "event_count": len(events),
        "events": [event.get("event") for event in events],
        "stores_memory_content": False,
    }


def default_scenario_file(sandbox_root: Path) -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.with_name("scenarios.json"),
        here.parent.parent / "fixtures" / "scenarios.json",
        sandbox_root / "fixtures" / "scenarios.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return sandbox_root / "fixtures" / "scenarios.json"


def default_public_root(fixtures_path: Path) -> Path:
    if fixtures_path.parent.name == "v1.0.0":
        return fixtures_path.parent.parent
    return Path(__file__).resolve().parent.parent / "export_public"


def write_methodology(path: Path, fixtures_hash: str, runner_hash: str) -> None:
    path.write_text(
        "\n".join(
            [
                "# Verification methodology",
                "",
                "These results are reproducible evidence for the codex-agent-mem `1.0.x` public scenario set.",
                "",
                "## Execution environment",
                "",
                "- Runtime: Codex Desktop",
                "- Model: not part of benchmark; synthetic fixtures only",
                "- Reasoning effort: not part of benchmark; synthetic fixtures only",
                "- Data: synthetic fixtures only",
                "",
                "## What is measured",
                "",
                "- Context compression: source tokens vs generated memory pack tokens.",
                "- Repeated-pack avoidance: `known_pack_hash` returning `not_modified=true`.",
                "- Lazy initialization: health/list calls do not initialize SQLite until a DB-backed tool is used.",
                "- Minimal tool surface: the low-impact MCP profile exposes four tools.",
                "- Read-only safety: mutating tools are blocked.",
                "- Response diet: compact, balanced and verbose textual response sizes.",
                "- Telemetry: local JSONL metadata events without memory content.",
                "- Closure control: deterministic refusal to mark work done without evidence.",
                "",
                "## Reproducibility",
                "",
                f"- Fixtures SHA-256: `{fixtures_hash}`",
                f"- Runner SHA-256: `{runner_hash}`",
                "",
                "Run from the project environment with the public fixture and runner:",
                "",
                "```bash",
                "python docs/verification/v1.0.0/run_verification.py --scenario-file docs/verification/v1.0.0/scenarios.json",
                "```",
                "",
                "The public result files intentionally avoid private absolute paths and real user data.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_public_readme(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Verification evidence",
                "",
                "This directory contains reproducible, sanitized evidence for codex-agent-mem.",
                "",
                "The current public run uses synthetic fixtures and records local runtime metadata for the `1.0.x` release line. It is not an external model benchmark.",
                "",
                "The verification set covers:",
                "",
                "- context compression and token savings;",
                "- repeated-pack avoidance with `known_pack_hash`; ",
                "- lazy MCP initialization;",
                "- minimal tool surface;",
                "- read-only safety;",
                "- response diet;",
                "- local telemetry;",
                "- closure-control checks;",
                "- a sub-agent handoff scenario.",
                "",
                "Start here:",
                "",
                "- `v1.0.0/RESULTS.md`",
                "- `v1.0.0/results.json`",
                "- `v1.0.0/METHODOLOGY.md`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_results_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# v1.0.x verification results",
        "",
        "These are reproducible, sanitized results generated from synthetic fixtures.",
        "",
        "Execution context:",
        "",
        "- Runtime: Codex Desktop",
        "- Model: not part of benchmark; synthetic fixtures only",
        "- Reasoning effort: not part of benchmark; synthetic fixtures only",
        "",
        "## Snapshot",
        "",
        "| Scenario | Source tokens | Pack tokens | Saved | not_modified | Tools | Lazy init | Read-only |",
        "|---|---:|---:|---:|---|---:|---|---|",
    ]
    for item in payload["scenarios"]:
        comp = item["context_compression"]
        lines.append(
            "| {title} | {source:,} | {pack:,} | {saved:.2f}% | {not_modified} | {tools} | {lazy_before}->{lazy_after} | {blocked} |".format(
                title=item["title"],
                source=comp["source_tokens"],
                pack=comp["pack_tokens"],
                saved=comp["savings_percent"],
                not_modified=str(item["not_modified"]["supported"]).lower(),
                tools=item["minimal_profile"]["tool_count"],
                lazy_before=str(item["lazy_init"]["before_db_tool"]).lower(),
                lazy_after=str(item["lazy_init"]["after_context_pack"]).lower(),
                blocked=str(item["read_only_safety"]["blocked"]).lower(),
            )
        )
    lines.extend(["", "## Token savings by scenario", ""])
    for item in payload["scenarios"]:
        comp = item["context_compression"]
        lines.extend(
            [
                f"### {item['title']}",
                "",
                item["plain_language"],
                "",
                f"- Source context: ~{comp['source_tokens']:,} tokens",
                f"- Memory pack: ~{comp['pack_tokens']:,} tokens",
                f"- Tokens not resent: ~{comp['saved_tokens']:,}",
                f"- Estimated savings: {comp['savings_percent']:.2f}%",
                f"- Pack hash: `{comp['pack_hash']}`",
                "",
                "`source` " + bar(100),
                "`pack`   " + bar(pct(comp["pack_tokens"], comp["source_tokens"])),
                "`saved`  " + bar(comp["savings_percent"]),
                "",
            ]
        )
        if item["subagents"]:
            lines.extend(["Sub-agent example:", ""])
            for subagent in item["subagents"]:
                lines.append(f"- `{subagent['role']}`: {subagent['task']}")
            lines.append("")
    lines.extend(
        [
            "## Repeated context avoided",
            "",
            "`known_pack_hash` lets the agent ask whether a pack changed before re-sending it.",
            "",
            "| Scenario | Result |",
            "|---|---|",
        ]
    )
    for item in payload["scenarios"]:
        lines.append(f"| {item['title']} | `not_modified={str(item['not_modified']['supported']).lower()}` |")
    lines.extend(
        [
            "",
            "## Runtime safety",
            "",
            "| Metric | Result |",
            "|---|---|",
            f"| Minimal profile tools | {', '.join(payload['scenarios'][0]['minimal_profile']['tools'])} |",
            f"| Tool count in minimal profile | {payload['scenarios'][0]['minimal_profile']['tool_count']} |",
            "| Lazy initialization before DB-backed tool | `false` |",
            "| Lazy initialization after context pack | `true` |",
            "| Mutating tool tested in read-only mode | `mem_snapshot_create` |",
            "| Mutating tool blocked | `true` |",
            "",
            "## Response diet",
            "",
            "Text shown to the model can be kept compact while the structured payload remains available to MCP clients.",
            "",
            "| Scenario | Compact text chars | Balanced text chars | Verbose text chars |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in payload["scenarios"]:
        diet = item["response_diet"]
        lines.append(
            f"| {item['title']} | {diet['compact']['content_text_chars']:,} | {diet['balanced']['content_text_chars']:,} | {diet['verbose']['content_text_chars']:,} |"
        )
    lines.extend(
        [
            "",
            "## Telemetry smoke",
            "",
            "- Telemetry mode tested: `summary`",
            f"- Events captured: {', '.join(payload['telemetry']['events'])}",
            f"- Stores memory content: `{str(payload['telemetry']['stores_memory_content']).lower()}`",
            "",
            "## Interpretation",
            "",
            "These numbers are not a universal guarantee. They show reproducible behavior on public synthetic fixtures.",
            "The expected value is highest when an agent would otherwise resend repeated project context across sessions.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def copy2_unless_same(src: Path, dst: Path) -> None:
    try:
        if src.resolve() == dst.resolve():
            return
    except FileNotFoundError:
        pass
    shutil.copy2(src, dst)


def copy_public_export(run_dir: Path, public_dir: Path, export_dir: Path, fixtures_path: Path, runner_path: Path) -> None:
    public_dir.mkdir(parents=True, exist_ok=True)
    export_dir.mkdir(parents=True, exist_ok=True)
    write_public_readme(public_dir.parent / "README.md")
    write_public_readme(export_dir.parent / "README.md")
    for name in ("RESULTS.md", "results.json", "METHODOLOGY.md", "checksums_sha256.txt"):
        copy2_unless_same(run_dir / name, public_dir / name)
        copy2_unless_same(run_dir / name, export_dir / name)
    copy2_unless_same(fixtures_path, public_dir / "scenarios.json")
    copy2_unless_same(fixtures_path, export_dir / "scenarios.json")
    copy2_unless_same(runner_path, public_dir / "run_verification.py")
    copy2_unless_same(runner_path, export_dir / "run_verification.py")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run codex-agent-mem public verification scenarios.")
    parser.add_argument(
        "--sandbox-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--public-root",
        type=Path,
        default=None,
    )
    parser.add_argument("--scenario-file", type=Path, default=None)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()

    sandbox = args.sandbox_root or (
        args.scenario_file.parent if args.scenario_file else Path(__file__).resolve().parent.parent
    )
    fixtures_path = args.scenario_file or default_scenario_file(sandbox)
    public_root = args.public_root or default_public_root(fixtures_path)
    runner_path = Path(__file__).resolve()
    fixtures = read_json(fixtures_path)
    run_id = "v1.0.0__" + datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S_UTC")
    run_dir = sandbox / "runs" / run_id
    work_root = run_dir / "_work"
    run_dir.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)

    scenarios = [run_scenario(args.python, scenario, work_root) for scenario in fixtures["scenarios"]]
    telemetry = run_telemetry_smoke(args.python, work_root)
    fixtures_hash = sha256_file(fixtures_path)
    runner_hash = sha256_file(runner_path)
    payload = {
        "schema_version": 1,
        "codex_agent_mem_version": __version__,
        "run_id": run_id,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "execution_context": fixtures["execution_context"],
        "privacy": fixtures["privacy"],
        "fixtures_sha256": fixtures_hash,
        "runner_sha256": runner_hash,
        "scenarios": scenarios,
        "telemetry": telemetry,
    }
    results_json = run_dir / "results.json"
    results_md = run_dir / "RESULTS.md"
    methodology = run_dir / "METHODOLOGY.md"
    checksums = run_dir / "checksums_sha256.txt"
    write_json(results_json, payload)
    write_results_markdown(results_md, payload)
    write_methodology(methodology, fixtures_hash, runner_hash)

    checksum_lines = []
    for path in (fixtures_path, runner_path, results_json, results_md, methodology):
        checksum_lines.append(f"{sha256_file(path)}  {path.name}")
    checksums.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    public_v = public_root / "v1.0.0"
    export_v = sandbox / "export_public" / "v1.0.0"
    copy_public_export(run_dir, public_v, export_v, fixtures_path, runner_path)
    if work_root.exists():
        shutil.rmtree(work_root)
    print(f"verification_run={run_id}")
    print(f"results={results_md}")
    print(f"public_export={public_v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
