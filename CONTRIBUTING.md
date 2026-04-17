# Contributing

Thanks for contributing to `codex-agent-mem`.

## Current scope

The current release line is intentionally narrow:

- Codex notify capture
- local SQLite persistence
- MCP retrieval
- heuristic extraction
- FastAPI inspection surface

Please keep changes aligned with the current scope unless the repository issue or milestone explicitly expands it.

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
- Do not add broad platform claims that the code does not yet support
- Prefer small, explicit interfaces over hidden automation
- Keep documentation aligned with the actual implementation

## Documentation expectations

If you change behavior, update the relevant docs:

- `README.md`
- `docs/quickstart.md`
- `docs/codex-integration.md`
- `docs/support-matrix.md`
- `docs/design-decisions.md`

## Pull request guidance

- Explain what changed
- Explain why it changed
- Call out user-facing behavior differences
- Call out test or packaging impact
- If scope expanded, state that explicitly
