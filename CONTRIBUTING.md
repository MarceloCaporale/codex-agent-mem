# Contributing

Thanks for contributing to `codex-agent-mem`.

## Current scope

The current release line focuses on:

- local-first MCP memory
- local SQLite persistence
- runtime/client compatibility
- reliability and release hygiene
- validation, documentation, and packaging

Please keep changes aligned with the local-first MCP design. Larger architecture changes should start with an issue or discussion before a pull request.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## Required checks

Run these before opening a pull request:

```powershell
ruff check .
python -m compileall src
pytest -q
python scripts/mcp_contract_smoke.py
codex-agent-mem-smoke
```

If your change affects packaging or install flow:

```powershell
python -m build
```

## Coding expectations

- Preserve the public/runtime distinction:
  - repo and CLI name: `codex-agent-mem`
  - Python package name: `codex_agent_mem`
- Keep Windows paths and TOML examples copy-pasteable
- Back new compatibility or performance claims with evidence, tests, or validation notes
- Prefer small, explicit interfaces over hidden automation
- Keep documentation aligned with the actual implementation
- Use temporary databases for tests and smoke checks; never rely on a maintainer's operational database

## Documentation expectations

If you change behavior, update the relevant docs:

- `README.md`
- `README_ES.md`
- `README_DE.md`
- `README_JA.md`
- `README_ZH.md`
- `docs/quickstart.md`
- `docs/support-matrix.md`
- `docs/validation/`
- `docs/design-decisions.md`

The README files are equivalent documents in different languages. Content changes should stay aligned across all of them.

## Pull request guidance

- Explain what changed
- Explain why it changed
- Call out user-facing behavior differences
- Call out test or packaging impact
- If scope expanded, state that explicitly
